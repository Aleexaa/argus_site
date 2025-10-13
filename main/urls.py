# main/urls.py
from django.urls import path
from . import views
from . import new_views

urlpatterns = [
    path('partners/', new_views.partners_simple, name='partners'),
        # path('', views.home, name='home'),
        # path('about/', views.about, name='about'),
        # path('services/', views.services, name='services'),
        # path('projects/', views.projects, name='projects'),
        # path('partners-new/', views.partners_new, name='partners_new'),
        # path('contacts/', views.contacts, name='contacts'),
        # path('order-kp/', views.order_kp, name='order_kp'),
        # path('order-success/', views.order_success, name='order_success'),
]