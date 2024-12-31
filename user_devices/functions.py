import logging
import time
import json
from sympy import sympify
from pymodbus.client import ModbusTcpClient
from .models import MappingVariable, ComputedVariable, DeviceData
from decimal import Decimal

logger = logging.getLogger(__name__)

MAX_WORDS_PER_READ = 12
TIMEOUT = 5                 # Timeout per la connessione

"""
Reads Modbus registers for a given device.
Handles multiple reads if needed due to word limits.
"""
def read_modbus_registers(device, client):
    try:
        start_address = int(device.start_address, 16)
        bytes_count = device.bytes_count 

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
            time.sleep(0.1)
        return base_values

    except Exception as e:
        logger.info(f"Modbus error on device {device.name}: {e}")
        return None
    

"""
Maps raw Modbus data to the defined variables in the VariableAddressMapping model.
Converts values using the defined conversion factors.
"""
def map_variables(base_values, device):
    mapped_values = {}
    mappings = MappingVariable.objects.filter(device=device)
    logger.info(f"Mapping obtained from database")

    for mapping in mappings:
        try:
            address = int(mapping.address, 16)
            logger.info(f"Mapping: {mapping.var_name}, Start: {mapping.address}")
            logger.info(f"Base values length: {len(base_values)}")

            raw_value = base_values[address]

            # Apply conversion factor
            converted_value = raw_value * mapping.conversion_factor
            mapped_values[mapping.var_name] = {
                "value": converted_value,
                "unit": mapping.unit 
            }

        except Exception as e:
            mapped_values[mapping.var_name] = {
                "value": 0,
                "unit": mapping.unit if hasattr(mapping, "unit") else "N/A"
            }
            logger.info(f"Error while mapping the values: {e}")
            continue
            # Convert to JSON
    json_result = json.dumps(mapped_values, indent=4)
    logger.info(f"Mapped JSON: {json_result}")
    return mapped_values


"""
Computes derived variables using formulas defined in ComputedVariable.
"""
def compute_variables(mapped_values, device):
    computed_vars = ComputedVariable.objects.filter(device=device)
    logger.info(f"Computing values:  {list(computed_vars.values())}")

    results = {}
    for var in computed_vars:
        try:

            "Work the data and adapt it to the sympify formula input data"
            values = {key: value_data["value"] for key, value_data in mapped_values.items()}
            logger.info(f"Worked data: {values}")

            formula = sympify(a=var.formula)
            logger.info(f"formula: {formula}")

            computed_value = float(formula.evalf(subs=values))
            logger.info(f"Computed value: {computed_value}")

            results[var.var_name] = {
                "value": computed_value,
                "unit": var.unit 
            }
            logger.info(computed_vars)
        except Exception as e:
            results[var.var_name] = {
                "value": 0,
                "unit": var.unit if hasattr(var, "unit") else "N/A"
            }
            logger.info(f"Error while mapping the values: {e}")
            continue

    # Convert to JSON
    json_result = json.dumps(results, indent=4)
    logger.info(f"Mapped JSON: {json_result}")
    logger.info(f"Computed variables for device {device.name}: {computed_vars}")
    return results

"""
Save device data into the DeviceData model.
"""
def store_data_in_database(device, data):
    try:
        DeviceData.objects.create(
            user=device.user,
            gateway=device.Gateway,
            device_name=device,
            data=data
        )
    except Exception as e:
        logger.info(f"Error while saving the data: {e}")