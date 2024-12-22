from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from .models import Device, Button, Gateway
from django.shortcuts import redirect
from .commands import set_pin_status

def base_redirect(request):
    if request.user.is_authenticated:
        return redirect('home/')
    else:
        return redirect('login/')

def home_view(request):
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
    return render(request, 'device_detail.html', {
        'gateway': device.Gateway, 
        'device': device,
        'buttons': buttons,
    })

def toggle_button_status(request, button_id):
    button = get_object_or_404(Button, id=button_id, device__user=request.user)
    status = 'on' if not button.is_active else 'off'

    # Use the utility function to toggle the button's state
    success, response = set_pin_status(button.device, button.pin_number, status)
    if success:
        button.is_active = not button.is_active
        button.save()
        messages.success(request, f"Button '{button.label}' updated successfully.")
    else:
        messages.error(request, f"Error updating button: {response}")
    return redirect('device_detail', device_name=button.device.name)