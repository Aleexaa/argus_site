from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.dashboard, name='crm_dashboard'),
    
    # 🔹 ДОБАВЬТЕ ЭТИ СТРОЧКИ
    path('check-new-requests/', views.check_new_requests, name='crm_check_new_requests'),
    path('request/<int:pk>/mark-viewed/', views.mark_request_as_viewed, name='crm_mark_request_viewed'),
    
    path('request/<int:pk>/download/', views.download_request_file, name='crm_download_file'),
    path('requests/', views.requests_list, name='crm_requests'),
    path('my-requests/', views.my_requests, name='crm_my_requests'),
    path('request/<int:pk>/', views.request_detail, name='crm_request_detail'),
    path('request/<int:pk>/assign/', views.assign_manager, name='crm_assign_manager'),
    path('request/<int:pk>/mark-viewed/', views.mark_request_as_viewed, name='crm_mark_request_viewed'),
    # Клиенты и проекты
    path('clients/', views.clients_list, name='crm_clients'),
    path('projects/', views.projects_list, name='crm_projects'),
    path('add-project/', views.add_project, name='crm_add_project'),
    path('clients/my/', views.clients_list, name='crm_my_clients'),

    # Менеджеры
    path('managers/', views.managers_list, name='crm_managers'),

    # Профиль
    path('profile/', views.profile_view, name='crm_profile'),
]