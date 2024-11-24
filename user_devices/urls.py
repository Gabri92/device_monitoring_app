# urls.py
from django.urls import path
from django.contrib.auth.views import LoginView, LogoutView
from .views import home_view  # Import your home view or another view to redirect after login
from . import views

urlpatterns = [
    path('', views.base_redirect, name='base_redirect'),
    path('login/', LoginView.as_view(), name='login'),  # URL for the login view
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),  # URL for logout
    path('home/', home_view, name='home'),  # URL for the home view
    path('device/<str:device_name>/', views.device_detail_view, name='device_detail')  # URL for the device detail view
]