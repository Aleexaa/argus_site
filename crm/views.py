from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import authenticate, login
from crm.models import ManagerProfile, ViewedRequest
from crm.models import Comment as CrmComment
from main.models import Request, Client, Project, ManagerComment
from django.http import JsonResponse, HttpResponse, FileResponse, Http404
from django.template.loader import render_to_string
from django.http import FileResponse
from django.utils import timezone
from datetime import timedelta
import os

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("crm_dashboard")
        else:
            messages.error(request, "Неверный логин или пароль")

    return render(request, "crm/login.html")

# ============================================================
# 🔐 Проверки ролей
# ============================================================
def is_owner(user):
    """Проверяет, является ли пользователь владельцем."""
    return hasattr(user, 'managerprofile') and user.managerprofile.role == 'owner'

def is_manager(user):
    """Проверяет, является ли пользователь менеджером."""
    return hasattr(user, 'managerprofile') and user.managerprofile.role == 'manager'

# ============================================================
# 📋 Главная панель (заявки)
# ============================================================
@login_required
def dashboard(request):
    """Главная страница CRM — заявки, обновляются без перезагрузки."""
    print("=== DASHBOARD CALLED ===")
    print("AJAX request:", request.headers.get('x-requested-with'))
    print("User:", request.user)
    
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        return redirect('logout')

    # Определяем набор заявок
    if profile.role == 'owner':
        requests_qs = Request.objects.all().select_related('client', 'responsible_manager').order_by('-created_at')
    else:
        requests_qs = Request.objects.filter(responsible_manager=profile).select_related('client').order_by('-created_at')

    # 🔹 АВТОМАТИЧЕСКИ ОТМЕЧАЕМ ВСЕ ЗАЯВКИ КАК ПРОСМОТРЕННЫЕ ПРИ ЗАГРУЗКЕ СТРАНИЦЫ
    if not request.headers.get('x-requested-with') == 'XMLHttpRequest':
        for req in requests_qs:
            ViewedRequest.objects.get_or_create(
                user=request.user,
                request=req
            )
        print(f"✅ Автоматически отмечено {requests_qs.count()} заявок как просмотренные")

    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    context = {
        'user': request.user,
        'profile': profile,
        'requests': requests_qs,
        'is_owner': profile.role == 'owner',
        'status_filter': status_filter,
    }

    # ⚡ Если запрос AJAX — возвращаем только HTML списка заявок
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        print("🔔 Returning AJAX response")
        html = render_to_string('crm/partials/requests_list.html', context, request=request)
        return HttpResponse(html)

    print("📄 Returning full page")
    return render(request, 'crm/dashboard.html', context)

# ============================================================
# 🧾 Мои заявки
# ============================================================
@login_required
def my_requests(request):
    """Отдельный раздел 'Мои заявки'."""
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('logout')

    if profile.role == 'owner':
        requests = Request.objects.all().order_by('-created_at')
    else:
        requests = Request.objects.filter(responsible_manager=profile).order_by('-created_at')

    return render(request, 'crm/my_requests.html', {
        'user': request.user,
        'profile': profile,
        'requests': requests,
        'is_owner': profile.role == 'owner',
    })

# ============================================================
# 🗂 Детальная карточка заявки
# ============================================================
@login_required
def request_detail(request, pk):
    """Карточка заявки + комментарии + смена статуса."""
    req = get_object_or_404(Request, pk=pk)
    profile = getattr(request.user, 'managerprofile', None)

    if not profile:
        messages.error(request, "У вашего аккаунта нет профиля менеджера.")
        return redirect('crm_dashboard')

    # Проверка доступа
    if not is_owner(request.user) and req.responsible_manager != profile:
        messages.error(request, "У вас нет доступа к этой заявке.")
        return redirect('crm_dashboard')

    # Менеджеры для выпадающего списка
    managers = ManagerProfile.objects.filter(role="manager").select_related("user")

    if request.method == "POST":
        new_status = request.POST.get("status")
        comment_text = request.POST.get("comment")
        new_manager_id = request.POST.get("manager")

        # 🔹 Обновляем менеджера, если изменился
        if new_manager_id:
            new_manager_profile = ManagerProfile.objects.filter(id=new_manager_id).first()
            if new_manager_profile and req.responsible_manager != new_manager_profile:
                req.responsible_manager = new_manager_profile
                req.save(update_fields=["responsible_manager"])
                messages.success(
                    request,
                    f"Менеджер назначен: {new_manager_profile.user.get_full_name() or new_manager_profile.user.username}"
                )

        # 🔹 Обновляем статус заявки
        if new_status and new_status != req.status:
            old_status = req.get_status_display()
            req.status = new_status
            req.save(update_fields=["status"])
            _notify_client_status(req)
            messages.success(request, f"Статус обновлён: {old_status} → {req.get_status_display()}")

        # 🔹 Добавляем комментарий
        if comment_text:
            CrmComment.objects.create(request=req, author=profile, text=comment_text)
            messages.success(request, "Комментарий добавлен.")

        # Если это AJAX, возвращаем только комментарии
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            comments = CrmComment.objects.filter(request=req).select_related('author').order_by('-created_at')
            html = render_to_string("crm/partials/comments_block.html", {"comments": comments}, request=request)
            return HttpResponse(html)

        return redirect('crm_request_detail', pk=req.pk)

    # 🔹 Получаем комментарии
    comments = CrmComment.objects.filter(request=req).select_related('author').order_by('-created_at')

    return render(request, 'crm/request_detail.html', {
        'user': request.user,
        'profile': profile,
        'req': req,
        'comments': comments,
        'managers': managers,
        'is_owner': profile.role == 'owner',
    })
# ============================================================
# ✉️ Email уведомления
# ============================================================
def _notify_manager_assignment(req):
    if not req.responsible_manager or not req.responsible_manager.corporate_email:
        return

    subject = "🔔 Вам назначена новая заявка"
    message = (
        f"Здравствуйте, {req.responsible_manager.user.first_name or req.responsible_manager.user.username}!\n\n"
        f"Вам назначена новая заявка от клиента {req.client.company_name}.\n"
        f"Тип объекта: {req.object_type}\n"
        f"Адрес объекта: {req.object_address or 'Не указан'}\n"
        f"Площадь: {req.area or 'Не указана'} м²\n\n"
        f"Перейти в CRM: http://ваш-домен/crm/request/{req.id}/"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [req.responsible_manager.corporate_email], fail_silently=True)

def _notify_client_status(req):
    client_email = req.client.email
    if not client_email:
        return

    subject = f"📄 Обновление по вашей заявке ({req.client.company_name})"
    message = (
        f"Здравствуйте!\n\n"
        f"Статус вашей заявки изменён: {req.get_status_display()}.\n"
        f"Наш специалист свяжется с вами при необходимости.\n\n"
        f"С уважением,\nКомпания Аргус."
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [client_email], fail_silently=True)

# ============================================================
# 🧑‍💼 Клиенты и проекты
# ============================================================
@login_required
def clients_list(request):
    profile = request.user.managerprofile
    if is_owner(request.user):
        clients = Client.objects.all().order_by('company_name')
    else:
        clients = Client.objects.filter(project__manager=profile).distinct().order_by('company_name')
    return render(request, 'crm/clients.html', {
        'user': request.user,
        'profile': profile,
        'clients': clients
    })

@login_required
def projects_list(request):
    profile = request.user.managerprofile
    if is_owner(request.user):
        projects = Project.objects.all().select_related('client', 'manager').order_by('-id')
    else:
        projects = Project.objects.filter(manager=profile).select_related('client').order_by('-id')
    return render(request, 'crm/projects.html', {
        'user': request.user,
        'profile': profile,
        'projects': projects
    })

@login_required
def add_project(request):
    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        client_id = request.POST.get("client_id")

        if not (name and client_id):
            messages.error(request, "Пожалуйста, заполните все обязательные поля.")
            return redirect('crm_add_project')

        client = get_object_or_404(Client, id=client_id)
        Project.objects.create(
            name=name,
            description=description,
            client=client,
            manager=request.user.managerprofile
        )
        messages.success(request, "Проект успешно добавлен.")
        return redirect('crm_projects')

    clients = Client.objects.all().order_by('company_name')
    return render(request, 'crm/add_project.html', {
        'user': request.user,
        'profile': request.user.managerprofile,
        'clients': clients
    })

# ============================================================
# 👤 Профиль
# ============================================================
@login_required
def profile_view(request):
    profile = request.user.managerprofile
    return render(request, 'crm/profile.html', {
        'user': request.user,
        'profile': profile
    })

# ============================================================
# 👔 Менеджеры (только для владельца)
# ============================================================
@login_required
@user_passes_test(is_owner)
def managers_list(request):
    managers = ManagerProfile.objects.filter(role='manager').select_related('user')
    return render(request, 'crm/managers.html', {
        'user': request.user,
        'profile': request.user.managerprofile,
        'managers': managers
    })

@login_required
def requests_list(request):
    """Список всех заявок с автообновлением"""
    profile = getattr(request.user, 'managerprofile', None)
    if not profile:
        return redirect('logout')

    # Определяем набор заявок - ИСПРАВЛЕНО!
    if profile.role == 'owner':
        requests_qs = Request.objects.all().select_related('client', 'responsible_manager').order_by('-created_at')
    else:
        requests_qs = Request.objects.filter(responsible_manager=profile).select_related('client').order_by('-created_at')

    # Фильтрация по статусу
    status_filter = request.GET.get('status')
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    context = {
        'user': request.user,
        'profile': profile,
        'requests': requests_qs,
        'is_owner': profile.role == 'owner',
        'status_filter': status_filter,
    }

    # ⚡ Если запрос AJAX — возвращаем только HTML списка заявок
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        html = render_to_string('crm/partials/requests_list.html', context, request=request)
        return HttpResponse(html)

    # Обычная загрузка страницы
    return render(request, 'crm/request_list.html', context)

# ============================================================
# 📊 Проверка новых заявок (ИСПРАВЛЕННАЯ ВЕРСИЯ)
# ============================================================
# ============================================================
# 📊 Проверка новых заявок (ОБНОВЛЕННАЯ ВЕРСИЯ)
# ============================================================
@login_required
def check_new_requests(request):
    """Проверяет наличие НЕПРОСМОТРЕННЫХ заявок и возвращает данные о них"""
    try:
        user = request.user
        
        # Получаем профиль менеджера
        profile = getattr(user, 'managerprofile', None)
        if not profile:
            return JsonResponse({
                'unviewed_requests_count': 0,
                'all_requests_count': 0,
                'new_requests': [],
                'last_check': timezone.now().isoformat(),
                'status': 'error',
                'error': 'User has no manager profile'
            })
        
        # Получаем все заявки в зависимости от роли
        if profile.role == 'owner':
            all_requests = Request.objects.all().select_related('client', 'responsible_manager__user')
        else:
            all_requests = Request.objects.filter(responsible_manager=profile).select_related('client', 'responsible_manager__user')
        
        # Получаем ID всех заявок пользователя
        all_request_ids = list(all_requests.values_list('id', flat=True))
        
        if not all_request_ids:
            return JsonResponse({
                'unviewed_requests_count': 0,
                'all_requests_count': 0,
                'new_requests': [],
                'last_check': timezone.now().isoformat(),
                'status': 'success',
                'user': user.username
            })
        
        # Получаем ID просмотренных заявок
        viewed_request_ids = list(
            ViewedRequest.objects.filter(
                user=user, 
                request_id__in=all_request_ids
            ).values_list('request_id', flat=True)
        )
        
        # Считаем непросмотренные заявки
        unviewed_count = len(all_request_ids) - len(viewed_request_ids)
        
        # 🔹 ПОЛУЧАЕМ ДАННЫЕ О НОВЫХ ЗАЯВКАХ
        new_requests_data = []
        if unviewed_count > 0:
            # Находим непросмотренные заявки
            unviewed_requests = all_requests.exclude(id__in=viewed_request_ids)
            
            for req in unviewed_requests:
                new_requests_data.append({
                    'id': req.id,
                    'company_name': req.client.company_name,
                    'object_type': req.object_type,
                    'object_address': req.object_address or 'Не указан',
                    'area': str(req.area) if req.area else 'Не указана',
                    'status': req.status,
                    'status_display': req.get_status_display(),
                    'created_at': req.created_at.strftime('%d.%m.%Y %H:%M'),
                    'has_file': bool(req.attached_file),
                    'description': req.description or '',
                    'responsible_manager': req.responsible_manager.user.get_full_name() if req.responsible_manager else None,
                    'client_contact': req.client.contact_person or 'Не указан',
                    'client_email': req.client.email or 'Не указан',
                })
        
        # Для отладки
        print(f"📊 Проверка непросмотренных заявок для {user.username}:")
        print(f"   - Всего заявок: {len(all_request_ids)}")
        print(f"   - Просмотренных: {len(viewed_request_ids)}")
        print(f"   - Непросмотренных: {unviewed_count}")
        print(f"   - Новых заявок для отображения: {len(new_requests_data)}")
        
        response_data = {
            'all_requests_count': len(all_request_ids),
            'unviewed_requests_count': unviewed_count,
            'viewed_requests_count': len(viewed_request_ids),
            'new_requests': new_requests_data,
            'last_check': timezone.now().isoformat(),
            'status': 'success',
            'user': user.username,
            'profile_role': profile.role
        }
        
    except Exception as e:
        print(f"❌ Ошибка в check_new_requests: {e}")
        response_data = {
            'unviewed_requests_count': 0,
            'all_requests_count': 0,
            'new_requests': [],
            'last_check': timezone.now().isoformat(),
            'status': 'error',
            'error': str(e)
        }
    
    return JsonResponse(response_data)

@login_required
def mark_request_as_viewed(request, pk=None):
    """Отмечает заявку или все заявки как просмотренные"""
    try:
        user = request.user
        
        if pk:
            # Отмечаем одну заявку
            req = get_object_or_404(Request, pk=pk)
            ViewedRequest.objects.get_or_create(user=user, request=req)
            
            return JsonResponse({
                'status': 'success',
                'message': f'Заявка #{req.id} отмечена как просмотренная'
            })
        else:
            # Отмечаем ВСЕ заявки пользователя
            profile = getattr(user, 'managerprofile', None)
            if not profile:
                return JsonResponse({
                    'status': 'error',
                    'error': 'User has no manager profile'
                })
            
            # Получаем все заявки пользователя
            if profile.role == 'owner':
                user_requests = Request.objects.all()
            else:
                user_requests = Request.objects.filter(responsible_manager=profile)
            
            # Создаем записи о просмотре для всех заявок
            viewed_count = 0
            for req in user_requests:
                ViewedRequest.objects.get_or_create(user=user, request=req)
                viewed_count += 1
            
            return JsonResponse({
                'status': 'success',
                'message': f'Все заявки ({viewed_count} шт.) отмечены как просмотренные',
                'viewed_count': viewed_count
            })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e)
        })

# ============================================================
# 📥 Скачивание файлов
# ============================================================
@login_required
def download_request_file(request, pk):
    req = get_object_or_404(Request, pk=pk)
    if req.attached_file:
        response = FileResponse(req.attached_file.open(), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{req.attached_file.name}"'
        return response
    else:
        raise Http404("Файл не найден")

@login_required
def download_request_file(request, pk):
    """Скачивание файла заявки"""
    req = get_object_or_404(Request, pk=pk)
    
    if not req.attached_file:
        raise Http404("Файл не прикреплен к заявке")
    
    try:
        # Полный путь к файлу
        file_path = os.path.join(settings.MEDIA_ROOT, req.attached_file.name)
        
        # Проверяем существование файла
        if not os.path.exists(file_path):
            raise Http404("Файл не найден на сервере")
        
        # Открываем файл в бинарном режиме
        file = open(file_path, 'rb')
        
        # Получаем оригинальное имя файла
        filename = os.path.basename(req.attached_file.name)
        
        # Создаем response
        response = FileResponse(file, as_attachment=True, filename=filename)
        response['Content-Type'] = 'application/octet-stream'
        
        return response
        
    except Exception as e:
        print(f"Ошибка при скачивании файла: {e}")
        raise Http404("Ошибка при загрузке файла")
    
@login_required
@user_passes_test(is_owner)
def assign_manager(request, pk):
    """Назначение менеджера на заявку (только владелец)."""
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
        messages.success(
            request,
            f"Менеджер {manager_profile.user.get_full_name() or manager_profile.user.username} назначен."
        )
        return redirect("crm_request_detail", pk=req.pk)

    managers = ManagerProfile.objects.filter(role="manager").select_related("user")
    return render(request, "crm/assign_manager.html", {
        'user': request.user,
        'profile': request.user.managerprofile,
        "req": req, 
        "managers": managers
    })

def get_unviewed_requests_count(request):
    """Возвращает количество непросмотренных заявок для текущего пользователя"""
    try:
        user = request.user
        profile = getattr(user, 'managerprofile', None)
        
        if not profile:
            return JsonResponse({
                'unviewed_count': 0,
                'status': 'error',
                'error': 'No manager profile'
            })
        
        # Получаем все ID заявок
        if profile.role == 'owner':
            all_request_ids = list(Request.objects.values_list('id', flat=True))
        else:
            all_request_ids = list(Request.objects.filter(
                responsible_manager=profile
            ).values_list('id', flat=True))
        
        # Здесь должна быть логика получения просмотренных заявок из localStorage
        # Но на сервере мы не знаем, какие заявки пользователь просмотрел
        # Поэтому временно возвращаем 0
        
        unviewed_count = 0  # Временно
        
        return JsonResponse({
            'unviewed_count': unviewed_count,
            'total_requests': len(all_request_ids),
            'status': 'success'
        })
        
    except Exception as e:
        return JsonResponse({
            'unviewed_count': 0,
            'status': 'error',
            'error': str(e)
        })