import logging
import time
import json
import requests
from sympy import sympify
from datetime import datetime, timezone, timedelta
from pymodbus.client import ModbusTcpClient
from .models import ModbusMappingVariable, ComputedVariable, DeviceData, EnergyData
from decimal import Decimal
from django.db.models import Sum
from django.db.models.expressions import RawSQL
from fractions import Fraction
from .helper_funcs import sanitize_variable_name, convert_value, convert_to_local_time

logger = logging.getLogger(__name__)

MAX_WORDS_PER_READ = 12
TIMEOUT = 5                 # Timeout per la connessione

"""
Reads DLMS registers for a given device.
"""
def read_dlms_values(device):

    mapped_values = {}
    gateway_ip = device.Gateway.ip_address
    gateway_port = device.port
    
    dlms_mappings = device.dlms_variables.all()

    ############################################################
    # MODIFICA TEMPORANEA PER LEGGERE DATI DAL CLIENTE ATTUALE #
    ############################################################
    for mapping in dlms_mappings:
        try:
            response = requests.get(f"http://{gateway_ip}:{gateway_port}/dlms/profile?obis_code={mapping.obis_code}&column={mapping.column_idx}")
            if response.ok:
                data = response.json()
                logger.info(data)

                reading = data['value']        
                last_reading_time = data['time_of_reading']

                # Store the value with the variable name as key
                converted_value = convert_value(reading, mapping.conversion_factor)

                sanitized_name = sanitize_variable_name(mapping.var_name)
                
                mapped_values[sanitized_name] = {
                    "value": converted_value,
                    "unit": mapping.unit,
                    "timestamp": last_reading_time
                }
                logger.info(f"Read DLMS value for {sanitized_name} (OBIS: {mapping.obis_code}): {converted_value} {mapping.unit}")
                logger.info(f"Mapped values: {mapped_values}")
            else:
                logger.error(f"Failed to get profile data: {response.status_code}")
                return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error while reading DLMS values: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in read_dlms_values: {e}")
            return None
          
    json_result = json.dumps(mapped_values, indent=4)
    logger.info(f"Mapped JSON: {json_result}")
    return mapped_values


"""
Reads Modbus registers for a given device.
Handles multiple reads if needed due to word limits.
"""
def read_modbus_registers(device, client):
    try:
        start_address = int(device.start_address, 16)
        logger.info(f"Start Address: {start_address}")
        bytes_count = device.bytes_count 
        logger.info(f"Bytes count: {bytes_count }")
        
        # Split reads into chunks of MAX_WORDS_PER_READ
        base_values = {}
        for offset in range(0, bytes_count, MAX_WORDS_PER_READ):
            current_address = start_address + offset
            logger.info(f"Start Address: {current_address}")
            words_to_read = min(MAX_WORDS_PER_READ, (bytes_count - offset) // 2)
            if hasattr(device, 'register_type') and device.register_type == 'holding':
                response = client.read_holding_registers(address=current_address, count=words_to_read, device_id=device.slave_id)
            else:
                response = client.read_input_registers(address=current_address, count=words_to_read, device_id=device.slave_id)
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
            converted_value = convert_value(raw_value, mapping.conversion_factor)

            # Salvo il valore nel dizionario
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
def compute_energy(variables, device_data, energy_data):
    logger.info("Starting to compute integral values")
    try:
        # Get the most recent data
        previous_data = device_data.order_by('-timestamp').first()

        # Define possible power variable names
        power_prod_variable_names = ['Pout', 'Power Production', 'Potenza in uscita']
        power_cons_variable_names = ['Pin', 'Power Consumption', 'Potenza in entrata']
        power_variable_names = ['P', 'Power', 'Potenza']

        power_name = None
        power_cons_variable_name = None
        power_prod_variable_name = None
        is_power_splitted = False

        # Check if the power variable name is configured (MODBUS VERSION)
        is_single_power_variable = False
        for name in power_variable_names:
            if name in variables:
                power_name = name
                is_single_power_variable = True
                break

        logger.info(f"is_single_power_variable: {is_single_power_variable}")
        if is_single_power_variable:
            logger.info(f"power_name: {power_name}")

        # Check if the power variable name is configured (DLMS VERSION - Two variables for power)
        if not is_single_power_variable:
            is_single_power_variable = False
            for name in power_prod_variable_names:
                if name in variables:
                    power_prod_variable_name = name
                    is_power_splitted = True
                    break
            
            logger.info(f"power_prod_variable_name: {power_prod_variable_name}")

            for name in power_cons_variable_names:
                if name in variables:
                    power_cons_variable_name = name
                    is_power_splitted = True
                    break

            logger.info(f"power_cons_variable_name: {power_cons_variable_name}")
            logger.info(f"is_power_splitted: {is_power_splitted}")
        # Compute energy for single power variable (DLMS VERSION)
        if previous_data and is_single_power_variable and not is_power_splitted:
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
            start_of_day_utc = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start_of_day_local = convert_to_local_time(start_of_day_utc)
            start_of_day_filter = start_of_day_local.astimezone(timezone.utc)
            
            # Daily energy
            daily_records = device_data.filter(timestamp__gte=start_of_day_filter)
            daily_produced = daily_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) < 0 THEN ABS(CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION)) ELSE 0 END", []))
            )['total'] or 0.0
            daily_consumed = daily_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) >= 0 THEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) ELSE 0 END", []))
            )['total'] or 0.0

            # Weekly energy
            start_of_week_utc = now.replace(hour=0, minute=0, second=0, microsecond=0).isocalendar().weekday(1)
            start_of_week_local = convert_to_local_time(start_of_week_utc)
            start_of_week_filter = start_of_week_local.astimezone(timezone.utc)
            weekly_records = device_data.filter(timestamp__gte=start_of_week_filter)
            weekly_produced = weekly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) < 0 THEN ABS(CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION)) ELSE 0 END", []))
            )['total'] or 0.0
            weekly_consumed = weekly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) >= 0 THEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) ELSE 0 END", []))
            )['total'] or 0.0

            # Monthly energy
            start_of_month_utc = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_of_month_local = convert_to_local_time(start_of_month_utc)
            start_of_month_filter = start_of_month_local.astimezone(timezone.utc)
            monthly_records = device_data.filter(timestamp__gte=start_of_month_filter)
            monthly_produced = monthly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) < 0 THEN ABS(CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION)) ELSE 0 END", []))
            )['total'] or 0.0
            monthly_consumed = monthly_records.aggregate(
                total=Sum(RawSQL("CASE WHEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) >= 0 THEN CAST(data->'"+power_name+"'->>'value' AS DOUBLE PRECISION) ELSE 0 END", []))
            )['total'] or 0.0

            # Apply time factor to get energy values (power × time)
            time_factor = delta_time  # This is approximate - ideally would sum actual time intervals

            # Store all computed values in a structured dictionary
            energy_data = {
                'Energy': {'value': energy_produced + energy_consumed, 'unit': 'kWh'},
                'Energy_produced': {'value': energy_produced, 'unit': 'kWh'},
                'Energy_consumed': {'value': energy_consumed, 'unit': 'kWh'},
                
                'Energy_daily_produced': {'value': daily_produced * time_factor, 'unit': 'kWh'},
                'Energy_daily_consumed': {'value': daily_consumed * time_factor, 'unit': 'kWh'},
                
                'Energy_weekly_produced': {'value': weekly_produced * time_factor, 'unit': 'kWh'},
                'Energy_weekly_consumed': {'value': weekly_consumed * time_factor, 'unit': 'kWh'},
                
                'Energy_monthly_produced': {'value': monthly_produced * time_factor, 'unit': 'kWh'},
                'Energy_monthly_consumed': {'value': monthly_consumed * time_factor, 'unit': 'kWh'},
            }


            logger.info(f"Computed energy data: {energy_data}")
            return energy_data
        
        # Compute energy for split power variables (DLMS VERSION)
        elif is_power_splitted and not is_single_power_variable and (power_prod_variable_name or power_cons_variable_name):
            
            logger.info(f"Computing the time intervals for the energy data")

            # Daily, weekly, monthly energy produced and consumed
            now = datetime.now(timezone.utc)

            # Start of UTC day
            start_of_day_utc = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
            # Convert to local (Django TZ)
            start_of_day_local = convert_to_local_time(start_of_day_utc)

            # For filtering DB (which expects UTC), convert back. Timestamps are utc in django
            start_of_day_filter = start_of_day_local.astimezone(timezone.utc)

            daily_records = energy_data.filter(timestamp__gte=start_of_day_filter)

            # Start of UTC week
            start_of_week_utc = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())

            # Convert to local (Django TZ)
            start_of_week_local = convert_to_local_time(start_of_week_utc)

            # For filtering DB (which expects UTC), convert back. Timestampas are utc in django
            start_of_week_filter = start_of_week_local.astimezone(timezone.utc)

            weekly_records = energy_data.filter(timestamp__gte=start_of_week_filter)

            # Start of UTC month
            start_of_month_utc = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            # Convert to local (Django TZ)
            start_of_month_local = convert_to_local_time(start_of_month_utc)

            # For filtering DB (which expects UTC), convert back. Timestampas are utc in django
            start_of_month_filter = start_of_month_local.astimezone(timezone.utc)
            monthly_records = energy_data.filter(timestamp__gte=start_of_month_filter)

            # Create a structured dictionary for the energy data
            energy_data = {}

            # Daily, weekly, monthly energy produced
            if power_prod_variable_name:

                logger.info(f"Computing energy for power produced: {power_prod_variable_name}")

                # Get the current value of power produced
                current_p_produced = variables.get(power_prod_variable_name, {}).get('value', 0)

                # Compute the energy increment for this period
                energy_produced_increment = current_p_produced / 4

                # Get the previous energy produced
                previous_energy_produced = previous_data.data.get('Energy_produced', {}).get('value', 0.0) if previous_data else 0.0

                # Update the energy produced
                energy_produced = previous_energy_produced + energy_produced_increment

                # Daily, weekly, monthly energy produced variables
                last_daily_record = daily_records.order_by('-timestamp').first()
                if last_daily_record and 'Energy_daily_produced' in last_daily_record.data:
                    daily_produced = last_daily_record.data['Energy_daily_produced'].get('value', 0.0)
                else:
                    daily_produced = 0.0
                daily_produced += energy_produced_increment

                last_weekly_record = weekly_records.order_by('-timestamp').first()
                if last_weekly_record and 'Energy_weekly_produced' in last_weekly_record.data:
                    weekly_produced = last_weekly_record.data['Energy_weekly_produced'].get('value', 0.0)
                else:
                    weekly_produced = 0.0
                weekly_produced += energy_produced_increment

                last_monthly_record = monthly_records.order_by('-timestamp').first()
                if last_monthly_record and 'Energy_monthly_produced' in last_monthly_record.data:
                    monthly_produced = last_monthly_record.data['Energy_monthly_produced'].get('value', 0.0)
                else:
                    monthly_produced = 0.0
                monthly_produced += energy_produced_increment

                # Add energy produced to the energy data dictionary
                energy_data['Energy_produced'] = {'value': energy_produced, 'unit': 'kWh'}
                energy_data['Energy_daily_produced'] = {'value': daily_produced, 'unit': 'kWh'}
                energy_data['Energy_weekly_produced'] = {'value': weekly_produced, 'unit': 'kWh'}
                energy_data['Energy_monthly_produced'] = {'value': monthly_produced, 'unit': 'kWh'}

            # Daily, weekly, monthly energy consumed
            if power_cons_variable_name:

                logger.info(f"Computing energy for power consumed: {power_cons_variable_name}")

                # Get the current value of power consumed
                current_p_consumed = variables.get(power_cons_variable_name, {}).get('value', 0)

                # Compute the energy increment for this period
                energy_consumed_increment = current_p_consumed / 4

                # Get the previous energy consumed
                previous_energy_consumed = previous_data.data.get('Energy_consumed', {}).get('value', 0.0) if previous_data else 0.0

                # Update the energy consumed
                energy_consumed = previous_energy_consumed + energy_consumed_increment

                # Daily, weekly, monthly energy consumed variables
                last_daily_record_cons = daily_records.order_by('-timestamp').first()
                if last_daily_record_cons and 'Energy_daily_consumed' in last_daily_record_cons.data:
                    daily_consumed = last_daily_record_cons.data['Energy_daily_consumed'].get('value', 0.0)
                else:
                    daily_consumed = 0.0
                daily_consumed += energy_consumed_increment

                last_weekly_record_cons = weekly_records.order_by('-timestamp').first()
                if last_weekly_record_cons and 'Energy_weekly_consumed' in last_weekly_record_cons.data:
                    weekly_consumed = last_weekly_record_cons.data['Energy_weekly_consumed'].get('value', 0.0)
                else:
                    weekly_consumed = 0.0
                weekly_consumed += energy_consumed_increment

                last_monthly_record_cons = monthly_records.order_by('-timestamp').first()
                if last_monthly_record_cons and 'Energy_monthly_consumed' in last_monthly_record_cons.data:
                    monthly_consumed = last_monthly_record_cons.data['Energy_monthly_consumed'].get('value', 0.0)
                else:
                    monthly_consumed = 0.0
                monthly_consumed += energy_consumed_increment

                # Add energy consumed to the energy data dictionary
                energy_data['Energy_consumed'] = {'value': energy_consumed, 'unit': 'kWh'}
                energy_data['Energy_daily_consumed'] = {'value': daily_consumed, 'unit': 'kWh'}
                energy_data['Energy_weekly_consumed'] = {'value': weekly_consumed, 'unit': 'kWh'}
                energy_data['Energy_monthly_consumed'] = {'value': monthly_consumed, 'unit': 'kWh'}

            logger.info(f"Computed energy data: {energy_data}")
            return energy_data

        else:   
            # If none of the above condition applies, the dict returned is empty.
            return None

    except Exception as e:
        logger.error(f"Error during computation: {e}", exc_info=True)
        return None
        

"""
Save device data into the DeviceData model.
"""
def store_data_in_database(device, data):     
    try:
        if is_device_data_already_stored(device, data):
            return
        dev_data = DeviceData.objects.create(
            Gateway=device.Gateway,
            device_name=device,
            data=data
        )
        if hasattr(device, "user"):
            dev_data.user.set(device.user.all())
        logger.info(f"Data saved for device {device.name}")
    except Exception as e:
        logger.info(f"Error while saving the data: {e}")


"""
Store Energy data into the Database
"""
def store_energy_data_in_database(device, data):
    try:
        if is_energy_data_already_stored(device, data):
            return
        energy_data = EnergyData.objects.create(
            Gateway=device.Gateway,
            device_name=device,
            data=data
        )
        if hasattr(device, "user"):
            energy_data.user.set(device.user.all())
        logger.info(f"Energy data saved for device {device.name}")
    except Exception as e:
        logger.info(f"Error while saving the energy data: {e}")

"""
Check if the device data is already stored in the Database
"""
def is_device_data_already_stored(device, data):
    try:
        if device.protocol == "dlms":
            latest_entry = DeviceData.objects.filter(
                device_name=device
            ).order_by('-timestamp').first()

            if latest_entry:
                existing_data = latest_entry.data
                for key in data:
                    if key in existing_data:
                        last_ts = existing_data[key].get("timestamp")
                        current_ts = data[key].get("timestamp")

                        if last_ts and current_ts:
                            last_time = datetime.fromisoformat(last_ts).replace(second=0, microsecond=0)
                            current_time = datetime.fromisoformat(current_ts).replace(second=0, microsecond=0) 

                            if last_time == current_time:
                                logger.info(f"Skipped {key}: already stored at {current_time}")
                                return True
        return False
    except Exception as e:
        logger.info(f"Error while checking the device data: {e}")
        return True

"""
Check if the energy data is already stored in the Database
"""
def is_energy_data_already_stored(device, data):
    try:
        if device.protocol == "dlms":
            latest_entry = EnergyData.objects.filter(
                device_name=device
            ).order_by('-timestamp').first()

            if latest_entry:
                existing_data = latest_entry.data
                for key in data:
                    if key in existing_data:
                        last_ts = existing_data[key].get("timestamp")
                        current_ts = data[key].get("timestamp")

                        if last_ts and current_ts:
                            last_time = datetime.fromisoformat(last_ts).replace(second=0, microsecond=0)
                            current_time = datetime.fromisoformat(current_ts).replace(second=0, microsecond=0) 

                            if last_time == current_time:
                                logger.info(f"Skipped {key}: already stored at {current_time}")
                                return True
        return False
    except Exception as e:
        logger.info(f"Error while checking the energy data: {e}")
        return True