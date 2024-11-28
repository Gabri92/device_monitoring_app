# Generated by Django 5.1.1 on 2024-11-28 15:41

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0002_alter_device_is_active'),
    ]

    operations = [
        migrations.CreateModel(
            name='Button',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=100)),
                ('pin_number', models.IntegerField()),
                ('is_active', models.BooleanField(default=False)),
                ('show_in_user_page', models.BooleanField(default=False)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='buttons', to='user_devices.device')),
            ],
        ),
    ]
