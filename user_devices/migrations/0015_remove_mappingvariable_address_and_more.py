# Generated by Django 5.1.1 on 2024-12-15 07:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0014_alter_computedvariable_device'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='mappingvariable',
            name='address',
        ),
        migrations.RemoveField(
            model_name='mappingvariable',
            name='bytes_count',
        ),
        migrations.AddField(
            model_name='mappingvariable',
            name='end_index',
            field=models.PositiveIntegerField(default=1, help_text='End index of the response array'),
        ),
        migrations.AddField(
            model_name='mappingvariable',
            name='start_index',
            field=models.PositiveBigIntegerField(default=1, help_text='Starting index of the response array'),
        ),
    ]
