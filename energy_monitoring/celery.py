import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "energy_monitoring.settings")
app = Celery("energy_monitoring")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.beat_schedule = {
    'check_devices_every_30_seconds': {
        'task': 'user_devices.tasks.check_all_devices',
        'schedule': 120,  # Run every 30 seconds
    },
}

app.autodiscover_tasks()