from django import forms
from .models import Device

class DeviceForm(forms.ModelForm):
    class Meta:
        model = Device
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        protocol = cleaned_data.get('protocol')
        
        modbus_fields = ['slave_id', 'register_type', 'start_address', 'bytes_count', 'port']

        if protocol == 'dlms':
            # Optional: remove validation errors for modbus fields
            for field in modbus_fields:
                self._errors.pop(field, None)
                cleaned_data[field] = None  # or a default like 0 or ''

        elif protocol == 'modbus':
            # Optionally: enforce required if not already done in model
            for field in modbus_fields:
                value = cleaned_data.get(field)
                if not value:
                    self.add_error(field, f"{field.replace('_', ' ').capitalize()} is required for Modbus.")

        return cleaned_data

    def save_model(self, request, obj, form, change):
        protocol = obj.protocol

        # Reset dei campi modbus se protocollo DLMS (già implementato da te)
        if protocol == 'dlms':
            obj.slave_id = None
            obj.register_type = None
            obj.start_address = None
            obj.bytes_count = None
            obj.port = None

        super().save_model(request, obj, form, change)

        