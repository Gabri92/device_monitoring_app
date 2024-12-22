from django.contrib import admin
from .models import User, Gateway, Device, DeviceVariable, MappingVariable, ComputedVariable, Button, DeviceData
from .commands import set_pin_status
from django.utils.html import format_html
from django.urls import reverse

class GatewayAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'user')
    list_filter = ('user','ip_address')  # Filter by user and active status
    search_fields = ('user', 'ip_address')  # Search bar

class MemoryMappingInline(admin.StackedInline):
    model = MappingVariable
    extra = 0
    fields = ('var_name', 'address', 'unit', 'conversion_factor')

class ComputedVariableInline(admin.StackedInline):
    model = ComputedVariable
    extra = 0
    fields = ('var_name', 'unit', 'formula')

class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name','user','Gateway','slave_id','start_address','bytes_count')
    list_filter = ('user','Gateway')
    search_fields = ('user','Gateway')
    inlines = [MemoryMappingInline, ComputedVariableInline]

    def get_inlines(self, request, obj=None):
        """
        Dynamically show the correct inline based on the variable_type selected
        """
        if obj:
            if hasattr(obj, 'variables'):
                variable_type = obj.variables.all()[0].variable_type if obj.variables.exists() else None
                if variable_type == "memory":
                    return [MemoryMappingInline]
                elif variable_type == "computed":
                    return [ComputedVariableInline]
        return super().get_inlines(request, obj)

@admin.register(DeviceData)
class DeviceDataAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'timestamp','user', 'gateway')
    search_fields = ('user__username', 'gateway__ip_address', 'name__device_name')
    list_filter = ('gateway', 'device_name', 'timestamp')
    readonly_fields = ('user', 'device_name', 'gateway', 'timestamp','data')
    fieldsets = (
        (None, {'fields': ('user', 'gateway', 'device_name', 'data')}),
        ('Timestamps', {'fields': ('timestamp',)}),
    )

class ButtonAdmin(admin.ModelAdmin):
    list_display = ('label', 'Gateway', 'pin_number', 'is_active', 'show_in_user_page', 'toggle_button_link')
    list_filter = ('Gateway', 'show_in_user_page')
    
    def get_readonly_fields(self, request, obj=None):
        # Make 'is_active' readonly
        readonly_fields = super().get_readonly_fields(request, obj)
        return readonly_fields + ("is_active",)

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
            device=button.Gateway,
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
    
admin.site.register(Gateway, GatewayAdmin)
admin.site.register(Device, DeviceAdmin)
admin.site.register(Button, ButtonAdmin)
admin.site.site_header = 'Site Administration'
