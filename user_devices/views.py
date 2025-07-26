from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from .models import Device, Button, Gateway, ComputedVariable, ModbusMappingVariable, DeviceData
from django.shortcuts import redirect
from .commands import set_pin_status
from user_devices.functions import sanitize_variable_name  # or wherever it is
import json
import logging 

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
    
    return render(request, 'home.html',
                  {'user': user, 
                   'gateways': gateways, 
                   'devices': devices
                   })  # Create a home.html template


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
        "data": None
    }


    # Retrieve last data from the device
    counter_data = DeviceData.objects.filter(device_name=device).order_by('-timestamp').first()
    if counter_data:
        # Create a filtered copy of the data with only selected energy metrics
        filtered_data = {}
        for key, val in counter_data.data.items():
            # Always include non-energy data
            if not key.startswith('Energy'):
                filtered_data[key] = val
                continue
                
            # Include basic energy metrics
            if key in ['Energy', 'Energy_produced', 'Energy_consumed']:
                filtered_data[key] = val
                continue
                
            # Filter daily/weekly/monthly based on settings
            if key == 'Energy' and device.show_energy:
                filtered_data[key] = val
            elif key in ['Energy_produced', 'Energy_consumed'] and device.show_energy:
                filtered_data[key] = val
            elif device.show_energy_daily and key.startswith('Energy_daily'):
                filtered_data[key] = val
            elif device.show_energy_weekly and key.startswith('Energy_weekly'):
                filtered_data[key] = val
            elif device.show_energy_monthly and key.startswith('Energy_monthly'):
                filtered_data[key] = val
                
        context["data"] = {"data": filtered_data}

    # Retrieve historic data for chart
    y_variable = ComputedVariable.objects.filter(device=device, show_on_graph=True).first() or \
    ModbusMappingVariable.objects.filter(device=device, show_on_graph=True).first()

    if y_variable:
        
        # Example: Generate dummy time-series data for demonstration
        chart_data = DeviceData.objects.filter(device_name=device).order_by('-timestamp')[:20][::-1]
        timestamps = [entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") for entry in chart_data]
        x_data = timestamps  # Example X values
        sanitized_name = sanitize_variable_name(y_variable.var_name)
        y_data = [entry.data.get(sanitized_name, {}).get("value", None) for entry in chart_data]
        # Assume you have logic to generate x_data and y_data
        context["x_data"] = json.dumps(x_data)
        context["y_data"] = json.dumps(y_data)
        context["y_label"] = y_variable.var_name
        context["chart_error"] = None  # Clear the error

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