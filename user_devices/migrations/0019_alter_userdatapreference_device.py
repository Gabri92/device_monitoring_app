# Generated by Django 5.1.1 on 2024-12-31 05:47

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0018_userdatapreference'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdatapreference',
            name='device',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='user_devices.device'),
        ),
    ]