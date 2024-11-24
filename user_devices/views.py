from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render
from django.shortcuts import render, get_object_or_404
from .models import Device
from user_devices.tasks import test_celery_task
from django.shortcuts import redirect

def base_redirect(request):
    if request.user.is_authenticated:
        return redirect('home/')
    else:
        return redirect('login/')

def home_view(request):
    devices = request.user.devices.all()
    return render(request, 'home.html',{'devices': devices})  # Create a home.html template

def device_detail_view(request,device_name):
    test_celery_task.delay()  # Call the Celery task
    device = get_object_or_404(Device, name=device_name, user=request.user)
    return render(request, 'device_detail.html', {'device': device})  # Create a device_detail.html template