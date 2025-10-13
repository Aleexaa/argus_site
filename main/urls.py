# main/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('projects/', views.projects, name='projects'),
    path('partners/', views.partners, name='partners_test'),
    path('contacts/', views.contacts, name='contacts'),
    path('order-kp/', views.order_kp, name='order_kp'),
    path('order-success/', views.order_success, name='order_success'),
]