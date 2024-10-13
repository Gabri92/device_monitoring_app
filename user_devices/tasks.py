import logging
import time
import datetime
from celery import shared_task, group
from .models import Device, DeviceData
from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)

@shared_task
def test_celery_task():
    time.sleep(5)
    logger.info("Celery task executed")

@shared_task
def check_device(device_mac):
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
            device.last_seen = datetime.datetime.now()
            read_attempts = 0

            while read_attempts < 3:
                try:
                    num_registers = 3
                    response = client.read_input_registers(0, num_registers)
                    if not response.isError():
                        logger.info(f"Device {device.name} responded with {response.registers}")
                        values_dict = {f'value_{i+1}': response.registers[i] for i in range(num_registers)}
                        DeviceData.objects.create(device=device, value=values_dict)
                        logger.info(f"Data saved for {device.name}")
                        is_alive = True
                        break
                    else:
                        logger.info(f"Error reading data from {device.name}")
                        read_attempts += 1
                        time.sleep(5)
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
        attempts += 1
        time.sleep(10)
    
    if not is_alive:
        logger.info(f"{device.name} is not responsive after 3 connection attempts and 3 read attempts.")

@shared_task
def check_all_devices():
    logger.info("Checking all devices...")
    devices = Device.objects.all()
    device_mac = [device.mac_address for device in devices]

    # Create a group of tasks for checking each device
    job = group(check_device.s(mac_address) for mac_address in device_mac)
    job.apply_async()  # Start the group of tasks