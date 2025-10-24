import os
from celery import Celery
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "energy_monitoring.settings")
app = Celery("energy_monitoring")
app.config_from_object("django.conf:settings", namespace="CELERY")

app.conf.beat_schedule = {
    'check_devices': {
        'task': 'user_devices.tasks.check_all_devices',
        'schedule': settings.CELERY_BEAT_SCHEDULE_INTERVAL, 
    },
    'compute_plant_metrics': {
        'task': 'user_devices.tasks.compute_plant_metrics',
        'schedule': settings.CELERY_BEAT_SCHEDULE_INTERVAL,  
    },
    'midnight_energy_aggregation': {
        'task': 'user_devices.tasks.midnight_energy_aggregation',
        'schedule': {'hour': 0, 'minute': 0},  # Every day at midnight
    },
}

app.autodiscover_tasks()