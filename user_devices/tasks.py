import logging

import time
from celery import shared_task, group
from celery.exceptions import SoftTimeLimitExceeded
from .models import Device, Gateway, DeviceData, EnergyData
from pymodbus.client import ModbusTcpClient
from redis import Redis 
from redis.lock import Lock
import user_devices.functions as functions

logger = logging.getLogger(__name__)

redis_client = Redis(host='redis', port=6379)

"""
    Celery task to:
    1. Scan devices connected to the gateway.
    2. Read Modbus registers for each device.
    3. Map the data to variables and compute derived values.
    4. Save data variable in database in JSON format.
"""
@shared_task(soft_time_limit=240, time_limit=300)
def scan_and_read_devices(gateway_ip):
    lock_key = f"lock_device_{gateway_ip}"
    
    # Use context manager to handle lock acquisition and release automatically
    with Lock(redis_client, lock_key, timeout=300) as lock:
        gateway = Gateway.objects.get(ip_address=gateway_ip)
        logger.info(f"Scanning devices for gateway {gateway.ip_address}")

        # Get only devices connected to this gateway IP
        devices = Device.objects.filter(Gateway = gateway)
        if not devices:
            logger.info(f"No devices found for gateway {gateway.ip_address}")
            return

        for device in devices:
            if device.is_enabled:
                try:
                    logger.info(f"Protocol: {device.protocol}")
                    if device.protocol == 'modbus':
                        client = ModbusTcpClient(gateway.ip_address, port=device.port)
                        connection = client.connect()
                        if not connection:
                            logger.warning(f"Failed to connect to device on {gateway.ip_address}:{device.port}")
                            client.close()
                            continue
                        
                        logger.info(f"Connected to device {device.name} on {gateway.ip_address}:{device.port}")
                        
                        # Step 1a: Read raw Modbus registers
                        base_values = functions.read_modbus_registers(device, client)
                        logger.info(f"Values read: {base_values}")

                        # Step 2a: Map raw values
                        mapped_values = functions.map_variables(base_values, device)
                        logger.info(f"Values mapped: {mapped_values}")
                        
                        # Step 3: Compute derived variables
                        computed_values = functions.compute_variables(mapped_values, device)
                        logger.info(f"Values computed: {computed_values}")

                        # Step 4: Merge values
                        values = {**mapped_values, **computed_values}

                        logger.info(f"Final values: {values}")
                    elif device.protocol == 'dlms':
                        logger.info(f"Connected to device {device.name} on {gateway.ip_address}:{device.port}")
                        values = functions.read_dlms_values(device)
                        logger.info(f"Values read: {values}")
                    
                    else:
                        continue
                    
                    if values is not None:

                        # Step 5: Compute device availability
                        device.availability = functions.compute_device_availability(device, values)
                        logger.info(f"Device availability: {device.availability}")

                        # Step 6: Compute energy
                        logger.info(f"Computing energy for device {device.name}")
                        device_data = DeviceData.objects.filter(device_name=device)
                        energy_data = EnergyData.objects.filter(device_name=device)
                        energy_values = functions.compute_energy(values, device_data, energy_data)

                        # Step 7: Store in DB
                        functions.store_data_in_database(device, values)
                        logger.info(f"Data saved for device {device.name}")

                        # Step 8: Store energy data in DB separately
                        if energy_values is not None:
                            functions.store_energy_data_in_database(device, energy_values)
                            device.daily_production = energy_values.get('Energy_daily_produced', {}).get('value', 0.0)
                            device.daily_consumption = energy_values.get('Energy_daily_consumed', {}).get('value', 0.0)
                            logger.info(f"Energy data saved for device {device.name}")

                        device.save()
                        logger.info(f"Device availability saved for device {device.name}")

                except Exception as e:
                    logger.error(f"Error while reading values for device {device.name}: {e}")
                    return
                finally:
                    if device.protocol == 'modbus':
                        client.close()        
                        
@shared_task
def compute_plant_metrics():
    """
    Celery task to compute and store plant metrics (availability, performance, production, consumption, radiance)
    for all gateways. Runs every 15 minutes.
    """
    logger.info("Computing plant metrics for all gateways...")
    
    try:
        gateways = Gateway.objects.all()
        
        for gateway in gateways:
            try:
                # Get devices for this gateway
                devices = Device.objects.filter(Gateway=gateway)
                if not devices:
                    logger.info(f"No devices found for gateway {gateway.ip_address}")
                    continue
                
                # Compute plant availability
                availability = functions.compute_plant_availability(gateway, devices)

                # Compute plant performance
                performance = functions.compute_plant_performance(gateway, devices)

                # Compute plant production
                production = functions.compute_plant_production(gateway, devices)
                
                # Collect radiance data from devices
                radiance_value = functions.find_radiance_value(devices)

                # Create new gateway data with value and unit, like device data
                gateway_data = {
                    'availability': {'value': availability, 'unit': '%'},
                    'performance': {'value': performance, 'unit': '%'},
                    'production': {'value': production, 'unit': 'kW'},
                    'radiance': {'value': radiance_value, 'unit': 'W/m²'}
                }
                functions.store_gateway_data_in_database(gateway, gateway_data)
                logger.info(f"Plant availability, performance, production and radiance saved for gateway {gateway.ip_address}")
                
            except Exception as e:
                logger.error(f"Error while computing plant metrics for gateway {gateway.ip_address}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in compute_plant_metrics task: {e}")


@shared_task
def check_all_devices():
    logger.info("Checking all devices...")
    gateways = Gateway.objects.all()
    gateway_ip = [gateway.ip_address for gateway in gateways]
    # Create a group of tasks for checking each device
    job = group(scan_and_read_devices.s(ip_address) for ip_address in gateway_ip)
    job.apply_async()