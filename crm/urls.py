from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.dashboard, name='crm_dashboard'),
    
    # 🔄 API ДЛЯ АВТООБНОВЛЕНИЯ
    path('api/check-new-requests/', views.check_new_requests, name='crm_api_check_new_requests'),
    path('api/check-new-candidates/', views.check_new_candidates, name='crm_api_check_new_candidates'),
    path('api/check-new-feedback/', views.check_new_feedback, name='crm_api_check_new_feedback'),
    path('api/mark-request-viewed/<int:pk>/', views.mark_request_as_viewed, name='crm_api_mark_request_viewed'),
    path('api/mark-all-viewed/', views.mark_all_viewed, name='crm_api_mark_all_viewed'),
    
    # 🔹 Проверка новых заявок
    path('check-new-requests/', views.check_new_requests, name='crm_check_new_requests'),
    path('request/<int:pk>/mark-viewed/', views.mark_request_as_viewed, name='crm_mark_request_viewed'),
    
    # 📋 Заявки
    path('request/<int:pk>/download/', views.download_request_file, name='crm_download_file'),  # ✅ ДОБАВЛЕНО
    path('request/<int:pk>/download/', views.download_request_file, name='crm_download_request_file'),  # ✅ Алиас для обратной совместимости
    path('requests/', views.my_requests, name='crm_requests'),
    path('my-requests/', views.my_requests, name='crm_my_requests'),
    path('request/<int:pk>/', views.request_detail, name='crm_request_detail'),
    path('request/<int:pk>/assign/', views.assign_manager, name='crm_assign_manager'),
    path('request/create/', views.create_request, name='crm_create_request'),
    path('request/<int:pk>/delete/', views.delete_request, name='crm_delete_request'),
    
    # 👥 Клиенты
    path('clients/', views.clients_list, name='crm_clients'),
    path('clients/<int:pk>/', views.client_detail, name='crm_client_detail'),
    path('clients/<int:pk>/update/', views.client_update, name='crm_client_update'),
    path('clients/<int:pk>/delete/', views.client_delete, name='crm_client_delete'),
    path('clients/create/', views.client_create, name='crm_create_client'),
    
    # 📊 Проекты
    path('projects/', views.projects_list, name='crm_projects'),
    path('projects/create/', views.project_create, name='crm_project_create'),
    path('projects/<int:pk>/', views.project_detail, name='crm_project_detail'),
    path('projects/<int:pk>/update/', views.project_update, name='crm_project_update'),
    path('projects/<int:pk>/delete/', views.project_delete, name='crm_project_delete'),
    path('projects/fix-existing/', views.fix_existing_projects, name='crm_fix_existing_projects'),
    path('projects/cleanup/', views.cleanup_projects, name='crm_cleanup_projects'),
    path('projects/<int:pk>/edit/', views.project_edit, name='crm_project_edit'),
    
    # 👔 Менеджеры (УПРАВЛЕНИЕ)
    path('managers/', views.managers_list, name='crm_managers_list'),
    path('managers/', views.managers_list, name='crm_managers'),
    path('managers/create/', views.manager_create, name='crm_manager_create'),
    path('managers/<int:manager_id>/', views.manager_detail, name='crm_manager_detail'),
    path('managers/<int:manager_id>/edit/', views.manager_edit, name='crm_manager_edit'),
    path('managers/<int:manager_id>/delete/', views.manager_delete, name='crm_manager_delete'),
    path('managers/<int:manager_id>/toggle-active/', views.manager_toggle_active, name='crm_manager_toggle_active'),
    path('managers/<int:manager_id>/reset-password/', views.reset_manager_password, name='crm_reset_manager_password'),
    
    # 👤 Профиль
    path('profile/', views.profile_view, name='crm_profile'),
    path('profile/update/', views.profile_update, name='crm_profile_update'),
    path('profile/change-password/', views.change_password, name='crm_change_password'),
    
    # 💼 Вакансии
    path('vacancies/', views.vacancies_list, name='crm_vacancies_list'),
    path('vacancies/create/', views.vacancy_create, name='crm_vacancy_create'),
    path('vacancies/<int:vacancy_id>/edit/', views.vacancy_edit, name='crm_vacancy_edit'),
    path('vacancies/<int:vacancy_id>/toggle/', views.vacancy_toggle, name='crm_vacancy_toggle'),
    path('vacancies/<int:vacancy_id>/delete/', views.vacancy_delete, name='crm_vacancy_delete'),
    
    # 👥 Кандидаты
    path('candidates/', views.candidates_list, name='crm_candidates_list'),
    path('candidates/<int:candidate_id>/', views.candidate_detail, name='crm_candidate_detail'),
    path('candidates/<int:candidate_id>/delete/', views.candidate_delete, name='crm_candidate_delete'),
    path('check-new-candidates/', views.check_new_candidates, name='crm_check_new_candidates'),
    
    # 🔄 Автообновление
    path('change-request-status/', views.change_request_status, name='crm_change_request_status'),
    path('mark-all-viewed/', views.mark_all_viewed, name='crm_mark_all_viewed'),

    # 📨 Обратная связь
    path('feedback/', views.feedback_list, name='crm_feedback'),
    path('feedback/<int:pk>/', views.feedback_detail, name='crm_feedback_detail'),
    path('feedback/<int:pk>/update-status/', views.feedback_update_status, name='crm_feedback_update_status'),
    path('feedback/<int:pk>/delete/', views.feedback_delete, name='crm_feedback_delete'),
    path('feedback/mark-all-viewed/', views.feedback_mark_all_viewed, name='crm_feedback_mark_all_viewed'),
    path('check-new-feedback/', views.check_new_feedback, name='crm_check_new_feedback'),
    
    # 🎯 ПРОМО-БЛОКИ
    path('promo-blocks/', views.crm_promo_blocks, name='crm_promo_blocks'),
    path('promo-blocks/create/', views.quick_promo_create, name='crm_promo_create'),
    path('promo-blocks/<int:pk>/edit/', views.promo_block_edit, name='crm_promo_block_edit'),
    path('promo-blocks/<int:pk>/quick-edit/', views.promo_block_quick_edit, name='crm_promo_block_quick_edit'),
    path('promo-blocks/<int:pk>/get-data/', views.promo_block_get_data, name='crm_promo_block_get_data'),
    path('promo-blocks/<int:pk>/update-dates/', views.promo_block_update_dates, name='crm_promo_block_update_dates'),
    path('promo-blocks/<int:pk>/update-design/', views.promo_block_update_design, name='crm_promo_block_update_design'),
    path('promo-blocks/<int:pk>/update-layout/', views.promo_block_update_layout, name='crm_promo_block_update_layout'),
    path('promo-blocks/<int:pk>/apply-template/', views.promo_block_apply_template, name='crm_promo_block_apply_template'),
    path('promo-blocks/<int:pk>/reset-image/', views.promo_block_reset_image, name='crm_promo_block_reset_image'),
    path('promo-blocks/<int:pk>/toggle-active/', views.promo_block_toggle_active, name='crm_promo_block_toggle_active'),
    path('promo-blocks/<int:pk>/duplicate/', views.duplicate_promo_block, name='crm_promo_block_duplicate'),
    path('promo-blocks/<int:pk>/preview/', views.promo_block_preview, name='crm_promo_block_preview'),
    path('services/', views.services_list, name='crm_services'),
    path('services/create/', views.service_create, name='crm_service_create'),
    path('services/<int:pk>/edit/', views.service_edit, name='crm_service_edit'),
    path('services/<int:pk>/delete/', views.service_delete, name='crm_service_delete'),
    path('services/<int:pk>/toggle-kp/', views.service_toggle_kp, name='crm_service_toggle_kp'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)