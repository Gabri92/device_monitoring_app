import logging

import time
from celery import shared_task, group
from .models import Device, Gateway, DeviceData
from pymodbus.client import ModbusTcpClient
from redis import Redis 
from redis.lock import Lock
from .functions import read_modbus_registers, map_variables, read_dlms_values, compute_variables, compute_energy, store_data_in_database

logger = logging.getLogger(__name__)

redis_client = Redis(host='redis', port=6379)

"""
    Celery task to:
    1. Scan devices connected to the gateway.
    2. Read Modbus registers for each device.
    3. Map the data to variables and compute derived values.
    4. Save data variable in database in JSON format.
"""
@shared_task
def scan_and_read_devices(gateway_ip):
    lock_key = f"lock_device_{gateway_ip}"
    lock = Lock(redis_client, lock_key, timeout=180)

    if lock.acquire(blocking=False):
        try:
            gateway = Gateway.objects.get(ip_address=gateway_ip)
            logger.info(f"Scanning devices for gateway {gateway.ip_address}")

            # Get only devices connected to this gateway IP
            devices = Device.objects.filter(Gateway = gateway)
            if not devices:
                logger.info(f"No devices found for gateway {gateway.ip_address}")
                return

            for device in devices:
                if device.is_enabled:
                    logger.info(f"Protocol: {device.protocol}")
                    if device.protocol == 'modbus':
                        client = ModbusTcpClient(gateway.ip_address, port=device.port)
                        connection = client.connect()
                        if not connection:
                            logger.warning(f"Failed to connect to device on {gateway.ip_address}:{device.port}")
                            client.close()
                            continue

                    logger.info(f"Connected to device {device.name} on {gateway.ip_address}:{device.port}")
                    try:
                        
                        if device.protocol == 'modubs':
                            # Step 1a: Read raw Modbus registers
                            base_values = read_modbus_registers(device, client)
                            logger.info(f"Values read: {base_values}")
                            # Step 2a: Map raw values
                            mapped_values = map_variables(base_values, device)
                            logger.info(f"Values mapped: {mapped_values}")
                        elif device.protocol == 'dlms':
                            base_values = read_dlms_values(device)
                        else:
                            continue

                        # Step 3: Compute derived variables
                        computed_values = compute_variables(mapped_values, device)
                        logger.info(f"Values computed: {computed_values}")

                        # Step 4: Merge values
                        values = {**mapped_values, **computed_values}

                        # Step 5: Compute energy
                        device_data = DeviceData.objects.filter(device_name__name=device.name)
                        energy_values = compute_energy(values, device_data)
                        values.update(energy_values)
                        logger.info(f"Final values: {values}")

                        # Step 6: Store in DB
                        store_data_in_database(device, values)
                        logger.info(f"Data saved for device {device.name}")

                    except Exception as e:
                        logger.error(f"Error while reading values for device {device.name}: {e}")
                    finally:
                        if device.protocol == 'modbus':
                            client.close()
        finally:
            lock.release()


@shared_task
def check_all_devices():
    logger.info("Checking all devices...")
    gateways = Gateway.objects.all()
    gateway_ip = [gateway.ip_address for gateway in gateways]
# Create a group of tasks for checking each device
    job = group(scan_and_read_devices.s(ip_address) for ip_address in gateway_ip)
    job.apply_async()