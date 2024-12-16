import logging
from pymodbus.client import ModbusTcpClient

logger = logging.getLogger(__name__)

MAX_WORDS_PER_READ = 12
TIMEOUT = 5                 # Timeout per la connessione

def read_modbus_registers(device, client):
    """
    Reads Modbus registers for a given device.
    Handles multiple reads if needed due to word limits.
    """
    try:
        start_address = int(device.start_address, 16)
        bytes_count = device.bytes_count #TODO: SONO WORDS NON BYTES

        # Split reads into chunks of MAX_WORDS_PER_READ
        base_values = {}
        for offset in range(0, bytes_count, MAX_WORDS_PER_READ):
            current_address = start_address + offset
            words_to_read = min(MAX_WORDS_PER_READ, (bytes_count - offset) // 2)
            response = client.read_input_registers(address=current_address, count=words_to_read,slave=device.slave_id)

            if response.isError():
                logger.info(f"Error reading address {current_address} for device {device.name}")
                continue

            # Map raw values to the address space
            for i, value in enumerate(response.registers):
                base_values[current_address + i * 2] = value
        return base_values

    except Exception as e:
        logger.info(f"Modbus error on device {device.name}: {e}")
        return None

    finally:
        client.close()