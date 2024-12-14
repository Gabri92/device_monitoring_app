from django.db import models
from django.contrib.auth.models import User

# Il device ha anche un ip associato
class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=100, default="unknown", unique=True)
    ssh_username = models.CharField(max_length=50, default='ssh_user')  # SSH username
    ssh_password = models.CharField(max_length=100, default='ssh_psw')  # SSH password
    ip_address = models.CharField(max_length=50)
    port = models.IntegerField(default=502)
    mac_address = models.CharField(max_length=50, unique=True)
    last_seen = models.DateTimeField(null=True, blank=True)  # Keeps track of when the device last responded
    is_active = models.BooleanField(default=False)  # Marks if the device is currently responsive
    last_records = models.IntegerField(default=10)  # Custom number of data records to display

    def __str__(self):
        return f"Device Name: {self.name}, Mac: {self.mac_address}"
    
class DeviceData(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='data_records')
    value = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

class ModbusAddress(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='modbus_addresses')
    address = models.IntegerField(default=0)
    count = models.IntegerField(default=1)
    description = models.CharField(max_length=100, blank=True, null=True)  # Optional field for description

    def __str__(self):
        return f"{self.description} - Address: {self.address}"
    
class Button(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='buttons')
    label = models.CharField(max_length=100)  # Button name
    pin_number = models.IntegerField()  # GPIO pin number
    is_active = models.BooleanField(default=False)  # Current pin status
    show_in_user_page = models.BooleanField(default=False)  # Show this button to users

    def __str__(self):
        return f"{self.label} ({self.device.name})"