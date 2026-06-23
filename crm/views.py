from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import EmailMessage
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.template.loader import render_to_string
from django.utils import timezone
from datetime import timedelta
import os
import logging
from main.models import Service
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.contrib.auth.models import User
from .models import ManagerProfile, ViewedRequest, Vacancy, Candidate, Comment, Client, Feedback, PromoBlock
from main.models import Request, Project
from .forms import ClientForm
import secrets
import string
import uuid

logger = logging.getLogger(__name__)


def login_view(request):
    if request.user.is_authenticated:
        try:
            profile = request.user.managerprofile
        except:
            from crm.models import ManagerProfile
            role = 'owner' if request.user.is_superuser else 'manager'
            ManagerProfile.objects.get_or_create(
                user=request.user,
                defaults={
                    'role': role,
                    'corporate_email': request.user.email or f"{request.user.username}@argus.ru",
                }
            )
        return redirect('crm_dashboard')

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            from crm.models import ManagerProfile
            role = 'owner' if user.is_superuser else 'manager'
            ManagerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': role,
                    'corporate_email': user.email or f"{user.username}@argus.ru",
                }
            )
            next_url = request.GET.get('next', '/crm/')
            return redirect(next_url)
        else:
            messages.error(request, "Неверный логин или пароль")

    return render(request, "crm/login.html")


def is_owner(user):
    return hasattr(user, 'managerprofile') and user.managerprofile.role == 'owner'


def is_manager(user):
    return hasattr(user, 'managerprofile') and user.managerprofile.role == 'manager'


def _notify_owner_about_request(request_obj):
    try:
        owner_profiles = ManagerProfile.objects.filter(role='owner')
        if not owner_profiles.exists():
            return

        recipient_list = [
            profile.corporate_email
            for profile in owner_profiles
            if profile.corporate_email
        ]
        if not recipient_list:
            return

        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        
        subject = f"Новая заявка #{request_obj.id} от {request_obj.client.company_name}"
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px;">
            <h2 style="color: #1E3A8A;">Новая заявка #{request_obj.id}</h2>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 10px 0;">
                <p><strong>Компания:</strong> {request_obj.client.company_name}</p>
                <p><strong>Контактное лицо:</strong> {request_obj.client.contact_person or 'Не указано'}</p>
                <p><strong>Телефон:</strong> {request_obj.client.phone}</p>
                <p><strong>Email:</strong> {request_obj.client.email or 'Не указан'}</p>
                <p><strong>Тип объекта:</strong> {request_obj.object_type}</p>
                <p><strong>Адрес:</strong> {request_obj.object_address or 'Не указан'}</p>
            </div>
            <p><strong>Статус:</strong> {request_obj.get_status_display()}</p>
            <p><strong>Дата:</strong> {request_obj.created_at.strftime('%d.%m.%Y %H:%M')}</p>
            <a href="{site_url}/crm/request/{request_obj.id}/"
               style="display: inline-block; background: #1E3A8A; color: white; padding: 10px 20px;
                      text-decoration: none; border-radius: 5px; margin-top: 10px;">
                Перейти к заявке
            </a>
        </body>
        </html>
        """
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления владельцам: {e}")


def _notify_manager_assignment(req):
    if not req.responsible_manager:
        return
    
    manager_email = None
    if req.responsible_manager.corporate_email:
        manager_email = req.responsible_manager.corporate_email
    elif req.responsible_manager.user.email:
        manager_email = req.responsible_manager.user.email
    
    if not manager_email:
        return
    
    try:
        site_url = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000')
        manager_name = req.responsible_manager.user.get_full_name() or req.responsible_manager.user.username
        
        subject = f"Вам назначена заявка #{req.id}"
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px;">
            <h2 style="color: #1E3A8A;">Вам назначена новая заявка</h2>
            <p>Здравствуйте, {manager_name}!</p>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
                <p><strong>Клиент:</strong> {req.client.company_name}</p>
                <p><strong>Тип объекта:</strong> {req.object_type}</p>
                <p><strong>Адрес:</strong> {req.object_address or 'Не указан'}</p>
            </div>
            <a href="{site_url}/crm/request/{req.id}/"
               style="display: inline-block; background: #1E3A8A; color: white; padding: 10px 20px;
                      text-decoration: none; border-radius: 5px; margin-top: 10px;">
                Перейти к заявке
            </a>
        </body>
        </html>
        """
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[manager_email],
        )
        email.content_subtype = "html"
        email.send(fail_silently=True)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления менеджеру: {e}")


def _notify_client_status(req):
    client_email = req.client.email
    if not client_email:
        return
    try:
        subject = f"Обновление статуса заявки #{req.id}"
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: Arial, sans-serif; padding: 20px; max-width: 600px;">
            <h2 style="color: #1E3A8A;">Обновление статуса заявки</h2>
            <p>Здравствуйте, {req.client.contact_person or req.client.company_name}!</p>
            <p>Статус вашей заявки <strong>#{req.id}</strong> изменён на:
               <span style="color: #1E3A8A;">{req.get_status_display()}</span></p>
            <div style="background: #f8f9fa; padding: 15px; border-radius: 8px;">
                <p><strong>Тип объекта:</strong> {req.object_type}</p>
                <p><strong>Адрес:</strong> {req.object_address or 'Не указан'}</p>
            </div>
            <p>Наш специалист свяжется с вами при необходимости.</p>
            <p style="margin-top: 20px;">С уважением,<br>Компания Аргус</p>
            <p>Телефон: (3452) 59-30-20<br>Email: argus-ops@mail.ru</p>
        </body>
        </html>
        """
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[client_email],
        )
        email.content_subtype = "html"
        email.send(fail_silently=False)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления клиенту: {e}")


def create_internal_notification(request_obj, notification_type, recipient_manager=None):
    """Создание внутреннего уведомления в системе"""
    from .models import InternalNotification
    
    if notification_type == 'new_request':
        # Уведомление для владельцев о новой заявке
        owners = ManagerProfile.objects.filter(role='owner')
        for owner in owners:
            InternalNotification.objects.create(
                recipient=owner,
                notification_type='new_request',
                title=f'Новая заявка #{request_obj.id}',
                message=f'Поступила новая заявка от компании {request_obj.client.company_name}',
                link=f'/crm/request/{request_obj.id}/',
                related_object_id=request_obj.id,
                related_object_type='request'
            )
    
    elif notification_type == 'request_assigned':
        # Уведомление менеджеру о назначении заявки
        if recipient_manager:
            InternalNotification.objects.create(
                recipient=recipient_manager,
                notification_type='request_assigned',
                title=f'Вам назначена заявка #{request_obj.id}',
                message=f'Клиент: {request_obj.client.company_name}',
                link=f'/crm/request/{request_obj.id}/',
                related_object_id=request_obj.id,
                related_object_type='request'
            )
    
    elif notification_type == 'status_changed':
        # Уведомление о смене статуса (для владельца и менеджера)
        if request_obj.responsible_manager:
            InternalNotification.objects.create(
                recipient=request_obj.responsible_manager,
                notification_type='status_changed',
                title=f'Изменение статуса заявки #{request_obj.id}',
                message=f'Статус изменен на: {request_obj.get_status_display()}',
                link=f'/crm/request/{request_obj.id}/',
                related_object_id=request_obj.id,
                related_object_type='request'
            )
        
        owners = ManagerProfile.objects.filter(role='owner')
        for owner in owners:
            InternalNotification.objects.create(
                recipient=owner,
                notification_type='status_changed',
                title=f'Изменение статуса заявки #{request_obj.id}',
                message=f'Статус изменен на: {request_obj.get_status_display()}',
                link=f'/crm/request/{request_obj.id}/',
                related_object_id=request_obj.id,
                related_object_type='request'
            )
    
    elif notification_type == 'new_comment':
        # Уведомление о новом комментарии
        if request_obj.responsible_manager:
            InternalNotification.objects.create(
                recipient=request_obj.responsible_manager,
                notification_type='new_comment',
                title=f'Новый комментарий к заявке #{request_obj.id}',
                message=f'Добавлен новый комментарий к заявке',
                link=f'/crm/request/{request_obj.id}/',
                related_object_id=request_obj.id,
                related_object_type='request'
            )
        
        owners = ManagerProfile.objects.filter(role='owner')
        for owner in owners:
            InternalNotification.objects.create(
                recipient=owner,
                notification_type='new_comment',
                title=f'Новый комментарий к заявке #{request_obj.id}',
                message=f'Добавлен новый комментарий к заявке',
                link=f'/crm/request/{request_obj.id}/',
                related_object_id=request_obj.id,
                related_object_type='request'
            )


@login_required
def get_notifications(request):
    try:
        profile = request.user.managerprofile
        from .models import InternalNotification
        
        # Получаем непрочитанные внутренние уведомления
        unread_notifications = InternalNotification.objects.filter(
            recipient=profile,
            is_read=False
        ).order_by('-created_at')[:20]
        
        unread_count = unread_notifications.count()
        
        # Внешние уведомления (старая логика)
        if profile.role == 'owner':
            all_requests = Request.objects.all()
        else:
            all_requests = Request.objects.filter(responsible_manager=profile)

        viewed_ids = ViewedRequest.objects.filter(user=request.user).values_list('request_id', flat=True)
        unviewed_requests = all_requests.exclude(id__in=viewed_ids).count()
        new_requests = all_requests.filter(status='new').count()
        new_candidates = 0
        if profile.role == 'owner':
            new_candidates = Candidate.objects.filter(
                applied_at__gte=timezone.now() - timedelta(days=1)
            ).count()
        new_feedback = Feedback.objects.filter(is_viewed=False).count()

        unviewed_list = []
        if unviewed_requests > 0:
            for req in all_requests.exclude(id__in=viewed_ids).order_by('-created_at')[:5]:
                unviewed_list.append({
                    'id': req.id,
                    'company': req.client.company_name,
                    'date': req.created_at.strftime('%d.%m.%Y %H:%M'),
                    'status': req.get_status_display(),
                })
        
        # Форматируем внутренние уведомления для JSON
        notifications_list = []
        for notif in unread_notifications:
            notifications_list.append({
                'id': notif.id,
                'type': notif.notification_type,
                'title': notif.title,
                'message': notif.message,
                'link': notif.link,
                'created_at': notif.created_at.strftime('%d.%m.%Y %H:%M'),
                'is_read': notif.is_read
            })

        return JsonResponse({
            'status': 'success',
            'unviewed_requests': unviewed_requests,
            'new_requests': new_requests,
            'new_candidates': new_candidates,
            'new_feedback': new_feedback,
            'total_notifications': unviewed_requests + new_candidates + new_feedback,
            'latest_unviewed': unviewed_list,
            'internal_notifications': notifications_list,
            'internal_unread_count': unread_count,
            'last_check': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})
@login_required
def mark_notification_read(request, notification_id):
    """Удалить уведомление (полное удаление из БД)"""
    try:
        from .models import InternalNotification
        profile = request.user.managerprofile
        
        notification = get_object_or_404(InternalNotification, id=notification_id, recipient=profile)
        notification.delete()  # Удаляем полностью, а не отмечаем как прочитанное
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})
@login_required
def mark_all_notifications_read(request):
    """Удалить все уведомления пользователя"""
    try:
        from .models import InternalNotification
        profile = request.user.managerprofile
        
        deleted_count = InternalNotification.objects.filter(recipient=profile).delete()[0]
        
        return JsonResponse({
            'status': 'success',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})
@login_required
def check_new_notifications(request):
    try:
        profile = request.user.managerprofile
        last_check = request.GET.get('last_check')
        from .models import InternalNotification

        if profile.role == 'owner':
            all_requests = Request.objects.all()
        else:
            all_requests = Request.objects.filter(responsible_manager=profile)

        viewed_ids = ViewedRequest.objects.filter(user=request.user).values_list('request_id', flat=True)

        if last_check:
            try:
                last_check_time = timezone.datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                new_unviewed = all_requests.filter(
                    created_at__gt=last_check_time
                ).exclude(id__in=viewed_ids).count()
                new_feedback = Feedback.objects.filter(
                    created_at__gt=last_check_time,
                    is_viewed=False
                ).count()
                new_candidates = 0
                if profile.role == 'owner':
                    new_candidates = Candidate.objects.filter(
                        applied_at__gt=last_check_time
                    ).count()
                new_internal = InternalNotification.objects.filter(
                    recipient=profile,
                    is_read=False,
                    created_at__gt=last_check_time
                ).count()
            except:
                new_unviewed = all_requests.exclude(id__in=viewed_ids).count()
                new_feedback = Feedback.objects.filter(is_viewed=False).count()
                new_candidates = 0
                new_internal = InternalNotification.objects.filter(recipient=profile, is_read=False).count()
        else:
            new_unviewed = all_requests.exclude(id__in=viewed_ids).count()
            new_feedback = Feedback.objects.filter(is_viewed=False).count()
            new_candidates = 0
            new_internal = InternalNotification.objects.filter(recipient=profile, is_read=False).count()

        return JsonResponse({
            'status': 'success',
            'has_new_notifications': new_unviewed > 0 or new_feedback > 0 or new_candidates > 0 or new_internal > 0,
            'unviewed_requests': new_unviewed,
            'new_feedback': new_feedback,
            'new_candidates': new_candidates,
            'new_internal': new_internal,
            'total_new': new_unviewed + new_feedback + new_candidates + new_internal,
            'timestamp': timezone.now().isoformat()
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})
@login_required
def dashboard(request):
    try:
        profile = request.user.managerprofile
    except:
        from crm.models import ManagerProfile
        role = 'owner' if request.user.is_superuser else 'manager'
        profile = ManagerProfile.objects.create(
            user=request.user,
            role=role,
            corporate_email=request.user.email or f"{request.user.username}@argus.ru",
            phone=''
        )
        messages.info(request, f'Автоматически создан профиль менеджера с ролью "{profile.get_role_display()}"')

    if profile.role == 'owner':
        requests_qs = Request.objects.all().select_related('client', 'responsible_manager__user').order_by('-created_at')
    else:
        requests_qs = Request.objects.filter(responsible_manager=profile).select_related('client').order_by('-created_at')

    status_filter = request.GET.get('status')
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    # Получаем ID просмотренных заявок
    viewed_ids = ViewedRequest.objects.filter(user=request.user).values_list('request_id', flat=True)
    viewed_ids_list = list(viewed_ids)
    
    # Для отладки
    print(f"DEBUG: viewed_ids = {viewed_ids_list}")

    context = {
        'user': request.user,
        'profile': profile,
        'requests': requests_qs,
        'is_owner': profile.role == 'owner',
        'status_filter': status_filter,
        'viewed_ids': viewed_ids_list,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/requests_list.html', context, request=request)
        return HttpResponse(html)

    return render(request, 'crm/dashboard.html', context)
@login_required
def my_requests(request):
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('logout')

    if profile.role == 'owner':
        requests_list = Request.objects.all().select_related('client', 'responsible_manager__user').order_by('-created_at')
        managers = ManagerProfile.objects.filter(role='manager').select_related('user')
    else:
        requests_list = Request.objects.filter(responsible_manager=profile).select_related('client').order_by('-created_at')
        managers = None

    # ПОЛУЧАЕМ ID ПРОСМОТРЕННЫХ ЗАЯВОК
    viewed_ids = ViewedRequest.objects.filter(user=request.user).values_list('request_id', flat=True)

    page = request.GET.get('page', 1)
    paginator = Paginator(requests_list, 50)
    try:
        requests = paginator.page(page)
    except PageNotAnInteger:
        requests = paginator.page(1)
    except EmptyPage:
        requests = paginator.page(paginator.num_pages)

    return render(request, 'crm/my_requests.html', {
        'user': request.user,
        'profile': profile,
        'requests': requests,
        'managers': managers,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': requests,
        'paginator': paginator,
        'is_owner': profile.role == 'owner',
        'viewed_ids': list(viewed_ids),  # ДОБАВЛЯЕМ ЭТУ СТРОКУ
    })
@login_required
def request_detail(request, pk):
    req = get_object_or_404(Request, pk=pk)
    profile = getattr(request.user, 'managerprofile', None)

    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('crm_dashboard')

    if not is_owner(request.user) and req.responsible_manager != profile:
        messages.error(request, "У вас нет доступа к этой заявке.")
        return redirect('crm_dashboard')

    ViewedRequest.objects.get_or_create(user=request.user, request=req)
    
    managers = ManagerProfile.objects.filter(role="manager").select_related("user")

    if request.method == "POST":
        new_status = request.POST.get("status")
        comment_text = request.POST.get("comment")
        new_manager_id = request.POST.get("manager")

        if new_manager_id:
            new_manager_profile = ManagerProfile.objects.filter(id=new_manager_id).first()
            if new_manager_profile and req.responsible_manager != new_manager_profile:
                req.responsible_manager = new_manager_profile
                req.save(update_fields=["responsible_manager"])
                messages.success(request, f"Менеджер назначен: {new_manager_profile.user.get_full_name() or new_manager_profile.user.username}")
                _notify_manager_assignment(req)
                create_internal_notification(req, 'request_assigned', new_manager_profile)

        if new_status and new_status != req.status:
            old_status = req.get_status_display()
            req.status = new_status
            req.save(update_fields=["status"])
            _notify_client_status(req)
            create_internal_notification(req, 'status_changed')
            messages.success(request, f"Статус обновлён: {old_status} → {req.get_status_display()}")

        if comment_text:
            Comment.objects.create(request=req, author=profile, text=comment_text)
            create_internal_notification(req, 'new_comment')
            messages.success(request, "Комментарий добавлен.")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            comments = Comment.objects.filter(request=req).select_related('author').order_by('-created_at')
            html = render_to_string("crm/partials/comments_block.html", {"comments": comments}, request=request)
            return HttpResponse(html)

        return redirect('crm_request_detail', pk=req.pk)

    comments = Comment.objects.filter(request=req).select_related('author').order_by('-created_at')

    return render(request, 'crm/request_detail.html', {
        'user': request.user,
        'profile': profile,
        'req': req,
        'comments': comments,
        'managers': managers,
        'is_owner': profile.role == 'owner',
    })


def create_request(request):
    services = Service.objects.all()
    
    responsible_manager = None
    if request.user.is_authenticated:
        try:
            responsible_manager = request.user.managerprofile
        except:
            pass
    
    if request.method == "POST":
        try:
            phone = request.POST.get("phone", "").strip()
            normalized_phone = Client.normalize_phone(phone) if phone else None
            
            client = Client.objects.create(
                company_name=request.POST.get("company_name", "").strip(),
                contact_person=request.POST.get("contact_person", "").strip(),
                phone=normalized_phone if normalized_phone else phone,
                email=request.POST.get("email", "").strip() or None,
            )
            
            new_request = Request.objects.create(
                client=client,
                object_type=request.POST.get("object_type", "").strip(),
                object_address=request.POST.get("object_address", "").strip(),
                description=request.POST.get("description", "").strip(),
                status="new",
                responsible_manager=responsible_manager,
            )
            
            selected_services = request.POST.getlist('services')
            for service_id in selected_services:
                try:
                    service = Service.objects.get(id=service_id)
                    new_request.services.add(service)
                except Service.DoesNotExist:
                    continue
            
            messages.success(request, f'Заявка от {client.company_name} успешно создана!')
            
            _notify_owner_about_request(new_request)
            create_internal_notification(new_request, 'new_request')
            
            if responsible_manager:
                _notify_manager_assignment(new_request)
                create_internal_notification(new_request, 'request_assigned', responsible_manager)
            
            return redirect('crm_my_requests')
            
        except Exception as e:
            logger.error(f"Ошибка при создании заявки: {e}")
            messages.error(request, f'Ошибка при создании заявки: {str(e)}')
    
    return render(request, 'crm/create_request.html', {
        'current_user': request.user,
        'profile': getattr(request.user, 'managerprofile', None),
        'services': services,
    })


@login_required
def clients_list(request):
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('logout')

    clients_qs = Client.objects.all().order_by('company_name')
    search_query = request.GET.get('search', '')
    if search_query:
        clients_qs = clients_qs.filter(
            Q(company_name__icontains=search_query) |
            Q(contact_person__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    page = request.GET.get('page', 1)
    paginator = Paginator(clients_qs, 30)
    try:
        clients = paginator.page(page)
    except PageNotAnInteger:
        clients = paginator.page(1)
    except EmptyPage:
        clients = paginator.page(paginator.num_pages)

    context = {
        'user': request.user,
        'profile': profile,
        'clients': clients,
        'search_query': search_query,
        'is_owner': profile.role == 'owner',
        'is_paginated': paginator.num_pages > 1,
        'page_obj': clients,
        'paginator': paginator,
    }

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/clients_table.html', context, request=request)
        return HttpResponse(html)

    return render(request, 'crm/clients_list.html', context)


@login_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('crm_dashboard')
    if profile.role != 'owner':
        if not client.requests.filter(responsible_manager=profile).exists():
            messages.error(request, "У вас нет доступа к этому клиенту.")
            return redirect('crm_clients')

    if profile.role == 'owner':
        requests = client.requests.all().select_related('responsible_manager__user').order_by('-created_at')
    else:
        requests = client.requests.filter(responsible_manager=profile).select_related('responsible_manager__user').order_by('-created_at')

    context = {
        'user': request.user,
        'profile': profile,
        'client': client,
        'requests': requests,
        'is_owner': profile.role == 'owner',
    }
    return render(request, 'crm/client_detail.html', context)


@login_required
def client_create(request):
    profile = getattr(request.user, 'managerprofile', None)
    if not profile or profile.role != 'owner':
        messages.error(request, "Недостаточно прав для создания клиента")
        return redirect('crm_clients')
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            try:
                client = form.save()
                messages.success(request, f'Клиент "{client.company_name}" успешно создан')
                return redirect('crm_clients')
            except Exception as e:
                messages.error(request, f'Ошибка при создании клиента: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = ClientForm()
    context = {
        'form': form,
        'title': 'Создание клиента',
        'user': request.user,
        'profile': profile,
        'is_owner': profile.role == 'owner',
    }
    return render(request, 'crm/client_form.html', context)


@login_required
@require_POST
def client_update(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        client = get_object_or_404(Client, pk=pk)
        profile = getattr(request.user, 'managerprofile', None)
        if not profile or profile.role != 'owner':
            return JsonResponse({'status': 'error', 'error': 'Недостаточно прав'})
        client.company_name = request.POST.get('company_name')
        client.contact_person = request.POST.get('contact_person', '')
        client.phone = request.POST.get('phone')
        client.email = request.POST.get('email', '')
        try:
            client.save()
            return JsonResponse({
                'status': 'success',
                'client': {
                    'id': client.id,
                    'company_name': client.company_name,
                    'contact_person': client.contact_person,
                    'phone': client.phone,
                    'email': client.email,
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@require_POST
def client_delete(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        client = get_object_or_404(Client, pk=pk)
        profile = getattr(request.user, 'managerprofile', None)
        if not profile or profile.role != 'owner':
            return JsonResponse({'status': 'error', 'error': 'Недостаточно прав'})
        company_name = client.company_name
        client.delete()
        return JsonResponse({'status': 'success', 'message': f'Клиент "{company_name}" удален'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})

@login_required
def check_new_requests(request):
    """API для проверки новых заявок"""
    try:
        user = request.user
        profile = getattr(user, 'managerprofile', None)
        
        if not profile:
            return JsonResponse({
                'status': 'error',
                'error': 'No manager profile'
            })
        
        # Получаем все заявки в зависимости от роли
        if profile.role == 'owner':
            all_requests = Request.objects.all().select_related('client')
        else:
            all_requests = Request.objects.filter(responsible_manager=profile).select_related('client')
        
        # Получаем ID просмотренных заявок
        viewed_ids = ViewedRequest.objects.filter(user=user).values_list('request_id', flat=True)
        
        # Непросмотренные заявки
        unviewed_requests = all_requests.exclude(id__in=viewed_ids)
        unviewed_count = unviewed_requests.count()
        
        # Получаем новые заявки (для отображения)
        new_requests_data = []
        for req in unviewed_requests.order_by('-created_at')[:10]:
            new_requests_data.append({
                'id': req.id,
                'company_name': req.client.company_name,
                'object_type': req.object_type,
                'object_address': req.object_address or 'Не указан',
                'created_at': req.created_at.strftime('%d.%m.%Y %H:%M'),
                'status': req.status,
                'status_display': req.get_status_display(),
                'client_contact': req.client.contact_person or 'Не указан',
            })
        
        return JsonResponse({
            'status': 'success',
            'unviewed_requests_count': unviewed_count,
            'all_requests_count': all_requests.count(),
            'new_requests': new_requests_data,
            'last_check': timezone.now().isoformat(),
            'profile_role': profile.role
        })
        
    except Exception as e:
        logger.error(f"Ошибка check_new_requests: {e}")
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'unviewed_requests_count': 0,
            'new_requests': []
        })

@login_required
def mark_request_as_viewed(request, pk):
    """Отметить заявку как просмотренную"""
    try:
        req = get_object_or_404(Request, pk=pk)
        
        # Создаем запись о просмотре, если её нет
        viewed, created = ViewedRequest.objects.get_or_create(
            user=request.user, 
            request=req
        )
        
        # Обновляем время просмотра
        if not created:
            viewed.viewed_at = timezone.now()
            viewed.save()
        
        # Также обновляем глобальный счетчик в localStorage через ответ
        # Получаем общее количество непросмотренных заявок для этого пользователя
        profile = getattr(request.user, 'managerprofile', None)
        if profile:
            if profile.role == 'owner':
                all_requests = Request.objects.all()
            else:
                all_requests = Request.objects.filter(responsible_manager=profile)
            
            viewed_ids = ViewedRequest.objects.filter(user=request.user).values_list('request_id', flat=True)
            unviewed_count = all_requests.exclude(id__in=viewed_ids).count()
        else:
            unviewed_count = 0
        
        return JsonResponse({
            'status': 'success', 
            'message': f'Заявка #{req.id} отмечена как просмотренная',
            'unviewed_count': unviewed_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})
@login_required
def profile_view(request):
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('crm_dashboard')
    requests_stats = {}
    clients_count = 0
    if profile.role == 'manager':
        requests_stats = {
            'total_requests': Request.objects.filter(responsible_manager=profile).count(),
            'active_requests': Request.objects.filter(
                responsible_manager=profile,
                status__in=['new', 'in_progress']
            ).count(),
            'completed_requests': Request.objects.filter(
                responsible_manager=profile,
                status='completed'
            ).count(),
        }
        clients_count = Client.objects.filter(
            requests__responsible_manager=profile
        ).distinct().count()
    context = {
        'user': request.user,
        'profile': profile,
        'requests_stats': requests_stats,
        'clients_count': clients_count,
    }
    return render(request, 'crm/profile.html', context)


@login_required
@require_POST
def profile_update(request):
    try:
        user = request.user
        profile = getattr(user, 'managerprofile', None)
        if not profile:
            return JsonResponse({'status': 'error', 'error': 'Профиль менеджера не найден'})
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        profile.phone = request.POST.get('phone', '')
        profile.corporate_email = request.POST.get('corporate_email', '')
        profile.save()
        messages.success(request, 'Профиль успешно обновлен')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
    except Exception as e:
        error_msg = f'Ошибка при обновлении профиля: {str(e)}'
        messages.error(request, error_msg)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'error': error_msg})
    return redirect('crm_profile')


@login_required
@require_POST
def change_password(request):
    try:
        user = request.user
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        if not user.check_password(current_password):
            messages.error(request, 'Текущий пароль указан неверно')
            return redirect('crm_profile')
        if new_password != confirm_password:
            messages.error(request, 'Новые пароли не совпадают')
            return redirect('crm_profile')
        if len(new_password) < 6:
            messages.error(request, 'Пароль должен содержать минимум 6 символов')
            return redirect('crm_profile')
        user.set_password(new_password)
        user.save()
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        messages.success(request, 'Пароль успешно изменен')
    except Exception as e:
        messages.error(request, f'Ошибка при смене пароля: {str(e)}')
    return redirect('crm_profile')


@login_required
@user_passes_test(is_owner)
def managers_list(request):
    managers = ManagerProfile.objects.all().select_related('user').order_by('-created_at')
    context = {
        'current_user': request.user,
        'profile': request.user.managerprofile,
        'managers': managers,
        'active_tab': 'managers'
    }
    return render(request, 'crm/managers_list.html', context)


@login_required
@user_passes_test(is_owner)
def manager_create(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password')
        role = request.POST.get('role', 'manager')
        corporate_email = request.POST.get('corporate_email', '')
        phone = request.POST.get('phone', '')
        if not username or not email or not password:
            messages.error(request, 'Заполните все обязательные поля')
            return render(request, 'crm/manager_form.html', {
                'title': 'Создание менеджера',
                'active_tab': 'managers',
                'current_user': request.user,
                'profile': request.user.managerprofile,
            })
        try:
            if User.objects.filter(username=username).exists():
                messages.error(request, f'Пользователь с логином "{username}" уже существует')
                return render(request, 'crm/manager_form.html', {
                    'title': 'Создание менеджера',
                    'active_tab': 'managers',
                    'current_user': request.user,
                    'profile': request.user.managerprofile,
                })
            if User.objects.filter(email=email).exists():
                messages.error(request, f'Пользователь с email "{email}" уже существует')
                return render(request, 'crm/manager_form.html', {
                    'title': 'Создание менеджера',
                    'active_tab': 'managers',
                    'current_user': request.user,
                    'profile': request.user.managerprofile,
                })
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            manager_profile = ManagerProfile.objects.create(
                user=user,
                role=role,
                corporate_email=corporate_email,
                phone=phone
            )
            messages.success(request, f'Менеджер "{username}" успешно создан')
            return redirect('crm_managers_list')
        except Exception as e:
            if 'user' in locals():
                user.delete()
            messages.error(request, f'Ошибка при создании менеджера: {str(e)}')
    return render(request, 'crm/manager_form.html', {
        'title': 'Создание менеджера',
        'active_tab': 'managers',
        'current_user': request.user,
        'profile': request.user.managerprofile,
    })


@login_required
@user_passes_test(is_owner)
def manager_edit(request, manager_id):
    manager_profile = get_object_or_404(ManagerProfile, id=manager_id)
    user = manager_profile.user
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name', '')
        last_name = request.POST.get('last_name', '')
        password = request.POST.get('password')
        role = request.POST.get('role', 'manager')
        corporate_email = request.POST.get('corporate_email', '')
        phone = request.POST.get('phone', '')
        if not username or not email:
            messages.error(request, 'Заполните все обязательные поля')
            return render(request, 'crm/manager_form.html', {
                'manager_profile': manager_profile,
                'title': 'Редактирование менеджера',
                'active_tab': 'managers',
                'current_user': request.user,
                'profile': request.user.managerprofile,
            })
        try:
            user.username = username
            user.email = email
            user.first_name = first_name
            user.last_name = last_name
            if password:
                user.set_password(password)
            user.save()
            manager_profile.role = role
            manager_profile.corporate_email = corporate_email
            manager_profile.phone = phone
            manager_profile.save()
            messages.success(request, f'Менеджер "{username}" успешно обновлен')
            return redirect('crm_managers_list')
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении менеджера: {str(e)}')
    return render(request, 'crm/manager_form.html', {
        'manager_profile': manager_profile,
        'title': 'Редактирование менеджера',
        'active_tab': 'managers',
        'current_user': request.user,
        'profile': request.user.managerprofile,
    })


@login_required
@user_passes_test(is_owner)
def manager_detail(request, manager_id):
    manager_profile = get_object_or_404(ManagerProfile, id=manager_id)
    user = manager_profile.user
    requests_stats = Request.objects.filter(
        responsible_manager=manager_profile
    ).aggregate(
        total_requests=Count('id'),
        new_requests=Count('id', filter=Q(status='new')),
        in_progress_requests=Count('id', filter=Q(status='in_progress')),
        completed_requests=Count('id', filter=Q(status='completed')),
        rejected_requests=Count('id', filter=Q(status='rejected'))
    )
    recent_requests = Request.objects.filter(
        responsible_manager=manager_profile
    ).select_related('client').order_by('-created_at')[:10]
    context = {
        'manager_profile': manager_profile,
        'manager_user': user,
        'requests_stats': requests_stats,
        'recent_requests': recent_requests,
        'active_tab': 'managers',
        'current_user': request.user,
        'profile': request.user.managerprofile,
    }
    return render(request, 'crm/manager_detail.html', context)


@login_required
@user_passes_test(is_owner)
def manager_delete(request, manager_id):
    manager_profile = get_object_or_404(ManagerProfile, id=manager_id)
    if request.method == 'POST':
        username = manager_profile.user.username
        active_requests = Request.objects.filter(
            responsible_manager=manager_profile,
            status__in=['new', 'in_progress']
        ).exists()
        if active_requests:
            messages.error(request, 'Нельзя удалить менеджера с активными заявками')
            return redirect('crm_managers_list')
        try:
            manager_profile.user.delete()
            messages.success(request, f'Менеджер "{username}" успешно удален')
        except Exception as e:
            messages.error(request, f'Ошибка при удалении менеджера: {str(e)}')
        return redirect('crm_managers_list')
    return render(request, 'crm/manager_confirm_delete.html', {
        'manager_profile': manager_profile,
        'active_tab': 'managers',
        'current_user': request.user,
        'profile': request.user.managerprofile,
    })


@login_required
@user_passes_test(is_owner)
def reset_manager_password(request, manager_id):
    manager_profile = get_object_or_404(ManagerProfile, id=manager_id)
    user = manager_profile.user
    alphabet = string.ascii_letters + string.digits
    new_password = ''.join(secrets.choice(alphabet) for i in range(12))
    user.set_password(new_password)
    user.save()
    messages.success(request, f'Пароль для {user.username} сброшен. Новый пароль: {new_password}')
    return redirect('crm_manager_detail', manager_id=manager_id)


@login_required
@user_passes_test(is_owner)
def manager_toggle_active(request, manager_id):
    manager_profile = get_object_or_404(ManagerProfile, id=manager_id)
    user = manager_profile.user
    if request.method == 'POST':
        try:
            user.is_active = not user.is_active
            user.save()
            status = "активирован" if user.is_active else "заблокирован"
            messages.success(request, f'Менеджер "{user.username}" {status}')
        except Exception as e:
            messages.error(request, f'Ошибка при изменении статуса менеджера: {str(e)}')
    return redirect('crm_managers_list')


@login_required
def download_request_file(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if not req.attached_file:
        raise Http404("Файл не прикреплен к заявке")
    try:
        file_path = os.path.join(settings.MEDIA_ROOT, req.attached_file.name)
        if not os.path.exists(file_path):
            raise Http404("Файл не найден на сервере")
        file = open(file_path, 'rb')
        filename = os.path.basename(req.attached_file.name)
        response = FileResponse(file, as_attachment=True, filename=filename)
        response['Content-Type'] = 'application/octet-stream'
        return response
    except Exception as e:
        raise Http404("Ошибка при загрузке файла")


@login_required
@user_passes_test(is_owner)
def vacancies_list(request):
    vacancies = Vacancy.objects.all().order_by('-created_at')
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'active':
        vacancies = vacancies.filter(is_active=True)
    elif status_filter == 'inactive':
        vacancies = vacancies.filter(is_active=False)
    context = {
        'vacancies': vacancies,
        'status_filter': status_filter,
        'active_tab': 'vacancies'
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/vacancies_table.html', context, request=request)
        return HttpResponse(html)
    return render(request, 'crm/vacancies_list.html', context)


@login_required
@user_passes_test(is_owner)
def vacancy_create(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        salary = request.POST.get('salary')
        employment_type = request.POST.get('employment_type')
        experience = request.POST.get('experience')
        responsibilities = request.POST.get('responsibilities')
        requirements = request.POST.get('requirements')
        conditions = request.POST.get('conditions')
        is_active = request.POST.get('is_active') == 'on'
        if title:
            vacancy = Vacancy.objects.create(
                title=title,
                salary=salary,
                employment_type=employment_type,
                experience=experience,
                responsibilities=responsibilities,
                requirements=requirements,
                conditions=conditions,
                is_active=is_active
            )
            messages.success(request, f'Вакансия "{vacancy.title}" создана')
            return redirect('crm_vacancies_list')
        else:
            messages.error(request, 'Заполните название вакансии')
    return render(request, 'crm/vacancy_form.html', {
        'active_tab': 'vacancies',
        'title': 'Создание вакансии'
    })


@login_required
@user_passes_test(is_owner)
def vacancy_edit(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    if request.method == 'POST':
        title = request.POST.get('title')
        salary = request.POST.get('salary')
        employment_type = request.POST.get('employment_type')
        experience = request.POST.get('experience')
        responsibilities = request.POST.get('responsibilities')
        requirements = request.POST.get('requirements')
        conditions = request.POST.get('conditions')
        is_active = request.POST.get('is_active') == 'on'
        if title:
            vacancy.title = title
            vacancy.salary = salary
            vacancy.employment_type = employment_type
            vacancy.experience = experience
            vacancy.responsibilities = responsibilities
            vacancy.requirements = requirements
            vacancy.conditions = conditions
            vacancy.is_active = is_active
            vacancy.save()
            messages.success(request, f'Вакансия "{vacancy.title}" обновлена')
            return redirect('crm_vacancies_list')
        else:
            messages.error(request, 'Заполните название вакансии')
    return render(request, 'crm/vacancy_form.html', {
        'vacancy': vacancy,
        'active_tab': 'vacancies',
        'title': 'Редактирование вакансии'
    })


@login_required
@user_passes_test(is_owner)
def vacancy_toggle(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    vacancy.is_active = not vacancy.is_active
    vacancy.save()
    status = "активирована" if vacancy.is_active else "деактивирована"
    messages.success(request, f'Вакансия "{vacancy.title}" {status}')
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'is_active': vacancy.is_active})
    return redirect('crm_vacancies_list')


@login_required
@user_passes_test(is_owner)
def vacancy_delete(request, vacancy_id):
    vacancy = get_object_or_404(Vacancy, id=vacancy_id)
    if request.method == 'POST':
        title = vacancy.title
        vacancy.delete()
        messages.success(request, f'Вакансия "{title}" удалена')
        return redirect('crm_vacancies_list')
    return render(request, 'crm/vacancy_confirm_delete.html', {
        'vacancy': vacancy,
        'active_tab': 'vacancies'
    })


@login_required
@user_passes_test(is_owner)
def candidates_list(request):
    candidates = Candidate.objects.all().select_related('vacancy').order_by('-applied_at')
    vacancy_filter = request.GET.get('vacancy', 'all')
    if vacancy_filter != 'all':
        candidates = candidates.filter(vacancy_id=vacancy_filter)
    status_filter = request.GET.get('status', 'all')
    vacancies = Vacancy.objects.all()
    context = {
        'candidates': candidates,
        'vacancies': vacancies,
        'vacancy_filter': vacancy_filter,
        'status_filter': status_filter,
        'active_tab': 'candidates'
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/candidates_table.html', context, request=request)
        return HttpResponse(html)
    return render(request, 'crm/candidates_list.html', context)


@login_required
@user_passes_test(is_owner)
def candidate_detail(request, candidate_id):
    candidate = get_object_or_404(Candidate, id=candidate_id)
    if request.method == 'POST':
        admin_notes = request.POST.get('admin_notes')
        candidate.admin_notes = admin_notes
        candidate.save()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Заметки обновлены'})
        messages.success(request, 'Заметки обновлены')
        return redirect('crm_candidate_detail', candidate_id=candidate.id)
    context = {
        'candidate': candidate,
        'active_tab': 'candidates'
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/candidate_detail_content.html', context, request=request)
        return HttpResponse(html)
    return render(request, 'crm/candidate_detail.html', context)


@login_required
@user_passes_test(is_owner)
def candidate_delete(request, candidate_id):
    candidate = get_object_or_404(Candidate, id=candidate_id)
    if request.method == 'POST':
        name = candidate.name
        candidate.delete()
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': f'Кандидат "{name}" удален'})
        messages.success(request, f'Кандидат "{name}" удален')
        return redirect('crm_candidates_list')
    return render(request, 'crm/candidate_confirm_delete.html', {
        'candidate': candidate,
        'active_tab': 'candidates'
    })


@login_required
@user_passes_test(is_owner)
def check_new_candidates(request):
    try:
        last_check = request.GET.get('last_check')
        if last_check:
            last_check_time = timezone.datetime.fromisoformat(last_check.replace('Z', '+00:00'))
            new_candidates = Candidate.objects.filter(
                applied_at__gt=last_check_time
            ).select_related('vacancy').order_by('-applied_at')
        else:
            new_candidates = Candidate.objects.none()
        new_candidates_data = []
        for candidate in new_candidates:
            new_candidates_data.append({
                'id': candidate.id,
                'name': candidate.name,
                'phone': candidate.phone_number,
                'vacancy': candidate.vacancy.title,
                'applied_at': candidate.applied_at.strftime('%d.%m.%Y %H:%M'),
                'has_comment': bool(candidate.comment),
                'comment': candidate.comment or ''
            })
        response_data = {
            'new_candidates_count': len(new_candidates),
            'new_candidates': new_candidates_data,
            'last_check': timezone.now().isoformat(),
            'status': 'success'
        }
    except Exception as e:
        response_data = {
            'new_candidates_count': 0,
            'new_candidates': [],
            'last_check': timezone.now().isoformat(),
            'status': 'error',
            'error': str(e)
        }
    return JsonResponse(response_data)


@login_required
@require_POST
def change_request_status(request):
    request_id = request.POST.get('request_id')
    new_status = request.POST.get('new_status')
    comment = request.POST.get('comment', '')
    try:
        req = Request.objects.get(id=request_id)
        if req.responsible_manager != request.user.managerprofile and not is_owner(request.user):
            return JsonResponse({'status': 'error', 'error': 'Нет прав на изменение этой заявки'})
        req.status = new_status
        req.save()
        create_internal_notification(req, 'status_changed')
        if comment:
            Comment.objects.create(
                request=req,
                author=request.user.managerprofile,
                text=comment
            )
            create_internal_notification(req, 'new_comment')
        return JsonResponse({'status': 'success'})
    except Request.DoesNotExist:
        return JsonResponse({'status': 'error', 'error': 'Заявка не найдена'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@login_required
@require_POST
def delete_request(request, pk):
    try:
        req = get_object_or_404(Request, pk=pk)
        profile = request.user.managerprofile
        if profile.role != 'owner' and req.responsible_manager != profile:
            return JsonResponse({'status': 'error', 'error': 'У вас нет прав для удаления этой заявки'})
        company_name = req.client.company_name
        req.delete()
        return JsonResponse({'status': 'success', 'message': f'Заявка "{company_name}" успешно удалена'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})

@login_required
@require_POST
def mark_all_viewed(request):
    """Отметить все заявки как просмотренные"""
    try:
        user = request.user
        profile = getattr(user, 'managerprofile', None)
        
        if not profile:
            return JsonResponse({'status': 'error', 'error': 'User has no manager profile'})
        
        if profile.role == 'owner':
            user_requests = Request.objects.all()
        else:
            user_requests = Request.objects.filter(responsible_manager=profile)
        
        viewed_count = 0
        for req in user_requests:
            obj, created = ViewedRequest.objects.get_or_create(user=user, request=req)
            if created:
                viewed_count += 1
            else:
                # Обновляем время просмотра
                obj.viewed_at = timezone.now()
                obj.save()
        
        return JsonResponse({
            'status': 'success',
            'message': f'{viewed_count} заявок отмечено как просмотренные',
            'viewed_count': viewed_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})

@login_required
@user_passes_test(is_owner)
def assign_manager(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if request.method == "POST":
        manager_id = request.POST.get("manager_id")
        if not manager_id:
            messages.error(request, "Не выбран менеджер.")
            return redirect("crm_request_detail", pk=req.pk)
        manager_profile = get_object_or_404(ManagerProfile, pk=manager_id)
        req.responsible_manager = manager_profile
        req.status = "in_progress"
        req.save(update_fields=["responsible_manager", "status"])
        _notify_manager_assignment(req)
        create_internal_notification(req, 'request_assigned', manager_profile)
        messages.success(request, f"Менеджер {manager_profile.user.get_full_name() or manager_profile.user.username} назначен.")
        return redirect("crm_my_requests")
    managers = ManagerProfile.objects.filter(role="manager").select_related("user")
    return render(request, "crm/assign_manager.html", {
        'user': request.user,
        'profile': request.user.managerprofile,
        "req": req,
        "managers": managers
    })


@login_required
def projects_list(request):
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('logout')
    projects_qs = Project.objects.all().order_by('-created_at')
    type_filter = request.GET.get('type', 'all')
    if type_filter != 'all':
        projects_qs = projects_qs.filter(object_type=type_filter)
    search_query = request.GET.get('search', '')
    if search_query:
        projects_qs = projects_qs.filter(
            Q(title__icontains=search_query) |
            Q(address__icontains=search_query)
        )
    types_stats = {
        'all': Project.objects.count(),
        'residential': Project.objects.filter(object_type='residential').count(),
        'commercial': Project.objects.filter(object_type='commercial').count(),
        'social': Project.objects.filter(object_type='social').count(),
        'other': Project.objects.filter(object_type='other').count(),
    }
    context = {
        'user': request.user,
        'profile': profile,
        'projects': projects_qs,
        'type_filter': type_filter,
        'search_query': search_query,
        'types_stats': types_stats,
        'is_owner': profile.role == 'owner',
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/projects_list.html', context, request=request)
        return HttpResponse(html)
    return render(request, 'crm/projects_list.html', context)


@login_required
@user_passes_test(is_owner)
def cleanup_projects(request):
    projects = Project.objects.all()
    for project in projects:
        try:
            if project.image and hasattr(project.image, 'path'):
                if not os.path.exists(project.image.path):
                    project.image = None
                    project.save()
        except Exception:
            project.image = None
            project.save()
    messages.success(request, "Проекты очищены от битых изображений")
    return redirect('crm_projects')


def fix_existing_projects(request):
    projects = Project.objects.all()
    for project in projects:
        if project.image and project.image.name:
            try:
                if not os.path.exists(project.image.path):
                    project.image = None
                    project.save()
            except Exception:
                project.image = None
                project.save()
    messages.success(request, "Проекты исправлены")
    return redirect('crm_projects')


@login_required
def project_create(request):
    profile = getattr(request.user, 'managerprofile', None)
    if not profile or profile.role != 'owner':
        messages.error(request, "Недостаточно прав для создания проекта")
        return redirect('crm_projects')
    if request.method == 'POST':
        try:
            title = request.POST.get('title', '').strip()
            object_type = request.POST.get('object_type', '').strip()
            address = request.POST.get('address', '').strip()
            if not all([title, object_type]):
                messages.error(request, "Заполните все обязательные поля")
                return render(request, 'crm/project_form.html')
            project = Project(title=title, object_type=object_type, address=address)
            if 'image' in request.FILES:
                image_file = request.FILES['image']
                if image_file.size > 10 * 1024 * 1024:
                    messages.error(request, "Размер изображения не должен превышать 10MB")
                    return render(request, 'crm/project_form.html')
                ext = os.path.splitext(image_file.name)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                project.image.save(filename, image_file)
            else:
                project.save()
            messages.success(request, f'Проект "{project.title}" успешно создан')
            return redirect('crm_projects')
        except Exception as e:
            messages.error(request, f'Ошибка при создании проекта: {str(e)}')
    return render(request, 'crm/project_form.html')


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('crm_dashboard')
    context = {
        'user': request.user,
        'profile': profile,
        'project': project,
        'is_owner': profile.role == 'owner',
    }
    return render(request, 'crm/project_detail.html', context)


@login_required
@require_POST
def project_update(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        project = get_object_or_404(Project, pk=pk)
        profile = getattr(request.user, 'managerprofile', None)
        if not profile or profile.role != 'owner':
            return JsonResponse({'status': 'error', 'error': 'Недостаточно прав'})
        project.title = request.POST.get('title')
        project.object_type = request.POST.get('object_type')
        project.address = request.POST.get('address', '')
        if 'image' in request.FILES:
            project.image = request.FILES['image']
        try:
            project.save()
            return JsonResponse({
                'status': 'success',
                'project': {
                    'id': project.id,
                    'title': project.title,
                    'object_type': project.object_type,
                    'object_type_display': project.get_object_type_display(),
                    'address': project.address,
                    'image_url': project.image.url if project.image else '',
                    'created_at': project.created_at.strftime('%d.%m.%Y'),
                }
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@require_POST
def project_delete(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        project = get_object_or_404(Project, pk=pk)
        profile = getattr(request.user, 'managerprofile', None)
        if not profile or profile.role != 'owner':
            return JsonResponse({'status': 'error', 'error': 'Недостаточно прав'})
        title = project.title
        project.delete()
        return JsonResponse({'status': 'success', 'message': f'Проект "{title}" удален'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
def project_edit(request, pk):
    project = get_object_or_404(Project, pk=pk)
    profile = getattr(request.user, 'managerprofile', None)
    if not profile or profile.role != 'owner':
        messages.error(request, "Недостаточно прав для редактирования проекта")
        return redirect('crm_projects')
    if request.method == 'POST':
        try:
            project.title = request.POST.get('title', '').strip()
            project.description = request.POST.get('description', '').strip()
            project.object_type = request.POST.get('object_type', '').strip()
            project.address = request.POST.get('address', '').strip()
            if not all([project.title, project.description, project.object_type]):
                messages.error(request, "Заполните все обязательные поля")
                return render(request, 'crm/project_form.html', {'project': project})
            if request.POST.get('remove_current_image') == 'true':
                if project.image:
                    project.image.delete(save=False)
                    project.image = None
            if 'image' in request.FILES:
                image_file = request.FILES['image']
                if image_file.size > 10 * 1024 * 1024:
                    messages.error(request, "Размер изображения не должен превышать 10MB")
                    return render(request, 'crm/project_form.html', {'project': project})
                ext = os.path.splitext(image_file.name)[1]
                filename = f"{uuid.uuid4().hex}{ext}"
                project.image.save(filename, image_file)
            project.save()
            messages.success(request, f'Проект "{project.title}" успешно обновлен')
            return redirect('crm_project_detail', pk=project.id)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении проекта: {str(e)}')
    context = {
        'user': request.user,
        'profile': profile,
        'project': project,
        'is_owner': profile.role == 'owner',
    }
    return render(request, 'crm/project_form.html', context)


@login_required
def feedback_list(request):
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('logout')
    feedbacks_qs = Feedback.objects.all().order_by('-created_at')
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        feedbacks_qs = feedbacks_qs.filter(status=status_filter)
    search_query = request.GET.get('search', '')
    if search_query:
        feedbacks_qs = feedbacks_qs.filter(
            Q(name__icontains=search_query) |
            Q(contact__icontains=search_query) |
            Q(message__icontains=search_query)
        )
    page = request.GET.get('page', 1)
    paginator = Paginator(feedbacks_qs, 20)
    try:
        feedbacks = paginator.page(page)
    except PageNotAnInteger:
        feedbacks = paginator.page(1)
    except EmptyPage:
        feedbacks = paginator.page(paginator.num_pages)
    context = {
        'user': request.user,
        'profile': profile,
        'feedbacks': feedbacks,
        'status_filter': status_filter,
        'search_query': search_query,
        'is_owner': profile.role == 'owner',
        'is_paginated': paginator.num_pages > 1,
        'page_obj': feedbacks,
        'paginator': paginator,
    }
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/feedback_list.html', context, request=request)
        return HttpResponse(html)
    return render(request, 'crm/feedback_list.html', context)


@login_required
def feedback_detail(request, pk):
    feedback = get_object_or_404(Feedback, pk=pk)
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('crm_dashboard')
    if not feedback.is_viewed:
        feedback.is_viewed = True
        feedback.save(update_fields=['is_viewed'])
    if request.method == "POST":
        new_status = request.POST.get("status")
        admin_notes = request.POST.get("admin_notes", "")
        if new_status and new_status != feedback.status:
            old_status = feedback.get_status_display()
            feedback.status = new_status
            feedback.save(update_fields=["status"])
            messages.success(request, f"Статус обновлён: {old_status} → {feedback.get_status_display()}")
        return redirect('crm_feedback_detail', pk=feedback.pk)
    return render(request, 'crm/feedback_detail.html', {
        'user': request.user,
        'profile': profile,
        'feedback': feedback,
        'is_owner': profile.role == 'owner',
    })


@login_required
@require_POST
def feedback_update_status(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        feedback = get_object_or_404(Feedback, pk=pk)
        profile = getattr(request.user, 'managerprofile', None)
        if not profile:
            return JsonResponse({'status': 'error', 'error': 'Недостаточно прав'})
        new_status = request.POST.get('status')
        if new_status and new_status in dict(Feedback.STATUS_CHOICES):
            feedback.status = new_status
            feedback.save(update_fields=['status'])
            return JsonResponse({
                'status': 'success',
                'new_status': feedback.status,
                'new_status_display': feedback.get_status_display()
            })
        return JsonResponse({'status': 'error', 'error': 'Неверный статус'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@require_POST
def feedback_delete(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        feedback = get_object_or_404(Feedback, pk=pk)
        profile = getattr(request.user, 'managerprofile', None)
        if not profile:
            return JsonResponse({'status': 'error', 'error': 'Недостаточно прав'})
        name = feedback.name
        feedback.delete()
        return JsonResponse({'status': 'success', 'message': f'Сообщение от "{name}" удалено'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@require_POST
def feedback_mark_all_viewed(request):
    try:
        profile = getattr(request.user, 'managerprofile', None)
        if not profile:
            return JsonResponse({'status': 'error', 'error': 'Недостаточно прав'})
        updated_count = Feedback.objects.filter(is_viewed=False).update(is_viewed=True)
        return JsonResponse({
            'status': 'success',
            'message': f'{updated_count} сообщений отмечены как просмотренные',
            'updated_count': updated_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@login_required
def check_new_feedback(request):
    try:
        profile = getattr(request.user, 'managerprofile', None)
        if not profile:
            return JsonResponse({
                'unviewed_feedback_count': 0,
                'all_feedback_count': 0,
                'new_feedback': [],
                'status': 'error',
                'error': 'User has no manager profile'
            })
        all_feedback_count = Feedback.objects.count()
        unviewed_feedback_count = Feedback.objects.filter(is_viewed=False).count()
        new_feedback_data = []
        if unviewed_feedback_count > 0:
            new_feedback = Feedback.objects.filter(is_viewed=False).order_by('-created_at')[:5]
            for fb in new_feedback:
                new_feedback_data.append({
                    'id': fb.id,
                    'name': fb.name,
                    'contact': fb.contact,
                    'message_preview': fb.message[:100] + '...' if len(fb.message) > 100 else fb.message,
                    'status': fb.status,
                    'status_display': fb.get_status_display(),
                    'created_at': fb.created_at.strftime('%d.%m.%Y %H:%M'),
                })
        return JsonResponse({
            'all_feedback_count': all_feedback_count,
            'unviewed_feedback_count': unviewed_feedback_count,
            'new_feedback': new_feedback_data,
            'last_check': timezone.now().isoformat(),
            'status': 'success',
        })
    except Exception as e:
        return JsonResponse({
            'unviewed_feedback_count': 0,
            'all_feedback_count': 0,
            'new_feedback': [],
            'last_check': timezone.now().isoformat(),
            'status': 'error',
            'error': str(e)
        })


@login_required
@user_passes_test(is_owner)
def services_list(request):
    services = Service.objects.all().order_by('id')
    context = {
        'services': services,
        'user': request.user,
        'profile': request.user.managerprofile,
        'active_tab': 'services'
    }
    return render(request, 'crm/services_list.html', context)


@login_required
@user_passes_test(is_owner)
def service_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        has_kp = request.POST.get('has_kp') == 'on'
        if not name:
            messages.error(request, 'Введите название услуги')
            return redirect('crm_services')
        try:
            service = Service.objects.create(name=name, has_kp=has_kp)
            messages.success(request, f'Услуга "{service.name}" создана')
            return redirect('crm_services')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
    return render(request, 'crm/service_form.html', {
        'title': 'Создание услуги',
        'user': request.user,
        'profile': request.user.managerprofile,
    })


@login_required
@user_passes_test(is_owner)
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        has_kp = request.POST.get('has_kp') == 'on'
        if not name:
            messages.error(request, 'Введите название услуги')
            return redirect('crm_services')
        try:
            service.name = name
            service.has_kp = has_kp
            service.save()
            messages.success(request, f'Услуга "{service.name}" обновлена')
            return redirect('crm_services')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
    return render(request, 'crm/service_form.html', {
        'service': service,
        'title': 'Редактирование услуги',
        'user': request.user,
        'profile': request.user.managerprofile,
    })


@login_required
@user_passes_test(is_owner)
def service_delete(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        service = get_object_or_404(Service, pk=pk)
        name = service.name
        service.delete()
        return JsonResponse({'status': 'success', 'message': f'Услуга "{name}" удалена'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'}, status=400)


@login_required
@user_passes_test(is_owner)
def service_toggle_kp(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        service = get_object_or_404(Service, pk=pk)
        service.has_kp = not service.has_kp
        service.save()
        return JsonResponse({
            'status': 'success',
            'has_kp': service.has_kp,
            'message': f'Услуга {"включена" if service.has_kp else "выключена"} в КП'
        })
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'}, status=400)


@login_required
@user_passes_test(is_owner)
def crm_promo_blocks(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'create':
                promo = PromoBlock.objects.create(
                    title=request.POST.get('title', ''),
                    text=request.POST.get('text', ''),
                    image=request.FILES.get('image'),
                    video_url=request.POST.get('video_url', ''),
                    button_text=request.POST.get('button_text', ''),
                    button_url=request.POST.get('button_url', ''),
                    layout=request.POST.get('layout', 'text_left'),
                    text_align=request.POST.get('text_align', 'left'),
                    content_position=request.POST.get('content_position', 'center'),
                    background_color=request.POST.get('background_color', '#1E3A8A'),
                    text_color=request.POST.get('text_color', '#FFFFFF'),
                    button_color=request.POST.get('button_color', '#C9A96A'),
                    button_text_color=request.POST.get('button_text_color', '#FFFFFF'),
                    font_family=request.POST.get('font_family', 'inter'),
                    title_font_size=int(request.POST.get('title_font_size', 24)),
                    text_font_size=int(request.POST.get('text_font_size', 16)),
                    button_font_size=int(request.POST.get('button_font_size', 16)),
                    block_width=request.POST.get('block_width', '100%'),
                    block_height=int(request.POST.get('block_height', 300)),
                    padding_top=int(request.POST.get('padding_top', 40)),
                    padding_bottom=int(request.POST.get('padding_bottom', 40)),
                    padding_left=int(request.POST.get('padding_left', 40)),
                    padding_right=int(request.POST.get('padding_right', 40)),
                    border_radius=int(request.POST.get('border_radius', 12)),
                    shadow_effect=request.POST.get('shadow_effect') == 'true',
                    background_gradient=request.POST.get('background_gradient') == 'true',
                    gradient_start=request.POST.get('gradient_start', '#1E3A8A'),
                    gradient_end=request.POST.get('gradient_end', '#3B82F6'),
                    gradient_angle=int(request.POST.get('gradient_angle', 135)),
                    use_image_as_background=request.POST.get('use_image_as_background') == 'true',
                    background_overlay=request.POST.get('background_overlay') == 'true',
                    overlay_color=request.POST.get('overlay_color', '#000000'),
                    background_overlay_opacity=float(request.POST.get('background_overlay_opacity', 0.5)),
                    is_active=request.POST.get('is_active') == 'true',
                    start_date=request.POST.get('start_date') or None,
                    end_date=request.POST.get('end_date') or None,
                )
                messages.success(request, f'Промо-блок "{promo.title}" создан')
            elif action == 'edit':
                promo_id = request.POST.get('promo_id')
                promo = get_object_or_404(PromoBlock, id=promo_id)
                fields_to_update = ['title', 'text', 'video_url', 'button_text', 'button_url',
                    'layout', 'text_align', 'content_position', 'background_color',
                    'text_color', 'button_color', 'button_text_color', 'font_family',
                    'block_width', 'background_overlay_opacity', 'overlay_color',
                    'gradient_start', 'gradient_end']
                for field in fields_to_update:
                    if field in request.POST:
                        setattr(promo, field, request.POST.get(field))
                numeric_fields = ['title_font_size', 'text_font_size', 'button_font_size',
                    'block_height', 'padding_top', 'padding_bottom', 'padding_left',
                    'padding_right', 'border_radius', 'gradient_angle']
                for field in numeric_fields:
                    if request.POST.get(field):
                        setattr(promo, field, int(request.POST.get(field)))
                promo.shadow_effect = request.POST.get('shadow_effect') == 'true'
                promo.background_gradient = request.POST.get('background_gradient') == 'true'
                promo.use_image_as_background = request.POST.get('use_image_as_background') == 'true'
                promo.background_overlay = request.POST.get('background_overlay') == 'true'
                promo.is_active = request.POST.get('is_active') == 'true'
                if 'image' in request.FILES:
                    promo.image = request.FILES['image']
                promo.start_date = request.POST.get('start_date') or None
                promo.end_date = request.POST.get('end_date') or None
                promo.save()
                messages.success(request, f'Промо-блок "{promo.title}" обновлен')
            elif action == 'toggle':
                promo_id = request.POST.get('promo_id')
                promo = get_object_or_404(PromoBlock, id=promo_id)
                promo.is_active = not promo.is_active
                promo.save()
                status = "активирован" if promo.is_active else "деактивирован"
                messages.success(request, f'Промо-блок "{promo.title}" {status}')
            elif action == 'delete':
                promo_id = request.POST.get('promo_id')
                promo = get_object_or_404(PromoBlock, id=promo_id)
                title = promo.title
                promo.delete()
                messages.success(request, f'Промо-блок "{title}" удален')
            return redirect('crm_promo_blocks')
        except Exception as e:
            messages.error(request, f'Ошибка: {str(e)}')
            return redirect('crm_promo_blocks')

    promo_blocks = PromoBlock.objects.all().order_by('-created_at')
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'active':
        promo_blocks = promo_blocks.filter(is_active=True)
    elif status_filter == 'inactive':
        promo_blocks = promo_blocks.filter(is_active=False)
    search_query = request.GET.get('search', '')
    if search_query:
        promo_blocks = promo_blocks.filter(
            Q(title__icontains=search_query) |
            Q(text__icontains=search_query)
        )
    context = {
        'promo_blocks': promo_blocks,
        'status_filter': status_filter,
        'search_query': search_query,
        'holiday_templates': get_holiday_templates(),
        'active_tab': 'promo_blocks'
    }
    return render(request, 'crm/promo_blocks.html', context)


def get_holiday_templates():
    return {
        'new_year': {'name': 'Новый Год', 'colors': ['#1a472a', '#2d5a27', '#ffffff'], 'description': 'Праздничный дизайн для новогодних акций'},
        'christmas': {'name': 'Рождество', 'colors': ['#1e3a8a', '#dc2626', '#ffffff'], 'description': 'Традиционные рождественские цвета'},
        'valentine': {'name': 'День Святого Валентина', 'colors': ['#dc2626', '#fecaca', '#ffffff'], 'description': 'Романтичный дизайн для Дня влюбленных'},
        'womens_day': {'name': '8 Марта', 'colors': ['#ec4899', '#fbcfe8', '#ffffff'], 'description': 'Нежный дизайн к Международному женскому дню'},
        'defenders_day': {'name': '23 Февраля', 'colors': ['#1e3a8a', '#60a5fa', '#ffffff'], 'description': 'Тематический дизайн ко Дню защитника Отечества'},
        'easter': {'name': 'Пасха', 'colors': ['#fef3c7', '#d97706', '#ffffff'], 'description': 'Светлый дизайн для пасхальных праздников'},
        'halloween': {'name': 'Хэллоуин', 'colors': ['#7c2d12', '#f59e0b', '#000000'], 'description': 'Тематический дизайн для Хэллоуина'},
        'birthday': {'name': 'День Рождения', 'colors': ['#ec4899', '#8b5cf6', '#ffffff'], 'description': 'Яркий дизайн для поздравлений с Днем рождения'},
        'summer_sale': {'name': 'Летние скидки', 'colors': ['#f59e0b', '#fbbf24', '#ffffff'], 'description': 'Яркий летний дизайн для акций и распродаж'},
        'winter_sale': {'name': 'Зимние скидки', 'colors': ['#60a5fa', '#bfdbfe', '#ffffff'], 'description': 'Зимний дизайн для сезонных распродаж'}
    }


def get_holiday_template(template_name):
    templates = {
        'new_year': {
            'background_color': '#1a472a', 'text_color': '#ffffff', 'button_color': '#dc2626',
            'button_text_color': '#ffffff', 'font_family': 'montserrat', 'title_font_size': 28,
            'layout': 'text_overlay', 'background_gradient': True, 'gradient_start': '#1a472a', 'gradient_end': '#2d5a27'
        },
        'valentine': {
            'background_color': '#dc2626', 'text_color': '#ffffff', 'button_color': '#fecaca',
            'button_text_color': '#dc2626', 'font_family': 'lora', 'title_font_size': 26, 'layout': 'text_left'
        },
        'womens_day': {
            'background_color': '#ec4899', 'text_color': '#ffffff', 'button_color': '#fbcfe8',
            'button_text_color': '#ec4899', 'font_family': 'playfair', 'title_font_size': 26, 'layout': 'text_right'
        },
        'defenders_day': {
            'background_color': '#1e3a8a', 'text_color': '#ffffff', 'button_color': '#60a5fa',
            'button_text_color': '#ffffff', 'font_family': 'ubuntu', 'title_font_size': 24, 'layout': 'text_left'
        },
        'summer_sale': {
            'background_gradient': True, 'gradient_start': '#f59e0b', 'gradient_end': '#fbbf24',
            'text_color': '#7c2d12', 'button_color': '#dc2626', 'button_text_color': '#ffffff',
            'font_family': 'inter', 'title_font_size': 28, 'layout': 'text_center'
        }
    }
    return templates.get(template_name, {})


@login_required
@user_passes_test(is_owner)
def quick_promo_create(request):
    if request.method == 'POST':
        try:
            template_name = request.POST.get('template')
            title = request.POST.get('title', '')
            text = request.POST.get('text', '')
            button_text = request.POST.get('button_text', 'Узнать больше')
            button_url = request.POST.get('button_url', '')
            promo_data = {'title': title, 'text': text, 'button_text': button_text, 'button_url': button_url, 'is_active': True}
            if template_name and template_name != 'custom':
                template_settings = get_holiday_template(template_name)
                promo_data.update(template_settings)
            promo = PromoBlock.objects.create(**promo_data)
            messages.success(request, f'Промо-блок "{promo.title}" создан за 1 клик!')
            return redirect('crm_promo_blocks')
        except Exception as e:
            messages.error(request, f'Ошибка при создании: {str(e)}')
    return render(request, 'crm/quick_promo_create.html', {
        'holiday_templates': get_holiday_templates(),
        'active_tab': 'promo_blocks'
    })


@login_required
@user_passes_test(is_owner)
def promo_block_preview(request, pk):
    promo = get_object_or_404(PromoBlock, pk=pk)
    return render(request, 'crm/promo_block_preview.html', {'promo': promo, 'active_tab': 'promo_blocks'})


@login_required
@user_passes_test(is_owner)
def duplicate_promo_block(request, pk):
    original = get_object_or_404(PromoBlock, pk=pk)
    promo_copy = PromoBlock.objects.create(
        title=f"{original.title} (копия)", text=original.text, image=original.image,
        video_url=original.video_url, button_text=original.button_text, button_url=original.button_url,
        layout=original.layout, text_align=original.text_align, content_position=original.content_position,
        background_color=original.background_color, text_color=original.text_color,
        button_color=original.button_color, button_text_color=original.button_text_color,
        font_family=original.font_family, title_font_size=original.title_font_size,
        text_font_size=original.text_font_size, button_font_size=original.button_font_size,
        block_width=original.block_width, block_height=original.block_height,
        padding_top=original.padding_top, padding_bottom=original.padding_bottom,
        padding_left=original.padding_left, padding_right=original.padding_right,
        border_radius=original.border_radius, shadow_effect=original.shadow_effect,
        background_gradient=original.background_gradient, gradient_start=original.gradient_start,
        gradient_end=original.gradient_end, gradient_angle=original.gradient_angle,
        use_image_as_background=original.use_image_as_background, background_overlay=original.background_overlay,
        overlay_color=original.overlay_color, background_overlay_opacity=original.background_overlay_opacity,
        is_active=False, start_date=original.start_date, end_date=original.end_date,
    )
    messages.success(request, f'Промо-блок "{original.title}" скопирован')
    return redirect('crm_promo_blocks')


@login_required
@user_passes_test(is_owner)
def promo_block_edit(request, pk):
    promo = get_object_or_404(PromoBlock, pk=pk)
    if request.method == 'POST':
        try:
            promo.title = request.POST.get('title', '')
            promo.text = request.POST.get('text', '')
            promo.video_url = request.POST.get('video_url', '')
            promo.button_text = request.POST.get('button_text', '')
            promo.button_url = request.POST.get('button_url', '')
            promo.layout = request.POST.get('layout', 'text_left')
            promo.text_align = request.POST.get('text_align', 'left')
            promo.content_position = request.POST.get('content_position', 'center')
            promo.background_color = request.POST.get('background_color', '#1E3A8A')
            promo.text_color = request.POST.get('text_color', '#FFFFFF')
            promo.button_color = request.POST.get('button_color', '#C9A96A')
            promo.button_text_color = request.POST.get('button_text_color', '#FFFFFF')
            promo.overlay_color = request.POST.get('overlay_color', '#000000')
            promo.font_family = request.POST.get('font_family', 'inter')
            promo.title_font_size = int(request.POST.get('title_font_size', 24))
            promo.text_font_size = int(request.POST.get('text_font_size', 16))
            promo.button_font_size = int(request.POST.get('button_font_size', 16))
            promo.block_width = request.POST.get('block_width', '100%')
            promo.block_height = int(request.POST.get('block_height', 300))
            promo.padding_top = int(request.POST.get('padding_top', 40))
            promo.padding_bottom = int(request.POST.get('padding_bottom', 40))
            promo.padding_left = int(request.POST.get('padding_left', 40))
            promo.padding_right = int(request.POST.get('padding_right', 40))
            promo.border_radius = int(request.POST.get('border_radius', 12))
            promo.shadow_effect = request.POST.get('shadow_effect') == 'true'
            promo.background_gradient = request.POST.get('background_gradient') == 'true'
            promo.gradient_start = request.POST.get('gradient_start', '#1E3A8A')
            promo.gradient_end = request.POST.get('gradient_end', '#3B82F6')
            promo.gradient_angle = int(request.POST.get('gradient_angle', 135))
            promo.use_image_as_background = request.POST.get('use_image_as_background') == 'true'
            promo.background_overlay = request.POST.get('background_overlay') == 'true'
            promo.background_overlay_opacity = float(request.POST.get('background_overlay_opacity', 0.5))
            promo.is_active = request.POST.get('is_active') == 'true'
            start_date = request.POST.get('start_date', '')
            end_date = request.POST.get('end_date', '')
            promo.start_date = timezone.datetime.fromisoformat(start_date) if start_date else None
            promo.end_date = timezone.datetime.fromisoformat(end_date) if end_date else None
            if 'image' in request.FILES:
                if promo.image:
                    promo.image.delete(save=False)
                promo.image = request.FILES['image']
            elif request.POST.get('remove_image') == 'true':
                if promo.image:
                    promo.image.delete(save=False)
                    promo.image = None
            promo.save()
            messages.success(request, f'Промо-блок "{promo.title}" успешно обновлен')
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success', 'message': 'Промо-блок обновлен', 'promo_id': promo.id})
            return redirect('crm_promo_blocks')
        except Exception as e:
            error_msg = f'Ошибка при обновлении: {str(e)}'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'error': error_msg})
            messages.error(request, error_msg)
    context = {
        'promo': promo,
        'holiday_templates': get_holiday_templates(),
        'active_tab': 'promo_blocks',
        'edit_mode': True
    }
    return render(request, 'crm/promo_block_form.html', context)


@login_required
@user_passes_test(is_owner)
def promo_block_quick_edit(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        promo = get_object_or_404(PromoBlock, pk=pk)
        try:
            field = request.POST.get('field')
            value = request.POST.get('value')
            if field and hasattr(promo, field):
                if field in ['title', 'text', 'button_text', 'button_url', 'video_url']:
                    setattr(promo, field, value)
                elif field == 'is_active':
                    setattr(promo, field, value == 'true')
                elif field in ['title_font_size', 'text_font_size', 'button_font_size', 'block_height', 'border_radius']:
                    setattr(promo, field, int(value))
                elif field == 'background_overlay_opacity':
                    setattr(promo, field, float(value))
                else:
                    setattr(promo, field, value)
                promo.save()
                return JsonResponse({'status': 'success', 'message': f'Поле {field} обновлено', 'new_value': getattr(promo, field)})
            else:
                return JsonResponse({'status': 'error', 'error': f'Поле {field} не найдено'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@user_passes_test(is_owner)
def promo_block_get_data(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        promo = get_object_or_404(PromoBlock, pk=pk)
        data = {
            'id': promo.id, 'title': promo.title, 'text': promo.text,
            'button_text': promo.button_text, 'button_url': promo.button_url, 'video_url': promo.video_url,
            'image_url': promo.image.url if promo.image else '',
            'layout': promo.layout, 'text_align': promo.text_align, 'content_position': promo.content_position,
            'background_color': promo.background_color, 'text_color': promo.text_color,
            'button_color': promo.button_color, 'button_text_color': promo.button_text_color,
            'overlay_color': promo.overlay_color, 'font_family': promo.font_family,
            'title_font_size': promo.title_font_size, 'text_font_size': promo.text_font_size,
            'button_font_size': promo.button_font_size, 'block_width': promo.block_width,
            'block_height': promo.block_height, 'padding_top': promo.padding_top,
            'padding_bottom': promo.padding_bottom, 'padding_left': promo.padding_left,
            'padding_right': promo.padding_right, 'border_radius': promo.border_radius,
            'shadow_effect': promo.shadow_effect, 'background_gradient': promo.background_gradient,
            'gradient_start': promo.gradient_start, 'gradient_end': promo.gradient_end,
            'gradient_angle': promo.gradient_angle, 'use_image_as_background': promo.use_image_as_background,
            'background_overlay': promo.background_overlay, 'background_overlay_opacity': float(promo.background_overlay_opacity),
            'is_active': promo.is_active, 'start_date': promo.start_date.isoformat() if promo.start_date else '',
            'end_date': promo.end_date.isoformat() if promo.end_date else '',
            'is_currently_active': promo.is_currently_active(),
            'created_at': promo.created_at.strftime('%d.%m.%Y %H:%M'),
            'updated_at': promo.updated_at.strftime('%d.%m.%Y %H:%M'),
        }
        return JsonResponse({'status': 'success', 'promo': data})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@user_passes_test(is_owner)
def promo_block_update_dates(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        promo = get_object_or_404(PromoBlock, pk=pk)
        try:
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            promo.start_date = timezone.datetime.fromisoformat(start_date) if start_date else None
            promo.end_date = timezone.datetime.fromisoformat(end_date) if end_date else None
            promo.save()
            return JsonResponse({
                'status': 'success', 'message': 'Даты обновлены',
                'start_date': promo.start_date.isoformat() if promo.start_date else '',
                'end_date': promo.end_date.isoformat() if promo.end_date else ''
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': f'Ошибка обновления дат: {str(e)}'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@user_passes_test(is_owner)
def promo_block_update_design(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        promo = get_object_or_404(PromoBlock, pk=pk)
        try:
            if 'background_color' in request.POST:
                promo.background_color = request.POST.get('background_color')
            if 'text_color' in request.POST:
                promo.text_color = request.POST.get('text_color')
            if 'button_color' in request.POST:
                promo.button_color = request.POST.get('button_color')
            if 'button_text_color' in request.POST:
                promo.button_text_color = request.POST.get('button_text_color')
            if 'font_family' in request.POST:
                promo.font_family = request.POST.get('font_family')
            if 'title_font_size' in request.POST:
                promo.title_font_size = int(request.POST.get('title_font_size'))
            if 'text_font_size' in request.POST:
                promo.text_font_size = int(request.POST.get('text_font_size'))
            if 'button_font_size' in request.POST:
                promo.button_font_size = int(request.POST.get('button_font_size'))
            promo.save()
            return JsonResponse({'status': 'success', 'message': 'Дизайн обновлен'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': f'Ошибка обновления дизайна: {str(e)}'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@user_passes_test(is_owner)
def promo_block_update_layout(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        promo = get_object_or_404(PromoBlock, pk=pk)
        try:
            if 'layout' in request.POST:
                promo.layout = request.POST.get('layout')
            if 'text_align' in request.POST:
                promo.text_align = request.POST.get('text_align')
            if 'content_position' in request.POST:
                promo.content_position = request.POST.get('content_position')
            if 'block_width' in request.POST:
                promo.block_width = request.POST.get('block_width')
            if 'block_height' in request.POST:
                promo.block_height = int(request.POST.get('block_height'))
            if 'padding_top' in request.POST:
                promo.padding_top = int(request.POST.get('padding_top'))
            if 'padding_bottom' in request.POST:
                promo.padding_bottom = int(request.POST.get('padding_bottom'))
            if 'padding_left' in request.POST:
                promo.padding_left = int(request.POST.get('padding_left'))
            if 'padding_right' in request.POST:
                promo.padding_right = int(request.POST.get('padding_right'))
            if 'border_radius' in request.POST:
                promo.border_radius = int(request.POST.get('border_radius'))
            promo.save()
            return JsonResponse({'status': 'success', 'message': 'Макет обновлен'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': f'Ошибка обновления макета: {str(e)}'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@user_passes_test(is_owner)
def promo_block_apply_template(request, pk):
    if request.method == 'POST':
        promo = get_object_or_404(PromoBlock, pk=pk)
        template_name = request.POST.get('template_name')
        try:
            template_data = get_holiday_template(template_name)
            if template_data:
                for key, value in template_data.items():
                    if hasattr(promo, key):
                        setattr(promo, key, value)
                promo.save()
                messages.success(request, f'Шаблон "{template_name}" применен к промо-блоку')
            else:
                messages.error(request, 'Шаблон не найден')
        except Exception as e:
            messages.error(request, f'Ошибка применения шаблона: {str(e)}')
    return redirect('crm_promo_block_edit', pk=pk)


@login_required
@user_passes_test(is_owner)
def promo_block_reset_image(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        promo = get_object_or_404(PromoBlock, pk=pk)
        try:
            if promo.image:
                promo.image.delete(save=False)
                promo.image = None
                promo.save()
            return JsonResponse({'status': 'success', 'message': 'Изображение сброшено'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': f'Ошибка сброса изображения: {str(e)}'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})


@login_required
@user_passes_test(is_owner)
def promo_block_toggle_active(request, pk):
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        promo = get_object_or_404(PromoBlock, pk=pk)
        try:
            promo.is_active = not promo.is_active
            promo.save()
            return JsonResponse({
                'status': 'success',
                'is_active': promo.is_active,
                'message': f'Промо-блок {"активирован" if promo.is_active else "деактивирован"}'
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': f'Ошибка переключения: {str(e)}'})
    return JsonResponse({'status': 'error', 'error': 'Неверный запрос'})

# ==================== ВНУТРЕННИЕ УВЕДОМЛЕНИЯ ====================

@login_required
def get_notifications(request):
    """Получить список НЕПРОЧИТАННЫХ уведомлений"""
    try:
        profile = request.user.managerprofile
        from .models import InternalNotification
        
        notifications = InternalNotification.objects.filter(
            recipient=profile,
            is_read=False
        ).order_by('-created_at')[:50]
        
        notifications_data = []
        for notif in notifications:
            notifications_data.append({
                'id': notif.id,
                'type': notif.notification_type,
                'title': notif.title,
                'message': notif.message,
                'link': notif.link,
                'created_at': notif.created_at.strftime('%d.%m.%Y %H:%M'),
                'is_read': notif.is_read
            })
        
        return JsonResponse({
            'status': 'success',
            'internal_notifications': notifications_data,
            'unread_count': len(notifications_data)
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@login_required
def mark_notification_read(request, notification_id):
    """Удалить уведомление ПОЛНОСТЬЮ из БД"""
    try:
        from .models import InternalNotification
        profile = request.user.managerprofile
        
        notification = get_object_or_404(InternalNotification, id=notification_id, recipient=profile)
        notification.delete()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})


@login_required
def mark_all_notifications_read(request):
    """Удалить ВСЕ уведомления пользователя"""
    try:
        from .models import InternalNotification
        profile = request.user.managerprofile
        
        deleted_count = InternalNotification.objects.filter(recipient=profile).delete()[0]
        
        return JsonResponse({
            'status': 'success',
            'deleted_count': deleted_count
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)})