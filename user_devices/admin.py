from django.contrib import admin

from .models import User, Device, DeviceData

admin.site.register(Device)
admin.site.register(DeviceData)