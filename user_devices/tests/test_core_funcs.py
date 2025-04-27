# user_devices/tests/test_functions.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fractions import Fraction
from pymodbus.client import ModbusTcpClient
from django.test import TestCase
from user_devices.models import Device, MappingVariable, ComputedVariable, DeviceData, Gateway
from user_devices.functions import (
    sanitize_variable_name, 
    read_modbus_registers, 
    map_variables, 
    compute_variables,
    compute_energy, 
    store_data_in_database
)

class TestSanitizeVariableName(TestCase):
    def test_sanitize_variable_name(self):
        """Test that variable names are properly sanitized"""
        test_cases = [
            ("test-variable", "test_variable"),
            ("test variable", "test_variable"),
            ("test-variable with space", "test_variable_with_space"),
            ("normal_name", "normal_name")
        ]
        
        for input_name, expected_output in test_cases:
            self.assertEqual(sanitize_variable_name(input_name), expected_output)

class TestReadModbusRegisters(TestCase):
    @patch('user_devices.functions.logger')
    def test_read_modbus_registers_success(self, mock_logger):
        """Test successful reading of modbus registers"""
        # Setup mock device and client
        device = Mock()
        device.name = "Test Device"
        device.start_address = "0x0280"  # Hex address
        device.bytes_count = 6  # 3 words
        device.slave_id = 1
        
        client = Mock()
        # Mock successful response
        response = Mock()
        response.isError.return_value = False
        response.registers = [100, 200, 300]  # Sample register values
        client.read_input_registers.return_value = response
        
        # Execute function
        result = read_modbus_registers(device, client)
        
        # Verify correct address calculations and returned data
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 3)  # Should have 3 values from our mock
        self.assertEqual(result[640], 100)  # 0x0280 = 640 decimal
        self.assertEqual(result[642], 200)
        self.assertEqual(result[644], 300)
        
        # Verify client was called with correct parameters
        client.read_input_registers.assert_called_with(
            address=640, count=3, slave=1
        )

    @patch('user_devices.functions.logger')
    def test_read_modbus_registers_error(self, mock_logger):
        """Test handling of errors during modbus register reading"""
        # Setup mock device and client
        device = Mock()
        device.name = "Test Device"
        device.start_address = "0x0280"
        device.bytes_count = 4
        device.slave_id = 1
        
        client = Mock()
        # Mock error response
        response = Mock()
        response.isError.return_value = True
        client.read_input_registers.return_value = response
        
        # Execute function
        result = read_modbus_registers(device, client)
        
        # Verify empty result due to error
        self.assertEqual(result, {})
        
        # Verify error was logged
        mock_logger.info.assert_any_call(f"Error reading address 640 for device Test Device")

    @patch('user_devices.functions.logger')
    def test_read_modbus_registers_exception(self, mock_logger):
        """Test handling of exceptions during modbus register reading"""
        # Setup mock device and client
        device = Mock()
        device.name = "Test Device"
        device.start_address = "0x0280"
        device.bytes_count = 4
        device.slave_id = 1
        
        client = Mock()
        # Force exception when calling read_input_registers
        client.read_input_registers.side_effect = Exception("Test exception")
        
        # Execute function
        result = read_modbus_registers(device, client)
        
        # Verify function returns None on exception
        self.assertIsNone(result)
        
        # Verify exception was logged
        mock_logger.info.assert_called_with("Modbus error on device Test Device: Test exception")

class TestMapVariables(TestCase):
    @patch('user_devices.functions.logger')
    @patch('user_devices.functions.MappingVariable.objects.filter')
    def test_map_variables_success(self, mock_filter, mock_logger):
        """Test successful mapping of variables from raw values"""
        # Setup mock device and base values
        device = Mock()
        device.name = "Test Device"
        
        base_values = {
            0x0280: 100,  # Voltage raw value
            0x0282: 200,  # Current raw value
        }
        
        # Setup mock mappings
        voltage_mapping = Mock()
        voltage_mapping.var_name = "Voltage"
        voltage_mapping.address = "0x0280"
        voltage_mapping.conversion_factor = "0.1"
        voltage_mapping.unit = "V"
        
        current_mapping = Mock()
        current_mapping.var_name = "Current"
        current_mapping.address = "0x0282"
        current_mapping.conversion_factor = "0.01"
        current_mapping.unit = "A"
        
        # Configure the mock filter to return our mock mappings
        mock_filter.return_value = [voltage_mapping, current_mapping]
        
        # Execute function
        result = map_variables(base_values, device)
        
        # Verify correct mapping of values
        self.assertEqual(result["Voltage"]["value"], 10.0)  # 100 * 0.1
        self.assertEqual(result["Voltage"]["unit"], "V")
        self.assertEqual(result["Current"]["value"], 2.0)  # 200 * 0.01
        self.assertEqual(result["Current"]["unit"], "A")

    @patch('user_devices.functions.logger')
    @patch('user_devices.functions.MappingVariable.objects.filter')
    def test_map_variables_fraction_conversion(self, mock_filter, mock_logger):
        """Test mapping with fractional conversion factors"""
        device = Mock()
        device.name = "Test Device"
        
        base_values = {0x0284: 300}
        
        # Test with fractional conversion factor
        power_mapping = Mock()
        power_mapping.var_name = "Power"
        power_mapping.address = "0x0284"
        power_mapping.conversion_factor = "1/10"
        power_mapping.unit = "kW"
        
        mock_filter.return_value = [power_mapping]
        
        result = map_variables(base_values, device)
        
        # 300 * (1/10) = 30.0
        self.assertEqual(result["Power"]["value"], 30.0)
        self.assertEqual(result["Power"]["unit"], "kW")

    @patch('user_devices.functions.logger')
    @patch('user_devices.functions.MappingVariable.objects.filter')
    def test_map_variables_error_handling(self, mock_filter, mock_logger):
        """Test error handling during variable mapping"""
        device = Mock()
        device.name = "Test Device"
        
        base_values = {0x0280: 100}
        
        # Setup mapping with invalid conversion factor
        invalid_mapping = Mock()
        invalid_mapping.var_name = "Invalid"
        invalid_mapping.address = "0x0280"
        invalid_mapping.conversion_factor = "invalid"
        invalid_mapping.unit = "X"
        
        # Setup mapping with missing address
        missing_mapping = Mock()
        missing_mapping.var_name = "Missing"
        missing_mapping.address = "0x0290"  # Not in base_values
        missing_mapping.conversion_factor = "0.1"
        missing_mapping.unit = "Y"
        
        mock_filter.return_value = [invalid_mapping, missing_mapping]
        
        result = map_variables(base_values, device)
        
        # For invalid conversion factor, should default to 0
        self.assertEqual(result["Invalid"]["value"], 0)
        self.assertEqual(result["Invalid"]["unit"], "X")
        
        # For missing address, should default to 0
        self.assertEqual(result["Missing"]["value"], 0)
        self.assertEqual(result["Missing"]["unit"], "Y")

class TestComputeVariables(TestCase):
    @patch('user_devices.functions.sympify')
    @patch('user_devices.functions.ComputedVariable.objects.filter')
    def test_compute_variables_success(self, mock_filter, mock_sympify):
        """Test successful computation of derived variables"""
        # Setup mapped values
        mapped_values = {
            "Voltage": {"value": 230.0, "unit": "V"},
            "Current": {"value": 2.0, "unit": "A"}
        }

        # Setup mock for sympify result
        mock_expr = Mock()
        mock_expr.evalf.return_value = 460.0
        mock_sympify.return_value = mock_expr

        # Setup mock for ComputedVariable
        power_var = Mock()
        power_var.var_name = "Power"
        power_var.formula = "Voltage * Current"
        power_var.unit = "W"

        # Use the queryset mock for the filtering
        mock_queryset = Mock()
        mock_queryset.__iter__ = Mock(return_value=iter([power_var]))
        mock_queryset.values.return_value = [{'var_name': 'Power', 'formula': 'Voltage * Current', 'unit': 'W'}]
        mock_filter.return_value = mock_queryset

        # Execute function
        result = compute_variables(mapped_values, Mock())

        # Verify results
        self.assertEqual(result["Power"]["value"], 460.0)
        self.assertEqual(result["Power"]["unit"], "W")

    @patch('user_devices.functions.logger')
    @patch('user_devices.functions.ComputedVariable.objects.filter')
    def test_compute_variables_error_handling(self, mock_filter, mock_logger):
        """Test error handling during variable computation"""
        device = Mock()
        device.name = "Test Device"
        
        mapped_values = {
            "Voltage": {"value": 230.0, "unit": "V"}
        }
        
        # Formula references a variable not in mapped_values
        invalid_var = Mock()
        invalid_var.var_name = "InvalidPower"
        invalid_var.formula = "Voltage * MissingCurrent"
        invalid_var.unit = "W"
        
        # Use the queryset mock for the filtering
        mock_queryset = Mock()
        mock_queryset.__iter__ = Mock(return_value=iter([invalid_var]))
        mock_queryset.values.return_value = [{'var_name': 'Power', 'formula': 'Voltage * Current', 'unit': 'W'}]
        mock_filter.return_value = mock_queryset
        try:
            result = compute_variables(mapped_values, device)
        except Exception as e:
            print(e)
        print(f"Result: {result}")
        # Should default to 0 when computation fails
        self.assertEqual(result["InvalidPower"]["value"], 0)
        self.assertEqual(result["InvalidPower"]["unit"], "W")

class TestComputeEnergy(TestCase):
    @patch('user_devices.functions.logger')
    def test_compute_energy_with_previous_data(self, mock_logger):
        """Test energy computation with previous data available"""
        # Setup device data queryset
        device_data = Mock()
        
        # Mock previous data
        previous_data = Mock()
        previous_data.timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        previous_data.data = {
            'P': {'value': 1000.0, 'unit': 'W'},
            'Energy': {'value': 5000.0, 'unit': 'J'},
            'Energy_produced': {'value': 1000.0, 'unit': 'J'},
            'Energy_consumed': {'value': 6000.0, 'unit': 'J'}
        }
        
        # Mock queryset methods
        device_data.order_by.return_value.first.return_value = previous_data
        
        # Setup filter and aggregate mocks for period data
        mock_daily_filter = Mock()
        mock_daily_filter.aggregate.return_value = {'total': 2000.0}
        
        mock_weekly_filter = Mock()
        mock_weekly_filter.aggregate.return_value = {'total': 5000.0}
        
        mock_monthly_filter = Mock()
        mock_monthly_filter.aggregate.return_value = {'total': 10000.0}
        
        # Return different mocks for different filter calls
        def side_effect_filter(timestamp__gte):
            if timestamp__gte > (datetime.now(timezone.utc) - timedelta(days=2)):
                return mock_daily_filter
            elif timestamp__gte > (datetime.now(timezone.utc) - timedelta(days=8)):
                return mock_weekly_filter
            else:
                return mock_monthly_filter
                
        device_data.filter.side_effect = side_effect_filter
        
        # Current values with positive power (consumption)
        variables = {
            'P': {'value': 2000.0, 'unit': 'W'}
        }
        
        # Execute function
        result = compute_energy(variables, device_data)

        print(f"Result: {result}")

        # Verify results
        # Check that all expected keys exist
        self.assertIn('Energy', result)
        self.assertIn('Energy_produced', result)
        self.assertIn('Energy_consumed', result)
        self.assertIn('Energy_daily_produced', result)
        self.assertIn('Energy_daily_consumed', result)
        self.assertIn('Energy_weekly_produced', result)
        self.assertIn('Energy_weekly_consumed', result)
        self.assertIn('Energy_monthly_produced', result)
        self.assertIn('Energy_monthly_consumed', result)
        
        # Check units
        self.assertEqual(result['Energy']['unit'], 'kWh')
        self.assertEqual(result['Energy_produced']['unit'], 'kWh')
        
        # Check that conversion factor to kWh was applied
        conv_factor_to_kwh = 3.6 * 10**6
        
        # Since we're using positive power (2000W), energy consumed should increase
        self.assertTrue(result['Energy_consumed']['value'] > previous_data.data['Energy_consumed']['value'] / conv_factor_to_kwh)
        
        # Energy produced should remain the same
        self.assertAlmostEqual(result['Energy_produced']['value'], 
        previous_data.data['Energy_produced']['value'] / conv_factor_to_kwh)

    @patch('user_devices.functions.logger')
    def test_compute_energy_with_negative_power(self, mock_logger):
        """Test energy computation with negative power (production)"""
        # Setup device data queryset
        device_data = Mock()
        
        # Mock previous data
        previous_data = Mock()
        previous_data.timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        previous_data.data = {
            'P': {'value': -500.0, 'unit': 'W'},  # Negative power
            'Energy': {'value': 5000.0, 'unit': 'J'},
            'Energy_produced': {'value': 3000.0, 'unit': 'J'},
            'Energy_consumed': {'value': 2000.0, 'unit': 'J'}
        }
        
        # Mock queryset methods
        device_data.order_by.return_value.first.return_value = previous_data
        
        # Setup filter and aggregate mocks
        mock_filter = Mock()
        mock_filter.aggregate.return_value = {'total': 1000.0}
        device_data.filter.return_value = mock_filter
        
        # Current values with negative power (production)
        variables = {
            'P': {'value': -1000.0, 'unit': 'W'}
        }
        
        # Execute function
        result = compute_energy(variables, device_data)
        
        # Verify results
        # Since we're using negative power (-1000W), energy produced should increase
        conv_factor_to_kwh = 3.6 * 10**6
        self.assertTrue(result['Energy_produced']['value'] > previous_data.data['Energy_produced']['value'] / conv_factor_to_kwh)
        
        # Energy consumed should remain the same
        self.assertAlmostEqual(result['Energy_consumed']['value'], 
                              previous_data.data['Energy_consumed']['value'] / conv_factor_to_kwh)

    @patch('user_devices.functions.logger')
    def test_compute_energy_with_alternative_power_name(self, mock_logger):
        """Test energy computation with alternative power variable name"""
        # Setup device data queryset
        device_data = Mock()
        
        # Mock previous data with "Power" instead of "P"
        previous_data = Mock()
        previous_data.timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        previous_data.data = {
            'Power': {'value': 1000.0, 'unit': 'W'},
            'Energy': {'value': 5000.0, 'unit': 'J'},
            'Energy_produced': {'value': 1000.0, 'unit': 'J'},
            'Energy_consumed': {'value': 6000.0, 'unit': 'J'}
        }
        
        # Mock queryset methods
        device_data.order_by.return_value.first.return_value = previous_data
        
        # Setup filter and aggregate mocks
        mock_filter = Mock()
        mock_filter.aggregate.return_value = {'total': 1000.0}
        device_data.filter.return_value = mock_filter
        
        # Current values with "Power" instead of "P"
        variables = {
            'Power': {'value': 2000.0, 'unit': 'W'}
        }
        
        # Execute function
        result = compute_energy(variables, device_data)
        
        # Verify results - function should recognize "Power" as a valid power variable name
        self.assertIn('Energy', result)
        self.assertIn('Energy_produced', result)
        self.assertIn('Energy_consumed', result)

    @patch('user_devices.functions.logger')
    def test_compute_energy_without_previous_data(self, mock_logger):
        """Test energy computation without previous data"""
        # Mock empty device data
        device_data = Mock()
        device_data.order_by.return_value.first.return_value = None
        
        variables = {'P': {'value': 1000.0, 'unit': 'W'}}
        
        result = compute_energy(variables, device_data)
        
        # Should initialize with zeros
        self.assertEqual(result['Energy']['value'], 0.0)
        self.assertEqual(result['Energy_produced']['value'], 0.0)
        self.assertEqual(result['Energy_consumed']['value'], 0.0)
        self.assertEqual(result['Energy_daily_produced']['value'], 0.0)
        self.assertEqual(result['Energy_daily_consumed']['value'], 0.0)
        self.assertEqual(result['Energy_weekly_produced']['value'], 0.0)
        self.assertEqual(result['Energy_weekly_consumed']['value'], 0.0)
        self.assertEqual(result['Energy_monthly_produced']['value'], 0.0)
        self.assertEqual(result['Energy_monthly_consumed']['value'], 0.0)

    @patch('user_devices.functions.logger')
    def test_compute_energy_exception_handling(self, mock_logger):
        """Test exception handling during energy computation"""
        # Mock device data that raises exception
        device_data = Mock()
        device_data.order_by.side_effect = Exception("Test exception")
        
        variables = {'P': {'value': 1000.0, 'unit': 'W'}}
        
        result = compute_energy(variables, device_data)
        
        # Should return default values on exception
        # Should initialize with zeros
        self.assertEqual(result['Energy']['value'], 0.0)
        self.assertEqual(result['Energy_produced']['value'], 0.0)
        self.assertEqual(result['Energy_consumed']['value'], 0.0)
        self.assertEqual(result['Energy_daily_produced']['value'], 0.0)
        self.assertEqual(result['Energy_daily_consumed']['value'], 0.0)
        self.assertEqual(result['Energy_weekly_produced']['value'], 0.0)
        self.assertEqual(result['Energy_weekly_consumed']['value'], 0.0)
        self.assertEqual(result['Energy_monthly_produced']['value'], 0.0)
        self.assertEqual(result['Energy_monthly_consumed']['value'], 0.0)
        mock_logger.error.assert_called()

# TODO: Test Commands e Tasks