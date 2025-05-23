# Generated by Django 5.1.1 on 2025-01-20 06:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0021_remove_computedvariable_is_x_axis_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='slave_id',
            field=models.IntegerField(default=-1, help_text='Slave ID of the device(nr between 1 to 247)'),
        ),
        migrations.AlterField(
            model_name='mappingvariable',
            name='conversion_factor',
            field=models.CharField(default='1', help_text='Factor to convert raw data to physical value'),
        ),
    ]
