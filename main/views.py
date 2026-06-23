from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.db import models
from django.utils import timezone
from django.views.generic import TemplateView
from django.http import HttpResponse, HttpResponseRedirect

# ✅ ПРАВИЛЬНЫЕ ИМПОРТЫ
from crm.models import Client, Feedback, PromoBlock, Vacancy, Candidate
from .models import Request, RequestService, Service, Project
from .forms import RequestForm, CandidateForm


def home(request):
    services = Service.objects.all()[:8]
    projects = Project.objects.all().order_by('-created_at')
    
    now = timezone.now()
    promo_blocks = PromoBlock.objects.filter(
        is_active=True
    ).filter(
        models.Q(start_date__isnull=True) | models.Q(start_date__lte=now)
    ).filter(
        models.Q(end_date__isnull=True) | models.Q(end_date__gte=now)
    ).order_by('-created_at')
    
    context = {
        'services': services,
        'projects': projects,
        'promo_blocks': promo_blocks,
    }
    return render(request, 'main/home.html', context)


def partners(request):
    return render(request, 'main/partners.html')


def about(request):
    stats = [
        {'value': '20+', 'label': 'лет на рынке', 'icon': 'award'},
        {'value': '500+', 'label': 'реализованных проектов', 'icon': 'target'},
        {'value': '100+', 'label': 'квалифицированных специалистов', 'icon': 'users'},
        {'value': '98%', 'label': 'довольных клиентов', 'icon': 'trending-up'},
    ]
    advantages = [
        {'icon': 'shield-check', 'title': 'Надежность', 'description': 'Все работы выполняются в строгом соответствии с нормативами и требованиями пожарной безопасности.'},
        {'icon': 'award', 'title': 'Опыт и экспертиза', 'description': 'Более 20 лет успешной работы в сфере пожарной безопасности.'},
        {'icon': 'users', 'title': 'Профессиональная команда', 'description': 'Наши специалисты регулярно проходят обучение и повышение квалификации.'},
        {'icon': 'briefcase', 'title': 'Комплексный подход', 'description': 'Предоставляем полный цикл услуг: от проектирования до технического обслуживания.'},
    ]
    return render(request, 'main/about.html', {'stats': stats, 'advantages': advantages})


def services(request):
    section1_services = [
        {'id': '1.1', 'title': 'Системы автоматического пожаротушения', 'description': 'Проектирование, монтаж и обслуживание автоматических систем пожаротушения (водяные, порошковые, газовые, аэрозольные).'},
        {'id': '1.2', 'title': 'Автоматическая пожарная сигнализация', 'description': 'Установка современных систем оповещения и управления эвакуацией людей при пожаре.'},
        {'id': '1.3', 'title': 'Электромонтажные работы', 'description': 'Полный комплекс электромонтажных работ: внутренние и наружные сети, освещение, силовое оборудование.'},
        {'id': '1.4', 'title': 'Системы вентиляции и кондиционирования', 'description': 'Проектирование и монтаж систем вентиляции, кондиционирования и отопления.'},
        {'id': '1.5', 'title': 'Огнезащита строительных конструкций', 'description': 'Огнезащитная обработка металлических и деревянных конструкций, воздуховодов, кабельных линий.'},
        {'id': '1.6', 'title': 'Системы оповещения и управления эвакуацией (СОУЭ)', 'description': 'Проектирование и монтаж систем оповещения людей о пожаре всех типов.'},
        {'id': '1.7', 'title': 'Техническое обслуживание систем безопасности', 'description': 'Регулярное техническое обслуживание установленных систем.'},
        {'id': '1.8', 'title': 'Монтаж систем видеонаблюдения и контроля доступа', 'description': 'Установка современных систем видеонаблюдения и СКУД.'},
    ]

    section2_services = [
        {'id': '2.1', 'title': 'Независимая оценка пожарного риска (пожарный аудит)', 'description': 'Экспертная оценка соответствия объекта требованиям пожарной безопасности.'},
        {'id': '2.2', 'title': 'Разработка проектной документации', 'description': 'Проектирование систем пожарной безопасности, электроснабжения, вентиляции.'},
        {'id': '2.3', 'title': 'Экспертиза проектной документации', 'description': 'Проверка проектной документации на соответствие нормам пожарной безопасности.'},
        {'id': '2.4', 'title': 'Консультационные услуги', 'description': 'Консультации по вопросам пожарной безопасности и подготовке документации.'},
    ]

    return render(request, 'main/services.html', {
        'section1_services': section1_services,
        'section2_services': section2_services,
    })


def projects(request):
    projects_list = Project.objects.all()
    object_types = ['all', 'residential', 'commercial', 'industrial', 'medical', 'sports']
    active_filter = request.GET.get('filter', 'all')
    if active_filter != 'all':
        projects_list = projects_list.filter(object_type=active_filter)
    return render(request, 'main/projects.html', {
        'projects': projects_list,
        'active_filter': active_filter,
        'object_types': object_types
    })


def get_client_ip(request):
    """Получение IP-адреса клиента"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def order_kp(request):
    """
    Оформление коммерческого предложения (КП) с соблюдением 152-ФЗ
    """
    if request.method == 'POST':
        form = RequestForm(request.POST, request.FILES)

        pd_agreed = request.POST.get('pd_agreed') == 'on'

        if not pd_agreed:
            messages.error(request, "❌ Для отправки заявки необходимо согласие на обработку персональных данных")
            services = Service.objects.filter(has_kp=True).order_by('id')
            selected_services = request.POST.getlist('services') if request.method == 'POST' else []
            return render(request, 'main/order_kp.html', {
                'form': form,
                'services': services,
                'selected_services': selected_services,
            })

            if form.is_valid():
                print("✅ ФОРМА ВАЛИДНА!")
                print("Очищенные данные:", form.cleaned_data)
            else:
                print("❌ ФОРМА НЕ ВАЛИДНА!")
                print("Ошибки формы:", form.errors)
                messages.error(request, f"❌ Ошибки формы: {form.errors}")
                return render(request, 'main/order_kp.html', {
                    'form': form,
                    'services': Service.objects.filter(has_kp=True).order_by('id'),
                    'selected_services': request.POST.getlist('services'),
                })

            # ✅ Создаем/находим клиента (Client из crm.models)
            try:
                client = Client.objects.create(
                    company_name=company_name,
                    phone=phone,
                    email=email,
                    contact_person=contact_person
                )
            except Exception as e:
                normalized_phone = Client.normalize_phone(phone)
                client = Client.objects.filter(phone__contains=normalized_phone).first()
                if not client:
                    messages.error(request, f"Ошибка создания клиента: {str(e)}")
                    return redirect('order_kp')

            # ✅ Создаем заявку (Request из main.models)
            try:
                new_request = Request.objects.create(
                    client=client,
                    object_type=form.cleaned_data['object_type'],
                    object_address=form.cleaned_data.get('object_address', ''),
                    attached_file=form.cleaned_data.get('attached_file'),
                    description=form.cleaned_data.get('description', ''),
                    status='new',
                    responsible_manager=None,
                    pd_agreed=True,
                    ip_address=get_client_ip(request),
                    policy_version='1.0',
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except Exception as e:
                messages.error(request, f"Ошибка сохранения заявки: {str(e)}")
                return redirect('order_kp')

            selected_services = form.cleaned_data.get('services', [])
            for service in selected_services:
                RequestService.objects.create(request=new_request, service=service)

            # Отправка уведомления на почту
            try:
                send_mail(
                    subject=f"🆕 Новая заявка #{new_request.id} от {client.company_name}",
                    message=(
                        f"Поступила новая заявка!\n\n"
                        f"Компания: {client.company_name}\n"
                        f"Контакт: {client.contact_person} ({client.phone})\n"
                        f"Email: {client.email}\n"
                        f"Согласие на обработку ПД: ДА\n"
                        f"IP: {new_request.ip_address}\n"
                        f"Время: {new_request.consent_date}\n"
                        f"Версия политики: {new_request.policy_version}\n\n"
                        f"Описание:\n{form.cleaned_data.get('description', '—')}\n\n"
                        f"Посмотреть в CRM: http://31.177.82.171/crm/request/{new_request.id}/"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.EMAIL_HOST_USER],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Ошибка отправки email: {e}")

            messages.success(request, "✅ Заявка успешно отправлена.")
            return redirect('order_success')

        else:
            messages.error(request, "❌ Проверьте правильность заполнения формы.")
    else:
        form = RequestForm()

    services = Service.objects.filter(has_kp=True).order_by('id')
    selected_services = request.POST.getlist('services') if request.method == 'POST' else []

    return render(request, 'main/order_kp.html', {
        'form': form,
        'services': services,
        'selected_services': selected_services,
    })


def order_success(request):
    return render(request, 'main/order_success.html')


def vacancies_list(request):
    vacancies = Vacancy.objects.filter(is_active=True)
    return render(request, 'main/vacancies_list.html', {'vacancies': vacancies})


def vacancy_detail(request, pk):
    vacancy = get_object_or_404(Vacancy, pk=pk)

    if request.method == 'POST':
        form = CandidateForm(request.POST)
        if form.is_valid():
            candidate = form.save(commit=False)
            candidate.vacancy = vacancy
            candidate.save()
            messages.success(request, 'Ваш отклик успешно отправлен!')
            return redirect('vacancy_detail', pk=pk)
    else:
        form = CandidateForm()

    return render(request, 'main/vacancy_detail.html', {
        'vacancy': vacancy,
        'form': form
    })


def contacts(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        contact = request.POST.get('contact')
        message = request.POST.get('message')
        pd_agreed = request.POST.get('pd_agreed') == 'on'

        if not name or not contact or not message:
            messages.error(request, '❌ Заполните все обязательные поля')
            return render(request, 'main/contacts.html')

        if not pd_agreed:
            messages.error(request, '❌ Необходимо дать согласие на обработку персональных данных')
            return render(request, 'main/contacts.html')

        try:
            feedback = Feedback.objects.create(
                name=name.strip(),
                contact=contact.strip(),
                message=message.strip(),
                pd_agreed=True,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                policy_version='1.0'
            )

            try:
                send_mail(
                    subject=f"📨 Новое сообщение обратной связи от {name}",
                    message=(
                        f"Поступило новое сообщение обратной связи!\n\n"
                        f"Имя: {name}\n"
                        f"Контакт: {contact}\n"
                        f"Сообщение:\n{message}\n\n"
                        f"Согласие на обработку ПД: ДА\n"
                        f"IP: {feedback.ip_address}\n"
                        f"Дата согласия: {feedback.pd_agreed_at.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Версия политики: {feedback.policy_version}\n\n"
                        f"Дата: {feedback.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                        f"Посмотреть в CRM: http://31.177.82.171/admin/crm/feedback/{feedback.id}/"
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.EMAIL_HOST_USER],
                    fail_silently=True,
                )
            except Exception as e:
                print(f"Ошибка отправки email: {e}")

            messages.success(request, '✅ Ваше сообщение успешно отправлено! Мы свяжемся с вами в ближайшее время.')
            return redirect('contacts')

        except Exception as e:
            messages.error(request, f'❌ Произошла ошибка при отправке сообщения: {str(e)}')

    return render(request, 'main/contacts.html')


class PrivacyPolicyView(TemplateView):
    template_name = 'main/privacy_policy.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_date'] = timezone.now().strftime('%d.%m.%Y')
        return context


class TermsView(TemplateView):
    template_name = 'main/terms.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_date'] = timezone.now().strftime('%d.%m.%Y')
        return context