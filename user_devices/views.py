from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from .models import Device, Button, Gateway, ComputedVariable, MappingVariable, DeviceData
from django.shortcuts import redirect
from .commands import set_pin_status
from user_devices.functions import sanitize_variable_name  # or wherever it is
import json

def base_redirect(request):
    if request.user.is_authenticated:
        return redirect('home/')
    else:
        return redirect('login/')

def home_view(request):

    if not request.user.is_authenticated:
        return redirect('login')
    
    user = request.user
    gateways = Gateway.objects.filter(user=user)
    devices = Device.objects.filter(user=user)
    return render(request, 'home.html',
                  {'user': user, 
                   'gateways': gateways, 
                   'devices': devices
                   })  # Create a home.html template


def device_detail_view(request,device_name):
    # Retrieve the device object
    device = get_object_or_404(Device, name=device_name, user=request.user)

    # Retrieve the buttons for this device
    buttons = Button.objects.filter(Gateway=device.Gateway, show_in_user_page=True)

    # Pass everything to the template
    context = {
        "gateway": device.Gateway,
        "device":  device,
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
        context["data"] = counter_data

    # Retrieve historic data for chart
    y_variable = ComputedVariable.objects.filter(device=device, show_on_graph=True).first() or \
    MappingVariable.objects.filter(device=device, show_on_graph=True).first()

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