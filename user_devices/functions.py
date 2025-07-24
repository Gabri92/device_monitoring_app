import logging
import time
import json
import requests
from sympy import sympify
from datetime import datetime, timezone, timedelta
from pymodbus.client import ModbusTcpClient
from .models import ModbusMappingVariable, ComputedVariable, DeviceData
from decimal import Decimal
from django.db.models import Sum
from django.db.models.expressions import RawSQL
from fractions import Fraction

logger = logging.getLogger(__name__)

MAX_WORDS_PER_READ = 12
TIMEOUT = 5                 # Timeout per la connessione

# Helper to sanitize variable names
def sanitize_variable_name(name):
    return name.replace("-", "_").replace(" ", "_")

"""
Reads DLMS registers for a given device.
"""
def read_dlms_values(device):
    gateway_ip = device.Gateway.ip_address
    response = requests.get(f"http://127.0.0.1:5000/dlms/profile?obis_code=12")
    logger.info(response.json())
    return

"""
Reads Modbus registers for a given device.
Handles multiple reads if needed due to word limits.
"""
def read_modbus_registers(device, client):
    try:
        start_address = int(device.start_address, 16)
        logger.info(f"Start Address: {start_address}")
        bytes_count = device.bytes_count 
        logger.info(f"Start Address: {bytes_count }")
        
        # Split reads into chunks of MAX_WORDS_PER_READ
        base_values = {}
        for offset in range(0, bytes_count, MAX_WORDS_PER_READ):
            current_address = start_address + offset
            logger.info(f"Start Address: {current_address}")
            words_to_read = min(MAX_WORDS_PER_READ, (bytes_count - offset) // 2)
            if hasattr(device, 'register_type') and device.register_type == 'holding':
                response = client.read_holding_registers(address=current_address, count=words_to_read, slave=device.slave_id)
            else:
                response = client.read_input_registers(address=current_address, count=words_to_read, slave=device.slave_id)
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
    mappings = ModbusMappingVariable.objects.filter(device=device)
    logger.info(f"Mapping obtained from database")

    for mapping in mappings:
        try:
            address = int(mapping.address, 16)
            logger.info(f"Mapping: {mapping.var_name}, Start: {mapping.address}")
            logger.info(f"Base values length: {len(base_values)}")

            # Calcolo quanti registri servono per il bit_length richiesto
            num_registers = mapping.bit_length // 16
            registers = []
            for i in range(num_registers):
                reg_addr = address + i * 2  # ogni registro Modbus è 2 byte
                if reg_addr in base_values:
                    registers.append(base_values[reg_addr])
                else:
                    raise Exception(f"Missing register at address {hex(reg_addr)} for variable {mapping.var_name}")

            # Combino i registri in un unico valore
            # I registri Modbus sono big-endian per default
            raw_bytes = b''.join(reg.to_bytes(2, byteorder='big') for reg in registers)
            raw_value = int.from_bytes(raw_bytes, byteorder='big', signed=mapping.is_signed)

            # Applico il conversion factor
            try:
                logger.info(f"Conv factor from mapping: {mapping.conversion_factor}")
                if mapping.conversion_factor.__contains__("/"):
                    conversion_factor = float(Fraction(mapping.conversion_factor))
                else:
                    conversion_factor = float(mapping.conversion_factor)
            except (ValueError, TypeError, ZeroDivisionError):
                logger.warning(f"Invalid conversion factor for {mapping.var_name}: {mapping.conversion_factor}. Defaulting to 0.")
                conversion_factor = 0.0
            logger.info(f"Conversion factor: {conversion_factor}")
            converted_value = raw_value * conversion_factor
            sanitized_name = sanitize_variable_name(mapping.var_name)
            mapped_values[sanitized_name] = {
                "value": converted_value,
                "unit": mapping.unit 
            }

        except Exception as e:
            sanitized_name = sanitize_variable_name(mapping.var_name)
            mapped_values[sanitized_name] = {
                "value": 0,
                "unit": mapping.unit if hasattr(mapping, "unit") else "N/A"
            }
            logger.info(f"Error while mapping the values: {e}")
            continue
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

            sanitized_formula = sanitize_variable_name(var.formula)
            formula = sympify(a=sanitized_formula)
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

        # Define possible power variable names
        power_variable_names = ['P', 'Power', 'Potenza']

        power_name = None
        is_power_configured = False
        for name in power_variable_names:
            if previous_data and name in previous_data.data and name in variables:
                power_name = name
                is_power_configured = True
                break

        if previous_data and is_power_configured:
            # Calculate delta time
            delta_time = (datetime.now(timezone.utc) - previous_data.timestamp).total_seconds()

            # Calculate the average value of power
            previous_p = previous_data.data.get(power_name, {}).get('value', 0)
            current_p = variables.get(power_name, {}).get('value', 0)
            average_value = (current_p + previous_p) / 2

            # Compute the energy increment for this period
            energy_increment = average_value * delta_time

            # Get previous energy values
            previous_energy = previous_data.data.get('Energy', {}).get('value', 0.0)
            previous_energy_produced = previous_data.data.get('Energy_produced', {}).get('value', 0.0)
            previous_energy_consumed = previous_data.data.get('Energy_consumed', {}).get('value', 0.0)
           
            # Update produced/consumed based on the sign of energy increment
            # Negative power = energy produced, Positive power = energy consumed
            if average_value >= 0:
                # Consumption (positive power)
                energy_consumed = previous_energy_consumed + energy_increment
                energy_produced = previous_energy_produced
            else:
                # Production (negative power)
                energy_produced = previous_energy_produced + abs(energy_increment)
                energy_consumed = previous_energy_consumed

            # Total energy is still the running sum of all increments
            integral_value = previous_energy + energy_increment

            logger.info(f"Computed integral value: {integral_value}")
            
            # Compute energy for different periods
            now = datetime.now(timezone.utc)

            # Define date ranges
            one_day_ago = now - timedelta(days=1)
            one_week_ago = now - timedelta(weeks=1)
            one_month_ago = now - timedelta(days=30)  # Approximate month as 30 days

             # Calculate daily produced/consumed energy
            daily_records = device_data.filter(timestamp__gte=one_day_ago)
            daily_produced = daily_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) < 0 THEN ABS(CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION)) ELSE 0 END", []))
            )['total'] or 0.0
            
            daily_consumed = daily_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) >= 0 THEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) ELSE 0 END", []))
            )['total'] or 0.0

            # Calculate weekly produced/consumed energy
            weekly_records = device_data.filter(timestamp__gte=one_week_ago)
            weekly_produced = weekly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) < 0 THEN ABS(CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION)) ELSE 0 END", []))
            )['total'] or 0.0
            
            weekly_consumed = weekly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) >= 0 THEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) ELSE 0 END", []))
            )['total'] or 0.0

            # Calculate monthly produced/consumed energy
            monthly_records = device_data.filter(timestamp__gte=one_month_ago)
            monthly_produced = monthly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) < 0 THEN ABS(CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION)) ELSE 0 END", []))
            )['total'] or 0.0
            
            monthly_consumed = monthly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) >= 0 THEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) ELSE 0 END", []))
            )['total'] or 0.0

            # Apply time factor to get energy values (power × time)
            time_factor = delta_time  # This is approximate - ideally would sum actual time intervals

            # Store all computed values in a structured dictionary
            conv_factor_to_kwh =3.6 * 10**6
            energy_data = {
                'Energy': {'value': integral_value / conv_factor_to_kwh, 'unit': 'kWh'},
                'Energy_produced': {'value': energy_produced / conv_factor_to_kwh, 'unit': 'kWh'},
                'Energy_consumed': {'value': energy_consumed / conv_factor_to_kwh, 'unit': 'kWh'},
                
                'Energy_daily_produced': {'value': daily_produced * time_factor / conv_factor_to_kwh, 'unit': 'kWh'},
                'Energy_daily_consumed': {'value': daily_consumed * time_factor / conv_factor_to_kwh, 'unit': 'kWh'},
                
                'Energy_weekly_produced': {'value': weekly_produced * time_factor / conv_factor_to_kwh, 'unit': 'kWh'},
                'Energy_weekly_consumed': {'value': weekly_consumed * time_factor / conv_factor_to_kwh, 'unit': 'kWh'},
                
                'Energy_monthly_produced': {'value': monthly_produced * time_factor / conv_factor_to_kwh, 'unit': 'kWh'},
                'Energy_monthly_consumed': {'value': monthly_consumed * time_factor / conv_factor_to_kwh, 'unit': 'kWh'},
            }


            logger.info(f"Computed energy data: {energy_data}")
            return energy_data

        else:
            # Initialize the integral value for the first entry
            energy_data = {
                'Energy': {'value': 0.0, 'unit': 'kWh'},
                'Energy_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_consumed': {'value': 0.0, 'unit': 'kWh'},
                'Energy_daily_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_daily_consumed': {'value': 0.0, 'unit': 'kWh'},
                'Energy_weekly_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_weekly_consumed': {'value': 0.0, 'unit': 'kWh'},
                'Energy_monthly_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_monthly_consumed': {'value': 0.0, 'unit': 'kWh'},
            }
            logger.info("No previous data or 'P' variable found, initializing energy values to 0")
            return energy_data

    except Exception as e:
        logger.error(f"Error during computation: {e}", exc_info=True)
        energy_data = {
                'Energy': {'value': 0.0, 'unit': 'kWh'},
                'Energy_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_consumed': {'value': 0.0, 'unit': 'kWh'},
                'Energy_daily_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_daily_consumed': {'value': 0.0, 'unit': 'kWh'},
                'Energy_weekly_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_weekly_consumed': {'value': 0.0, 'unit': 'kWh'},
                'Energy_monthly_produced': {'value': 0.0, 'unit': 'kWh'},
                'Energy_monthly_consumed': {'value': 0.0, 'unit': 'kWh'},
            }
        return energy_data
        

"""
Save device data into the DeviceData model.
"""
def store_data_in_database(device, data):
    try:
        dev_data = DeviceData.objects.create(
            Gateway=device.Gateway,
            device_name=device,
            data=data
        )
        if hasattr(device, "user"):
            dev_data.user.set(device.user.all())
    except Exception as e:
        logger.info(f"Error while saving the data: {e}")