from django.urls import path
from . import views
from .views import PrivacyPolicyView, TermsView

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('services/', views.services, name='services'),
    path('projects/', views.projects, name='projects'),
    path('partners/', views.partners, name='partners'),  # Новая чистая версия
    path('contacts/', views.contacts, name='contacts'),
    path('order-kp/', views.order_kp, name='order_kp'),
    path('order-success/', views.order_success, name='order_success'),
    path('vacancies/', views.vacancies_list, name='vacancies_list'),
    path('vacancies/<int:pk>/', views.vacancy_detail, name='vacancy_detail'),
    path('privacy-policy/', PrivacyPolicyView.as_view(), name='privacy_policy'),
    path('terms/', TermsView.as_view(), name='terms'),
]