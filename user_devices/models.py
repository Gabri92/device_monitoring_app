from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

# Il device ha anche un ip associato
class Gateway(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_gateway')
    ssh_username = models.CharField(max_length=50, default='ssh_user')  # SSH username
    ssh_password = models.CharField(max_length=100, default='ssh_psw')  # SSH password
    ip_address = models.CharField(max_length=50)
    port = models.IntegerField(default=502)

    def __str__(self):
        return f"Device user: {self.user}, Ip address: {self.ip_address}"

class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_device')
    Gateway = models.ForeignKey(Gateway, null=True, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=100, unique=True)
    slave_id = models.IntegerField(default=-1, unique=True, help_text="Slave ID of the device(nr between 1 to 247)")
    start_address = models.CharField(help_text="Starting Modbus address in hexadecimal (e.g., 0x0280)")
    bytes_count = models.PositiveIntegerField(default=1, help_text="Total number of consecutive bytes to read")

    def __str__(self):
        return f"{self.name}"

class DeviceVariable(models.Model):
    VARIABLE_TYPE_CHOICES = [
        ('memory', 'Memory Mapping'),
        ('computed', 'Computed Variable'),
    ]
    variable_type = models.CharField(
        max_length=10,
        choices=VARIABLE_TYPE_CHOICES,
        default='memory',
        help_text="Choose the type of variable to configure (Memory Mapping or Computed Variable)"
    )
    var_name = models.CharField(max_length=100, help_text="Name of the variable (e.g., Voltage, Power)")
    unit = models.CharField(max_length=20, help_text="Measurement unit (e.g., V, A, W)")
    show_on_graph = models.BooleanField(default=False, help_text="Show this variable on the graph")

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # If this variable is selected as X-axis, deselect others as X-axis
        if self.show_on_graph:
            ComputedVariable.objects.filter(show_on_graph=True).exclude(pk=self.pk).update(show_on_graph=False)
            MappingVariable.objects.filter(show_on_graph=True).exclude(pk=self.pk).update(show_on_graph=False)

        super().save(*args, **kwargs)

class MappingVariable(DeviceVariable):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="mapped_variables")
    address = models.CharField(default="",help_text="Address of the mapped value")
    unit = models.CharField(max_length=20, help_text="Measurement unit (e.g., V, A, Hz)")
    conversion_factor = models.FloatField(default=1.0, help_text="Factor to convert raw data to physical value")

    def __str__(self):
        return f"{self.var_name}"
    
class ComputedVariable(DeviceVariable):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="computed_variables")
    formula = models.TextField(
        help_text="Formula to calculate the value (e.g., 'voltage * current'). Variables must match existing MemoryMapping variable names"
    )
    unit = models.CharField(max_length=20, help_text="Measurement unit (e.g., W, kW, etc.)")

    def __str__(self):
        return f"{self.var_name} (Computed)"

class DeviceData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_device_data')
    gateway = models.ForeignKey(Gateway, on_delete=models.CASCADE, related_name='gateway_data')
    device_name = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='device_data')
    data = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device_name} - {self.timestamp}"

class Button(models.Model):
    Gateway = models.ForeignKey(Gateway, null=True, on_delete=models.CASCADE, related_name='buttons')
    label = models.CharField(max_length=100)  # Button name
    pin_number = models.IntegerField()  # GPIO pin number
    is_active = models.BooleanField(default=False)  # Current pin status
    show_in_user_page = models.BooleanField(default=False)  # Show this button to users

    def __str__(self):
        return f"{self.Gateway.user} ({self.Gateway})"