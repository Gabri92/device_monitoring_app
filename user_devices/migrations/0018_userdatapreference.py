# Generated by Django 5.1.1 on 2024-12-31 05:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_devices', '0017_remove_mappingvariable_end_index_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserDataPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('display_fields', models.JSONField()),
                ('chart_x_field', models.CharField(blank=True, max_length=255, null=True)),
                ('chart_y_field', models.CharField(blank=True, max_length=255, null=True)),
                ('display_order', models.JSONField()),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='user_devices.devicedata')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]