from django.contrib import admin
from .models import User,DeviceData, Device, ModbusAddress, Button
from .commands import set_pin_status

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

class ButtonAdmin(admin.ModelAdmin):
    list_display = ('label', 'device', 'pin_number', 'is_active', 'show_in_user_page')
    list_filter = ('device', 'show_in_user_page')
    actions = ['toggle_button']

admin.site.register(DeviceData, DeviceDataAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(ModbusAddress, ModbusAddressAdmin)
admin.site.register(Button, ButtonAdmin)
admin.site.site_header = 'Site Administration'

def toggle_button(self, request, queryset):
    """
    Custom admin action to toggle button status.
    """
    for button in queryset:
        status = "on" if not button.is_active else "off"
        success, response = set_pin_status(
            device=button.device,
            pin=button.pin_number,
            status=status
        )
        if success:
            button.is_active = not button.is_active
            button.save()
    self.message_user(request, "Selected buttons toggled successfully.")
toggle_button.short_description = "Toggle Selected Buttons"