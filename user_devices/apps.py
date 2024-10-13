from django.apps import AppConfig

class UserDevicesConfig(AppConfig):
    name = 'user_devices'

    def ready(self):
        from user_devices.tasks import check_all_devices
        check_all_devices.delay()  # Call the task to check all devices immediately on startup
