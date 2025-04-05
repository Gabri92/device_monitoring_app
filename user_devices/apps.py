from django.apps import AppConfig

class UserDevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_devices'

    def ready(self):
        import user_devices.signals  # 👈 import to connect signals