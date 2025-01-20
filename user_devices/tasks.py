import logging
import time
from celery import shared_task, group
from .models import Device, Gateway, DeviceData
from pymodbus.client import ModbusTcpClient
from redis import Redis 
from redis.lock import Lock
from .functions import read_modbus_registers, map_variables, compute_variables, compute_energy, store_data_in_database

logger = logging.getLogger(__name__)

redis_client = Redis(host='redis', port=6379)

"""
    Celery task to:
    1. Scan devices connected to the gateway.
    2. Read Modbus registers for each device.
    3. Map the data to variables and compute derived values.
    4. Save data variable in database in JSON format
"""
@shared_task
def scan_and_read_devices(gateway_ip):
    lock_key = f"lock_device_{gateway_ip}"
    lock = Lock(redis_client, lock_key, timeout=180)

    if lock.acquire(blocking=False):
        try:
            gateway = Gateway.objects.get(ip_address=gateway_ip)
            client = ModbusTcpClient(gateway.ip_address, port=gateway.port)
            connection = client.connect()
            if connection:
                logger.info(f"Connected to {gateway.ip_address}")
                # Step 1: Scan devices
                devices = Device.objects.all()
                if not devices:
                    logger.info(f"Connected to {gateway.ip_address}")
                    return
                for device in devices:
                    try:
                        # Legge valori raw da registro modbus
                        base_values = read_modbus_registers(device, client)
                        logger.info(f"Values read: {base_values}")

                        # Converte i valori grezzi nei valori base mappati su sito admin
                        mapped_values = map_variables(base_values, device)
                        logger.info(f"Values mapped: {mapped_values}")

                        # Calcola valori combinazioni di letture precedenti
                        computed_values = compute_variables(mapped_values, device)
                        logger.info(f"Values computed: {computed_values}")

                        # Aggregate values in a single dictionary
                        values = {**mapped_values, **computed_values}

                        # Compute energy
                        device_data = DeviceData.objects.filter(device_name__name=device.name)
                        energy_values = compute_energy(values, device_data)
                       
                        values = {**values, **energy_values}
                        logger.info(f"Values: {values}")

                        store_data_in_database(device, values)
                        logger.info(f"Data have been saved")
                    except:
                        logger.info(f"Error while reading the values")
                        continue
            else:
               logger.info(f"Failed to connect to {gateway.ip_address}. ")
               return
        finally:
            client.close()
            lock.release()


@shared_task
def check_all_devices():
    logger.info("Checking all devices...")
    gateways = Gateway.objects.all()
    gateway_ip = [gateway.ip_address for gateway in gateways]
# Create a group of tasks for checking each device
    job = group(scan_and_read_devices.s(ip_address) for ip_address in gateway_ip)
    job.apply_async()