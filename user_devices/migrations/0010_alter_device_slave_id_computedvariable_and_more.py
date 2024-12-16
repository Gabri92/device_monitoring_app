# Generated by Django 5.1.1 on 2024-12-14 18:35

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0009_remove_button_device_button_gateway'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='slave_id',
            field=models.IntegerField(default=-1, help_text='Slave ID of the device(nr between 1 to 247)', unique=True),
        ),
        migrations.CreateModel(
            name='ComputedVariable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('variable_type', models.CharField(choices=[('memory', 'Memory Mapping'), ('computed', 'Computed Variable')], default='memory', help_text='Choose the type of variable to configure (Memory Mapping or Computed Variable)', max_length=10)),
                ('var_name', models.CharField(help_text='Name of the variable (e.g., Voltage, Power)', max_length=100)),
                ('formula', models.TextField(help_text="Formula to calculate the value (e.g., 'voltage * current'). Variables must match existing MemoryMapping.variable_name.")),
                ('unit', models.CharField(help_text='Measurement unit (e.g., W, kW, etc.)', max_length=20)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='computer_variables', to='user_devices.device')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='MappingVariable',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('variable_type', models.CharField(choices=[('memory', 'Memory Mapping'), ('computed', 'Computed Variable')], default='memory', help_text='Choose the type of variable to configure (Memory Mapping or Computed Variable)', max_length=10)),
                ('var_name', models.CharField(help_text='Name of the variable (e.g., Voltage, Power)', max_length=100)),
                ('address', models.CharField(help_text='Starting Modbus address in hexadecimal (e.g., 0x0280)')),
                ('bytes_count', models.PositiveIntegerField(default=1, help_text='Number of bytes to read')),
                ('unit', models.CharField(help_text='Measurement unit (e.g., V, A, Hz)', max_length=20)),
                ('conversion_factor', models.FloatField(default=1.0, help_text='Factor to convert raw data to physical value')),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mapped_variables', to='user_devices.device')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.DeleteModel(
            name='Mapping',
        ),
    ]