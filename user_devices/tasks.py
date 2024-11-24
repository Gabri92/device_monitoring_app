import logging
import time
from celery import shared_task, group
from .models import Device, DeviceData, ModbusAddress
from pymodbus.client import ModbusTcpClient
from django.utils import timezone
from redis import Redis 
from redis.lock import Lock

logger = logging.getLogger(__name__)

redis_client = Redis(host='redis', port=6379)

@shared_task
def test_celery_task():
    time.sleep(5)
    logger.info("Celery task executed")

@shared_task
def check_device(device_mac):
    lock_key = f"lock_device_{device_mac}"
    lock = Lock(redis_client, lock_key, timeout=180)

    if lock.acquire(blocking=False):
        try:
            device = Device.objects.get(mac_address=device_mac)
            logger.info(f"Checking device: {device.name}")
            is_alive = False
            attempts = 0

            while attempts < 3:
                client = ModbusTcpClient(device.ip_address, port=device.port)
                connection = client.connect()

                if connection:
                    logger.info(f"Device {device.name} is online")
                    device.is_active = True
                    device.last_seen = timezone.now()
                    device.save()
                    read_attempts = 0

                    addresses = ModbusAddress.objects.filter(device = device)

                    while read_attempts < 3:
                        try:
                            for address in addresses:
                                response = client.read_input_registers(address.address, address.count)
                                if not response.isError():
                                    values_dict = {f'value_{i+1}': response.registers[i] for i in range(address.count)}
                                    values_dict['device'] = device.name
                                    logger.info(f"Data read from {device.name}: {values_dict}")
                                    data = DeviceData.objects.create(device=device, value=values_dict)
                                    data.save()
                                    logger.info(f"Data saved for {device.name}")
                                    is_alive = True
                                else:
                                    logger.info(f"Error reading data from {device.name}")
                                    read_attempts += 1
                                    time.sleep(5)
                            if is_alive:
                                break
                        except:
                                logger.info(f"Error reading data from {device.name}")
                                read_attempts += 1
                                time.sleep(5)

                    client.close()
                    if is_alive:
                        break
                else:
                    logger.info(f"Could not connect to {device.name}. Attempt number {attempts + 1}")
                    device.is_active = False 
                    device.save()                  
                attempts += 1
                time.sleep(10)

            if not is_alive:
                logger.info(f"{device.name} is not responsive after 3 connection attempts and 3 read attempts.")
        finally:
            lock.release()


@shared_task
def check_all_devices():
    logger.info("Checking all devices...")
    devices = Device.objects.all()
    device_mac = [device.mac_address for device in devices]

    # Create a group of tasks for checking each device
    job = group(check_device.s(mac_address) for mac_address in device_mac)
    job.apply_async()  # Start the group of tasks