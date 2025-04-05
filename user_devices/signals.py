from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import Gateway, Device, DeviceData

@receiver(m2m_changed, sender=Gateway.user.through)
def sync_users_to_devices_and_data(sender, instance, action, **kwargs):
    if action in ['post_add', 'post_remove', 'post_clear']:
        users = instance.user.all()

        # Update Devices
        for device in instance.devices.all():
            device.user.set(users)

            # Update DeviceData for each Device
            for data in device.device_data.all():
                data.user.set(users)

