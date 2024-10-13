from django.db import models
from django.contrib.auth.models import User

# Il device ha anche un ip associato
class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField(protocol="ipv4")
    port = models.IntegerField(default=502)
    mac_address = models.CharField(max_length=50, unique=True)
    last_seen = models.DateTimeField(null=True, blank=True)  # Keeps track of when the device last responded
    is_active = models.BooleanField(default=True)  # Marks if the device is currently responsive

    def __str__(self):
        return self.name
    
class DeviceData(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='data_records')
    value = models.JSONField()
    timestamp = models.DateTimeField(auto_now_add=True)