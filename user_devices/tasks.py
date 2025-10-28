import logging

import time
from celery import shared_task, group
from celery.exceptions import SoftTimeLimitExceeded
from .models import Device, Gateway, DeviceData, EnergyData
from pymodbus.client import ModbusTcpClient
from redis import Redis 
from redis.lock import Lock
import user_devices.functions as functions
from .helper_funcs import convert_to_local_time

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


@shared_task
def midnight_energy_aggregation():
    """
    Celery task to aggregate and save energy data at midnight.
    Collects daily, weekly, and monthly energy totals per gateway.
    """
    from datetime import datetime, timezone, timedelta
    
    logger.info("Starting midnight energy aggregation...")
    
    try:
        # Get current time and convert to local timezone (same as functions.py)
        now = datetime.now(timezone.utc)
        now_local = convert_to_local_time(now)
        today = now_local.date()
        
        # Get all gateways
        gateways = Gateway.objects.all()
        
        if not gateways.exists():
            logger.info("No gateways found for energy aggregation")
            return
        
        # Calculate time ranges using same logic as functions.py
        # Start of UTC day
        start_of_day_utc = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Convert to local (Django TZ)
        start_of_day_local = convert_to_local_time(start_of_day_utc)
        
        # For filtering DB (which expects UTC), convert back. Timestamps are utc in django
        start_of_day_filter = start_of_day_local.astimezone(timezone.utc)
        
        # Start of UTC week
        start_of_week_utc = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
        
        # Convert to local (Django TZ)
        start_of_week_local = convert_to_local_time(start_of_week_utc)
        
        # For filtering DB (which expects UTC), convert back. Timestamps are utc in django
        start_of_week_filter = start_of_week_local.astimezone(timezone.utc)
        
        # Start of UTC month
        start_of_month_utc = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Convert to local (Django TZ)
        start_of_month_local = convert_to_local_time(start_of_month_utc)
        
        # For filtering DB (which expects UTC), convert back. Timestamps are utc in django
        start_of_month_filter = start_of_month_local.astimezone(timezone.utc)
        
        # Loop through each gateway
        for gateway in gateways:
            try:
                # Get active devices for this gateway
                devices = Device.objects.filter(Gateway=gateway, is_enabled=True)
                
                if not devices.exists():
                    logger.info(f"No active devices found for gateway {gateway.name}")
                    continue
                
                # Initialize aggregation data for this gateway
                aggregation_data = {
                    "data_type": "Data Aggregate",
                    "date": today.isoformat(),
                    "daily": {"produced": 0.0, "consumed": 0.0},
                    "weekly": {"produced": 0.0, "consumed": 0.0},
                    "monthly": {"produced": 0.0, "consumed": 0.0}
                }
                
                # Loop through each device in this gateway
                for device in devices:
                    try:
                        # Get energy data for this device
                        energy_data_queryset = EnergyData.objects.filter(device_name=device)
                        
                        if not energy_data_queryset.exists():
                            logger.info(f"No energy data found for device {device.name}")
                            continue
                        
                        # Get energy data for each period
                        daily_data = energy_data_queryset.filter(timestamp__gte=start_of_day_filter)
                        weekly_data = energy_data_queryset.filter(timestamp__gte=start_of_week_filter)
                        monthly_data = energy_data_queryset.filter(timestamp__gte=start_of_month_filter)
                        
                        # Sum all Energy_produced and Energy_consumed values for each period
                        daily_prod, daily_cons = 0.0, 0.0
                        weekly_prod, weekly_cons = 0.0, 0.0
                        monthly_prod, monthly_cons = 0.0, 0.0
                        
                        # Sum daily produced and consumed
                        for record in daily_data:
                            data = record.data
                            if isinstance(data, dict):
                                energy_produced = data.get('Energy_produced', {})
                                energy_consumed = data.get('Energy_consumed', {})
                                if isinstance(energy_produced, dict):
                                    daily_prod += energy_produced.get('value', 0.0)
                                if isinstance(energy_consumed, dict):
                                    daily_cons += energy_consumed.get('value', 0.0)
                        
                        # Sum weekly produced and consumed
                        for record in weekly_data:
                            data = record.data
                            if isinstance(data, dict):
                                energy_produced = data.get('Energy_produced', {})
                                energy_consumed = data.get('Energy_consumed', {})
                                if isinstance(energy_produced, dict):
                                    weekly_prod += energy_produced.get('value', 0.0)
                                if isinstance(energy_consumed, dict):
                                    weekly_cons += energy_consumed.get('value', 0.0)
                        
                        # Sum monthly produced and consumed
                        for record in monthly_data:
                            data = record.data
                            if isinstance(data, dict):
                                energy_produced = data.get('Energy_produced', {})
                                energy_consumed = data.get('Energy_consumed', {})
                                if isinstance(energy_produced, dict):
                                    monthly_prod += energy_produced.get('value', 0.0)
                                if isinstance(energy_consumed, dict):
                                    monthly_cons += energy_consumed.get('value', 0.0)
                        
                        # Add to aggregation totals
                        aggregation_data["daily"]["produced"] += daily_prod
                        aggregation_data["daily"]["consumed"] += daily_cons
                        aggregation_data["weekly"]["produced"] += weekly_prod
                        aggregation_data["weekly"]["consumed"] += weekly_cons
                        aggregation_data["monthly"]["produced"] += monthly_prod
                        aggregation_data["monthly"]["consumed"] += monthly_cons
                        
                        logger.info(f"Device {device.name}: Daily({daily_prod:.2f}/{daily_cons:.2f}), "
                                  f"Weekly({weekly_prod:.2f}/{weekly_cons:.2f}), "
                                  f"Monthly({monthly_prod:.2f}/{monthly_cons:.2f})")
                        
                    except Exception as e:
                        logger.error(f"Error processing device {device.name}: {e}")
                        continue
                
                # Round values to 2 decimal places
                aggregation_data["daily"]["produced"] = round(aggregation_data["daily"]["produced"], 2)
                aggregation_data["daily"]["consumed"] = round(aggregation_data["daily"]["consumed"], 2)
                aggregation_data["weekly"]["produced"] = round(aggregation_data["weekly"]["produced"], 2)
                aggregation_data["weekly"]["consumed"] = round(aggregation_data["weekly"]["consumed"], 2)
                aggregation_data["monthly"]["produced"] = round(aggregation_data["monthly"]["produced"], 2)
                aggregation_data["monthly"]["consumed"] = round(aggregation_data["monthly"]["consumed"], 2)
                
                # Save aggregated data for this gateway
                try:
                    # Get or create aggregation device for this gateway
                    aggregation_device_name = f"Aggregate_{gateway.name}"
                    aggregation_device, created = Device.objects.get_or_create(
                        name=aggregation_device_name,
                        defaults={
                            'Gateway': gateway,
                            'is_enabled': False,  # Virtual device, not scanned
                            'protocol': 'modbus',  # Default value
                        }
                    )
                    
                    if created:
                        logger.info(f"Created aggregation device: {aggregation_device_name} for gateway {gateway.name}")
                        # Copy users from gateway to the aggregation device
                        aggregation_device.user.set(gateway.user.all())
                    
                    # Create EnergyData entry for this gateway's aggregate
                    energy_data = EnergyData.objects.create(
                        Gateway=gateway,
                        device_name=aggregation_device,
                        data=aggregation_data
                    )
                    
                    # Set users from gateway
                    energy_data.user.set(gateway.user.all())
                    
                    logger.info(f"Gateway {gateway.name} - Midnight energy aggregation saved. Totals - Daily: {aggregation_data['daily']}, "
                               f"Weekly: {aggregation_data['weekly']}, Monthly: {aggregation_data['monthly']}")
                        
                except Exception as e:
                    logger.error(f"Error saving midnight aggregation for gateway {gateway.name}: {e}")
                    continue
                
            except Exception as e:
                logger.error(f"Error processing gateway {gateway.name}: {e}")
                continue
        
        logger.info("Midnight energy aggregation completed for all gateways")
        
    except Exception as e:
        logger.error(f"Error in midnight_energy_aggregation task: {e}")