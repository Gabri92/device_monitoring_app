from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from django.db.models import Avg
from .models import Device, Button, Gateway, ComputedVariable, ModbusMappingVariable, DlmsMappingVariable, DeviceData, EnergyData
from django.shortcuts import redirect
from .commands import set_pin_status
from user_devices.helper_funcs import sanitize_variable_name, convert_to_local_time
import json
import logging 
from datetime import datetime, timedelta

def base_redirect(request):
    if request.user.is_authenticated:
        return redirect('home/')
    else:
        return redirect('login/')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)


def home_view(request):

    if not request.user.is_authenticated:
        return redirect('login')
    
    user = request.user
    gateways = Gateway.objects.filter(user=user)
    # Get user's gateways
    gateways = Gateway.objects.filter(user=user)
    
    # Get devices through the gateway relationship
    all_devices = Device.objects.filter(Gateway__in=gateways)
    devices = all_devices.filter(is_enabled=True)

    # Variabili da mostrare in homepage
    modbus_vars = ModbusMappingVariable.objects.filter(show_in_homepage=True, device__in=devices)
    dlms_vars = DlmsMappingVariable.objects.filter(show_in_homepage=True, device__in=devices)
    computed_vars = ComputedVariable.objects.filter(show_in_homepage=True, device__in=devices)

    # Add debug logging
    logger.info("==================== HOME VIEW DEBUG INFO ====================")
    logger.info(f"User: {user.username}")
    logger.info(f"User ID: {user.id}")
    logger.info(f"User's gateways: {gateways.count()}")
    logger.info("Gateway details:")
    for gateway in gateways:
        logger.info(f"  Gateway: {gateway.name} ({gateway.ip_address})")
        logger.info(f"  Devices on this gateway:")
        for dev in gateway.devices.all():
            logger.info(f"    - {dev.name} (enabled: {dev.is_enabled})")
    
    logger.info(f"\nTotal devices through gateways: {all_devices.count()}")
    logger.info(f"Enabled devices: {devices.count()}")
    logger.info("=========================================================")
    
    # Separate tables for gateway/plant data and device data
    gateway_rows = []
    device_rows = []
    
    # Show gateway production and consumption data
    for gateway in gateways:

        # Plant availability
        logger.info(f"Gateway availability: {gateway.availability}")
        gateway_rows.append({
            'device_name': gateway.name,
            'var_name': 'Average Availability',
            'value': gateway.availability,
            'unit': '%',
            'conversion_factor': '',
            'timestamp': datetime.now(),
        })

        # Plant production
        logger.info(f"Gateway production: {gateway.production}")
        logger.info(f"Gateway consumption: {gateway.consumption}")
        gateway_rows.append({
            'device_name': gateway.name,
            'var_name': 'Production',
            'value': gateway.production,
            'unit': 'kWh',
            'conversion_factor': '',
            'timestamp': datetime.now(),
        })

        # Plant consumption
        gateway_rows.append({
            'device_name': gateway.name,
            'var_name': 'Consumption',
            'value': gateway.consumption,
            'unit': 'kWh',
            'conversion_factor': '',
            'timestamp': datetime.now(),
        })

        # Plant performance
        gateway_rows.append({
            'device_name': gateway.name,
            'var_name': 'Performance',
            'value': gateway.performance,
            'unit': '%',
            'conversion_factor': '',
            'timestamp': datetime.now(),
        })

    for var in list(modbus_vars) + list(dlms_vars) + list(computed_vars):
        last_data = DeviceData.objects.filter(device_name=var.device).order_by('-timestamp').first()
        if last_data and var.var_name in last_data.data:
            raw = last_data.data.get(var.var_name)

            if isinstance(var, DlmsMappingVariable) and isinstance(raw, dict):
                value = raw.get("value", "N/A")
                timestamp_raw = raw.get("timestamp", last_data.timestamp)
                try:
                    # Parse the timestamp and convert to local time
                    parsed_timestamp = datetime.fromisoformat(timestamp_raw)
                    timestamp = convert_to_local_time(parsed_timestamp)
                except Exception:
                    timestamp = convert_to_local_time(last_data.timestamp)
            elif isinstance(raw, dict) and "value" in raw:
                value = raw["value"]
                timestamp = convert_to_local_time(last_data.timestamp)
            else:
                value = raw
                timestamp = convert_to_local_time(last_data.timestamp)

            device_rows.append({
                'device_name': var.device.name,
                'var_name': var.var_name,
                'value': value,
                'unit': var.unit,
                'conversion_factor': var.conversion_factor,
                'timestamp': timestamp,
            })

    # Energy data
    for device in devices:
        last_data = EnergyData.objects.filter(device_name=device).order_by('-timestamp').first()
        if not last_data:
            continue
        energy_data = last_data.data

        def add_energy_row(name, value):
            if isinstance(value, dict):
                val = value.get("value", "N/A")
                val = round(val,2)
            else:
                val = value
            device_rows.append({
                'device_name': device.name,
                'var_name': name.replace("_"," "),
                'value': val,
                'unit': 'kWh',
                'conversion_factor': '',
                'timestamp': last_data.timestamp,
            })

        if device.show_energy and 'Energy' in energy_data:
            add_energy_row('Energy', energy_data['Energy'])

        if device.show_energy_daily:
            for key, val in energy_data.items():
                logger.info(f"Energy daily: {key} - {val}")
                if key.startswith('Energy_daily'):
                    add_energy_row(key, val)

        if device.show_energy_weekly:
            for key, val in energy_data.items():
                if key.startswith('Energy_weekly'):                 
                    add_energy_row(key, val)

        if device.show_energy_monthly:
            for key, val in energy_data.items():
                if key.startswith('Energy_monthly'):
                    add_energy_row(key, val)

    return render(request, 'home.html', {
        'user': user,
        'gateways': gateways,
        'devices': devices,
        'gateway_rows': gateway_rows,
        'device_rows': device_rows,
    })


def device_detail_view(request, device_name):
    # Get user's gateways first
    user_gateways = Gateway.objects.filter(user=request.user)
    
    # Find device through gateway relationship
    device = get_object_or_404(
        Device, 
        name=device_name,
        Gateway__in=user_gateways  # Check device belongs to user's gateways
    )

    # Retrieve the buttons for this device
    buttons = Button.objects.filter(Gateway=device.Gateway, show_in_user_page=True)

    # Pass everything to the template
    context = {
        "gateway": device.Gateway,
        "device": device,
        "buttons": buttons,
        "y_label": "",
        "x_data": [],
        "y_data": [],
        "chart_error": "No data configure for this device yet.",
        "data": {}
    }

    # Retrieve last data from the device
    energy_data = EnergyData.objects.filter(device_name=device).order_by('-timestamp').first()
    device_data = DeviceData.objects.filter(device_name=device).order_by('-timestamp').first()
    
    # Only process energy_data if it exists
    if energy_data:
        for key, value in energy_data.data.items():
            
            if key == "Energy_daily_produced":
                context["data"]["Energy_daily_produced"] = value
            if key == "Energy_daily_consumed":
                context["data"]["Energy_daily_consumed"] = value
            if not key.startswith("Energy") and key != "timestamp":
                context["data"][key] = value

    # Only process device_data if it exists
    if device_data:
        for key, value in device_data.data.items():
            if not key == "timestamp":
                context["data"][key] = value

    # Retrieve historic data for chart
    y_variable = ComputedVariable.objects.filter(device=device, show_on_graph=True).first() or \
    ModbusMappingVariable.objects.filter(device=device, show_on_graph=True).first() or \
    DlmsMappingVariable.objects.filter(device=device, show_on_graph=True).first()

    if y_variable:
        logger.info(f"y_variable found: {y_variable}")
        logger.info(f"y_variable name: {y_variable.var_name}")
        logger.info(f"Device protocol: {device.protocol}")

        # Get data from last 24 hours
        from datetime import timedelta
        from django.utils import timezone
        
        # Use timezone-aware datetime
        now = timezone.now()
        twenty_four_hours_ago = now - timedelta(hours=24)
        
        # First, let's check if there's any data at all for this device
        all_data_count = DeviceData.objects.filter(device_name=device).count()
        logger.info(f"Total data records for device {device.name}: {all_data_count}")
        
        if all_data_count > 0:
            # Show the latest timestamp
            latest_data = DeviceData.objects.filter(device_name=device).order_by('-timestamp').first()
            logger.info(f"Latest data timestamp: {latest_data.timestamp}")
            logger.info(f"Current time: {now}")
            logger.info(f"24 hours ago: {twenty_four_hours_ago}")
        
        chart_data = DeviceData.objects.filter(
            device_name=device, 
            timestamp__gte=twenty_four_hours_ago
        ).order_by('timestamp')
        logger.info(f"Chart data count: {len(chart_data)} (from {twenty_four_hours_ago} to {now})")
        
        # If no data in last 24 hours, get the most recent data available
        if len(chart_data) == 0 and all_data_count > 0:
            logger.info("No data in last 24 hours, getting most recent data available")
            chart_data = DeviceData.objects.filter(device_name=device).order_by('-timestamp')[:50][::-1]
            logger.info(f"Fallback chart data count: {len(chart_data)}")
        
        if chart_data:
            logger.info(f"First chart data entry: {chart_data[0].data}")
            # Convert to list to safely access last element
            chart_data_list = list(chart_data)
            if chart_data_list:
                logger.info(f"Last chart data entry: {chart_data_list[-1].data}")
            # Reassign the list for further processing
            chart_data = chart_data_list
        
        sanitized_name = sanitize_variable_name(y_variable.var_name)
        logger.info(f"Sanitized variable name: {sanitized_name}")
        
        if device.protocol == "dlms":
            timestamps = []
            for entry in chart_data:
                # For DLMS, timestamp is at root level, not inside the variable
                timestamp_str = entry.data.get("timestamp", "")
                if timestamp_str:
                    try:
                        # Parse the timestamp and convert to local time
                        parsed_timestamp = datetime.fromisoformat(timestamp_str)
                        local_timestamp = convert_to_local_time(parsed_timestamp)
                        timestamp = local_timestamp.strftime("%Y-%m-%d %H:%M")
                        timestamps.append(timestamp)
                    except Exception as e:
                        logger.info(f"Error parsing timestamp '{timestamp_str}': {e}")
                        # Fallback to entry timestamp
                        timestamp = convert_to_local_time(entry.timestamp).strftime("%Y-%m-%d %H:%M")
                        timestamps.append(timestamp)
                else:
                    # Fallback to entry timestamp if no timestamp in data
                    timestamp = convert_to_local_time(entry.timestamp).strftime("%Y-%m-%d %H:%M")
                    timestamps.append(timestamp)      
        elif device.protocol == "modbus":  # Corretto da "modubs" a "modbus"
            timestamps = [
                convert_to_local_time(entry.timestamp).strftime("%Y-%m-%d %H:%M")  # Formato consistente con DLMS
                for entry in chart_data
            ]  
        else:
            timestamps = []
            logger.info(f"Unknown protocol: {device.protocol}")
            
        x_data = timestamps  # Example X values
        y_data = [entry.data.get(sanitized_name, {}).get("value", None) for entry in chart_data]
        
        logger.info(f"X data length: {len(x_data)}")
        logger.info(f"Y data length: {len(y_data)}")
        logger.info(f"X data sample: {x_data[:3] if x_data else 'Empty'}")
        logger.info(f"Y data sample: {y_data[:3] if y_data else 'Empty'}")
        
        # Debug: show what we're extracting for Y data
        logger.info("Y data extraction details:")
        for i, entry in enumerate(chart_data):
            var_data = entry.data.get(sanitized_name, {})
            value = var_data.get("value", None) if isinstance(var_data, dict) else None
            logger.info(f"  Entry {i}: {sanitized_name} = {value} (from {var_data})")

        # Assume you have logic to generate x_data and y_data
        context["x_data"] = json.dumps(x_data)
        context["y_data"] = json.dumps(y_data)
        context["y_label"] = y_variable.var_name
        context["chart_error"] = None  # Clear the error
    else:
        logger.info("No y_variable found for chart")

    return render(request, 'device_detail.html', context)

def toggle_button_status(request, button_id):
    button = get_object_or_404(Button, id=button_id, Gateway__user=request.user)
    status = 'on' if not button.is_active else 'off'

    # Use the utility function to toggle the button's state
    success, response = set_pin_status(button.Gateway, button.pin_number, status)
    if success:
        button.is_active = not button.is_active
        button.save()
        messages.success(request, f"Button '{button.label}' updated successfully.")
    else:
        messages.error(request, f"Error updating button: {response}")
    # Redirect back to the referring page
    return redirect(request.META.get('HTTP_REFERER', '/'))