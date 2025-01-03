# Generated by Django 5.1.1 on 2024-12-18 05:37

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0015_remove_mappingvariable_address_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DeviceData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.JSONField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('device_name', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='device_data', to='user_devices.device')),
                ('gateway', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gateway_data', to='user_devices.gateway')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_device_data', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
