from django.contrib import admin
from .models import User,DeviceData, Device, ModbusAddress

class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'ip_address', 'mac_address', 'is_active')
    list_filter = ('user', 'is_active')  # Filter by user and active status
    search_fields = ('name', 'ip_address', 'mac_address')  # Search bar

class DeviceDataAdmin(admin.ModelAdmin):
    list_display = ('device', 'timestamp', 'value')  # Display these fields in the list view
    list_filter = ('device__user', 'device')  # Filter by user and device
    ordering = ('device', 'timestamp')  # Order by device and timestamp

class ModbusAddressAdmin(admin.ModelAdmin):
    list_display = ('device','address','description')
    list_filter = ('device__user', 'device')  # Filter by user (through device) and device
    search_fields = ('device__name', 'address')  # search  device  

admin.site.register(DeviceData, DeviceDataAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(ModbusAddress, ModbusAddressAdmin)
admin.site.site_header = 'Site Administration'