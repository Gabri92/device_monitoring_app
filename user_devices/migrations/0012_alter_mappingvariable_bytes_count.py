# Generated by Django 5.1.1 on 2024-12-14 18:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0011_alter_computedvariable_formula_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='mappingvariable',
            name='bytes_count',
            field=models.PositiveIntegerField(default=1, help_text='Number of bytes to read'),
        ),
    ]
