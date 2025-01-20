import logging
import time
import json
from sympy import sympify
from datetime import datetime, timezone, timedelta
from pymodbus.client import ModbusTcpClient
from .models import MappingVariable, ComputedVariable, DeviceData
from decimal import Decimal
from django.db.models import Sum
from django.db.models.expressions import RawSQL

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
Compute energy as power integral
"""
def compute_energy(variables, device_data):
    logger.info("Starting to compute integral values")
    try:
        # Get the most recent data
        previous_data = device_data.order_by('-timestamp').first()

        if previous_data and 'P' in previous_data.data and 'P' in variables:
            # Calculate delta time
            delta_time = (datetime.now(timezone.utc) - previous_data.timestamp).total_seconds()

            # Calculate the average value of power
            previous_p = previous_data.data.get('P', {}).get('value', 0)
            current_p = variables.get('P', {}).get('value', 0)
            average_value = (current_p + previous_p) / 2

            # Compute the integral value
            previous_energy = previous_data.data.get('Energy', {}).get('value', 0.0)
            integral_value = previous_energy + (average_value * delta_time)

            logger.info(f"Computed integral value: {integral_value}")
            logger.info(f"delta_time: {delta_time}, previouse_energy: {previous_energy}, previous_p: {previous_p}, current_p:{current_p}")
            # Compute energy for different periods
            now = datetime.now(timezone.utc)

            # Define date ranges
            one_day_ago = now - timedelta(days=1)
            one_week_ago = now - timedelta(weeks=1)
            one_month_ago = now - timedelta(days=30)  # Approximate month as 30 days

            # Use RawSQL to sum JSONB values
            daily_energy = device_data.filter(timestamp__gte=one_day_ago).aggregate(
                total_energy=Sum(
                    RawSQL("CAST(data->'Energy'->>'value' AS DOUBLE PRECISION)", [])
                )
            )['total_energy'] or 0.0

            weekly_energy = device_data.filter(timestamp__gte=one_week_ago).aggregate(
                total_energy=Sum(
                    RawSQL("CAST(data->'Energy'->>'value' AS DOUBLE PRECISION)", [])
                )
            )['total_energy'] or 0.0

            monthly_energy = device_data.filter(timestamp__gte=one_month_ago).aggregate(
                total_energy=Sum(
                    RawSQL("CAST(data->'Energy'->>'value' AS DOUBLE PRECISION)", [])
                )
            )['total_energy'] or 0.0

            # Store all computed values in a structured dictionary
            energy_data = {
                'Energy': {'value': integral_value, 'unit': 'J'},
                'Energy_daily': {'value': daily_energy, 'unit': 'J'},
                'Energy_weekly': {'value': weekly_energy, 'unit': 'J'},
                'Energy_monthly': {'value': monthly_energy, 'unit': 'J'},
            }

            logger.info(f"Computed energy data: {energy_data}")
            return energy_data

        else:
            # Initialize the integral value for the first entry
            energy_data = {
                'Energy': {'value': 0.0, 'unit': 'J'},
                'Energy_daily': {'value': 0.0, 'unit': 'J'},
                'Energy_weekly': {'value': 0.0, 'unit': 'J'},
                'Energy_monthly': {'value': 0.0, 'unit': 'J'},
            }
            logger.info("No previous data or 'P' variable found, initializing energy values to 0")
            return energy_data

    except Exception as e:
        logger.error(f"Error during computation: {e}", exc_info=True)
        energy_data = {
            'Energy': {'value': 0.0, 'unit': 'J'},
            'Energy_daily': {'value': 0.0, 'unit': 'J'},
                'Energy_weekly': {'value': 0.0, 'unit': 'J'},
            'Energy_monthly': {'value': 0.0, 'unit': 'J'},
        }
        return energy_data
        

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