from django.contrib import admin
from .models import User,DeviceData, Device, ModbusAddress, Button
from .commands import set_pin_status
from django.utils.html import format_html
from django.urls import reverse

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
    list_display = ('label', 'device', 'pin_number', 'is_active', 'show_in_user_page', 'toggle_button_link')
    list_filter = ('device', 'show_in_user_page')

    def toggle_button_link(self, obj):
        """
        Display a custom toggle button in the admin interface.
        """
        url = reverse('admin:toggle_button_action', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Toggle</a>',
            url
        )

    toggle_button_link.short_description = "Toggle Button"
    toggle_button_link.allow_tags = True

    def get_urls(self):
        """
        Add a custom URL for the toggle button action.
        """
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pk>/toggle/',
                self.admin_site.admin_view(self.toggle_button_action),
                name='toggle_button_action',
            ),
        ]
        return custom_urls + urls

    def toggle_button_action(self, request, pk):
        """
        Handle the toggle button action.
        """
        button = Button.objects.get(pk=pk)
        status = 'on' if not button.is_active else 'off'

        # Call the SSH function
        success, response = set_pin_status(
            device=button.device,
            pin=button.pin_number,
            status=status
        )

        if success:
            button.is_active = not button.is_active
            button.save()
            self.message_user(request, f"Button '{button.label}' toggled successfully.")
        else:
            self.message_user(request, f"Failed to toggle button '{button.label}': {response}", level="error")

        # Redirect back to the button list
        from django.shortcuts import redirect
        return redirect('admin:user_devices_button_changelist')
    
admin.site.register(DeviceData, DeviceDataAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(ModbusAddress, ModbusAddressAdmin)
admin.site.register(Button, ButtonAdmin)
admin.site.site_header = 'Site Administration'
