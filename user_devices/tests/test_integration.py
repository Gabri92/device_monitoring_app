# user_devices/tests/test_integration.py
from django.test import TestCase, TransactionTestCase
from django.contrib.auth.models import User
from unittest.mock import patch, Mock
from user_devices.models import (
    Gateway, Device, DeviceData, MappingVariable, 
    ComputedVariable, Button
)
from user_devices.tasks import scan_and_read_devices, check_all_devices
from user_devices.functions import read_modbus_registers, map_variables, compute_variables
from datetime import datetime, timezone
import json

#TODO: Funzione scan_and_read_devices poco testabile
class DeviceDataFlowIntegrationTest(TransactionTestCase):
    """Tests the entire data flow from device reading to data storage"""
    
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        # Create test gateway
        self.gateway = Gateway.objects.create(
            name="Test Gateway",
            ssh_username="ssh_user",
            ssh_password="ssh_pass",
            ip_address="192.168.1.100"
        )
        self.gateway.user.add(self.user)
        
        # Create test device
        self.device = Device.objects.create(
            name="Test Device",
            Gateway=self.gateway,
            slave_id=1,
            start_address="0x0280",
            bytes_count=24,
            port=502
        )
        self.device.user.add(self.user)
        
        # Create mapping variables
        self.voltage_var = MappingVariable.objects.create(
            device=self.device,
            var_name="Voltage",
            address="0x0280",
            unit="V",
            conversion_factor="0.1"
        )
        
        self.current_var = MappingVariable.objects.create(
            device=self.device,
            var_name="Current",
            address="0x0282",
            unit="A",
            conversion_factor="0.01"
        )
        
        # Create computed variable
        self.power_var = ComputedVariable.objects.create(
            device=self.device,
            var_name="P",
            formula="Voltage * Current",
            unit="W"
        )

    @patch('pymodbus.client.ModbusTcpClient')
    @patch('redis.lock.Lock.acquire')
    @patch('redis.lock.Lock.release')
    def test_end_to_end_device_reading(self, mock_lock_release, mock_lock_acquire, mock_modbus_client):
        # Mock Redis lock
        mock_lock_acquire.return_value = True
        
        # Mock ModbusTcpClient
        mock_client = Mock()
        mock_client.connect.return_value = True
        
        # Mock successful register reading
        mock_response = Mock()
        mock_response.isError.return_value = False
        mock_response.registers = [1000, 200]  # Simple test values
        mock_client.read_input_registers.return_value = mock_response
        mock_modbus_client.return_value = mock_client
        
        # Run the task
        scan_and_read_devices(self.gateway.ip_address)
        
        # Check that data was stored
        self.assertTrue(DeviceData.objects.exists())
        data = DeviceData.objects.first().data
        
        # Check that key values exist
        self.assertIn('Voltage', data)
        self.assertIn('Current', data)
        self.assertIn('P', data)
        
        # Check user relationship was preserved
        device_data = DeviceData.objects.first()
        self.assertIn(self.user, device_data.user.all())

class UserPermissionPropagationTest(TestCase):
    """Tests the propagation of user permissions through models"""
    
    def setUp(self):
        # Create users
        self.user1 = User.objects.create_user(username='user1', password='pass1')
        self.user2 = User.objects.create_user(username='user2', password='pass2')
        
        # Create gateway with initial user
        self.gateway = Gateway.objects.create(
            name="Test Gateway",
            ip_address="192.168.1.100"
        )
        self.gateway.user.add(self.user1)
        
        # Create device
        self.device = Device.objects.create(
            name="Test Device",
            Gateway=self.gateway,
            slave_id=1,
            start_address="0x0280",
            bytes_count=10
        )
        
        # Create button
        self.button = Button.objects.create(
            Gateway=self.gateway,
            label="Test Button",
            pin_number=5
        )
        
        # Create sample data
        self.device_data = DeviceData.objects.create(
            Gateway=self.gateway,
            device_name=self.device,
            data={"test": {"value": 1, "unit": "X"}}
        )
    
    def test_user_propagation_on_addition(self):
        """Test that adding a user to a gateway propagates to devices and data"""
        # Initial check
        self.assertIn(self.user1, self.gateway.user.all())
        self.assertIn(self.user1, self.device.user.all())
        self.assertIn(self.user1, self.device_data.user.all())
        
        # Add another user to gateway
        self.gateway.user.add(self.user2)
        
        # Check user propagated to devices
        self.assertIn(self.user2, self.device.user.all())
        
        # Check user propagated to device data
        self.assertIn(self.user2, self.device_data.user.all())
    
    def test_user_propagation_on_removal(self):
        """Test that removing a user from a gateway propagates to devices and data"""
        # Setup: add second user
        self.gateway.user.add(self.user2)
        
        # Remove first user
        self.gateway.user.remove(self.user1)
        
        # Check user removed from devices
        self.assertNotIn(self.user1, self.device.user.all())
        
        # Check user removed from device data
        self.assertNotIn(self.user1, self.device_data.user.all())
        
        # Check second user still present
        self.assertIn(self.user2, self.device.user.all())
        self.assertIn(self.user2, self.device_data.user.all())

class TaskExecutionTest(TransactionTestCase):
    """Tests the Celery tasks execution"""
    
    def setUp(self):
        # Create test gateway
        self.gateway = Gateway.objects.create(
            name="Test Gateway",
            ip_address="192.168.1.100"
        )
    
    @patch('user_devices.tasks.scan_and_read_devices')
    @patch('user_devices.tasks.group')
    def test_check_all_devices_task(self, mock_group, mock_scan_task):
        """Test that check_all_devices creates tasks for all gateways"""
        # Mock the group execution
        mock_job = Mock()
        mock_group.return_value = mock_job
        
        # Create additional gateway
        Gateway.objects.create(
            name="Second Gateway",
            ip_address="192.168.1.101"
        )
        
        # Run the task
        check_all_devices()
        
        # Verify task group creation
        mock_group.assert_called_once()
        
        # Check both gateways are included
        call_args = mock_group.call_args[0][0]
        self.assertEqual(len(call_args), 2)  # Should have 2 tasks
        
        # Verify job was applied
        mock_job.apply_async.assert_called_once()