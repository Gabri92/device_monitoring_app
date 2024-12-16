# Generated by Django 5.1.1 on 2024-12-14 17:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0008_alter_device_bytes_count_alter_device_slave_id_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='button',
            name='device',
        ),
        migrations.AddField(
            model_name='button',
            name='Gateway',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='buttons', to='user_devices.gateway'),
        ),
    ]