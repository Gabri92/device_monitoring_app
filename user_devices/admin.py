from django.contrib import admin
from .models import User, Gateway, Device, DeviceVariable, ModbusMappingVariable, DlmsMappingVariable, ComputedVariable, Button, DeviceData
from .commands import set_pin_status
from django.utils.html import format_html
from django.urls import reverse
from adminsortable2.admin import  SortableAdminBase, SortableStackedInline
from .forms import DeviceForm

class GatewayAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'get_users')
    list_filter = ('user','ip_address')  # Filter by user and active status
    search_fields = ('user', 'ip_address')  # Search bar
    filter_horizontal = ('user',)

    def get_users(self, obj):
        return ", ".join([user.username for user in obj.user.all()])
    get_users.short_description = 'Users'
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        # Sync users to each device under the gateway
        for device in obj.devices.all():
            for user in obj.user.all():
                device.user.add(user)

                # Also sync users to device data
                for data in device.device_data.all():
                    data.user.add(user)

class MemoryMappingInlineModbus(SortableStackedInline, admin.StackedInline):
    model = ModbusMappingVariable
    extra = 0
    fields = ('var_name', 'address', 'unit', 'conversion_factor', 'bit_length', 'is_signed', 'show_on_graph') 
    sortable = 'order'
    classes = ['modbus-inline']
    

class MemoryMappingInlineDlms(SortableStackedInline, admin.StackedInline):
    model = DlmsMappingVariable
    extra = 0
    fields = ('var_name', 'obis_code', 'unit', 'conversion_factor', 'show_on_graph') 
    sortable = 'order'
    classes = ['dlms-inline']
    
    
class ComputedVariableInline(SortableStackedInline, admin.StackedInline):
    model = ComputedVariable
    extra = 0
    fields = ('var_name', 'unit', 'formula','show_on_graph')
    sortable = 'order'
    
class DeviceAdmin(SortableAdminBase, admin.ModelAdmin):
    form = DeviceForm
    list_display = ('name','is_enabled', 'get_users','Gateway__name', 'Gateway__ip_address', 'protocol')
    list_filter = ('user','Gateway', 'is_enabled')
    search_fields = ('user','Gateway')
    #inlines = [MemoryMappingInlineModbus, ComputedVariableInline]
    actions = ['reset_axis_assignments']
    readonly_fields = ('get_users',)
    exclude = ('user',)  # Hide the actual editable ManyToMany field
    fieldsets = (
        (None, {
            'fields': ( 'is_enabled', 'name', 'Gateway', 'protocol', 'slave_id','register_type', 'start_address', 'bytes_count', 'port')
        }),
        ('Energy Display Options', {
            'fields': ('show_energy','show_energy_daily', 'show_energy_weekly', 'show_energy_monthly'),
        }),
    )
    
    class Media:
        js = ('admin/js/device_admin.js',)
    
    def get_users(self, obj):
        return ", ".join([user.username for user in obj.user.all()])
    get_users.short_description = 'Users'
    
    def get_inline_instances(self, request, obj=None):
        return [
            MemoryMappingInlineModbus(self.model, self.admin_site),
            MemoryMappingInlineDlms(self.model, self.admin_site),
            ComputedVariableInline(self.model, self.admin_site),
        ]


    def reset_axis_assignments(self, request, queryset):
        queryset.update(is_x_axis=False, is_y_axis=False)
        self.message_user(request, "Axis assignments reset.")


class DeviceDataAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'timestamp','get_users', 'Gateway__ip_address')
    search_fields = ('user__username', 'Gateway__ip_address', 'name__device_name')
    list_filter = ('Gateway__ip_address', 'device_name', 'timestamp')
    readonly_fields = ('get_users', 'device_name', 'Gateway', 'timestamp','data')
    fieldsets = (
        (None, {'fields': ('get_users', 'Gateway', 'device_name', 'data')}),
        ('Timestamps', {'fields': ('timestamp',)}),
    )

    def get_users(self, obj):
        return ", ".join([user.username for user in obj.user.all()])
    get_users.short_description = 'Users'

class ButtonAdmin(admin.ModelAdmin):
    list_display = ('label','Gateway__name', 'Gateway__ip_address', 'pin_number', 'is_active', 'show_in_user_page', 'toggle_button_link')
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
admin.site.register(DeviceData, DeviceDataAdmin)    
admin.site.register(Button, ButtonAdmin)
admin.site.site_header = 'Site Administration'