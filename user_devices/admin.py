from django.contrib import admin
from .models import DeviceData, Device

class DeviceDataAdmin(admin.ModelAdmin):
    list_display = ('device', 'timestamp', 'value')  # Display these fields in the list view
    list_filter = ('device__user', 'device')  # Filter by user and device
    ordering = ('device', 'timestamp')  # Order by device and timestamp

    def get_queryset(self, request):
        # Override to annotate with user for grouping
        queryset = super().get_queryset(request)
        return queryset.select_related('device__user')  # Optimize for related user access

admin.site.register(DeviceData, DeviceDataAdmin)
admin.site.register(Device)
admin.site.site_header = 'Site Administration'