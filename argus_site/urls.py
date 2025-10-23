# argus_site/urls.py
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from crm import views as crm_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Главный сайт
    path('', include('main.urls')),

    # CRM
    path('crm/', include('crm.urls')),

    # --- Аутентификация ---
    path('login/', crm_views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
]
