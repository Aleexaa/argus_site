# main/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Client, Request, RequestService, Service, Project
from .forms import RequestForm
from django.core.mail import send_mail
from django.conf import settings

def home(request):
    services = Service.objects.all()[:8]
    featured_projects = Project.objects.all()[:3]
    context = {
        'services': services,
        'featured_projects': featured_projects
    }
    return render(request, 'main/home.html', context)


def partners(request):
    partners_list = [
        {'name': 'ТехноПрофи', 'description': 'Официальный партнер'},
        {'name': 'СтройГарант', 'description': 'Надежный поставщик'},
        {'name': 'ЭнергоСервис', 'description': 'Технологический партнер'},
        {'name': 'Безопасность+', 'description': 'Эксперты в СОУЭ'},
    ]
    return render(request, 'main/partners.html', {'partners': partners_list})


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


def contacts(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        contact = request.POST.get('contact')
        message = request.POST.get('message')
        messages.success(request, 'Сообщение отправлено! Мы свяжемся с вами в ближайшее время.')
        return redirect('contacts')
    return render(request, 'main/contacts.html')


def order_kp(request):
    """
    Оформление коммерческого предложения (КП)
    — сохраняет клиента, заявку и выбранные услуги в базу PostgreSQL
    """
    if request.method == 'POST':
        form = RequestForm(request.POST, request.FILES)

        if form.is_valid():
            company_name = form.cleaned_data.get('company_name') or 'Не указано'
            phone = form.cleaned_data.get('phone') or ''
            email = form.cleaned_data.get('email') or ''
            contact_person = form.cleaned_data.get('contact_person') or ''

            client, created = Client.objects.get_or_create(
                company_name=company_name,
                phone=phone,
                defaults={'contact_person': contact_person, 'email': email}
            )

            new_request = Request.objects.create(
                client=client,
                object_type=form.cleaned_data['object_type'],
                object_address=form.cleaned_data.get('object_address', ''),
                attached_file=form.cleaned_data.get('attached_file'),
                description=form.cleaned_data.get('description', ''),
                status='new',
                responsible_manager=None
            )

            # сохраняем выбранные услуги
            selected_services = form.cleaned_data.get('services', [])
            for service in selected_services:
                RequestService.objects.create(request=new_request, service=service)

            # уведомление по почте
            send_mail(
                subject=f"🆕 Новая заявка #{new_request.id} от {client.company_name}",
                message=(
                    f"Поступила новая заявка!\n\n"
                    f"Компания: {client.company_name}\n"
                    f"Контакт: {client.contact_person} ({client.phone})\n"
                    f"Email: {client.email}\n\n"
                    f"Описание:\n{form.cleaned_data.get('description', '—')}\n\n"
                    f"Посмотреть в CRM: https://argus.local/crm/request/{new_request.id}/"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=["afanaseva.sasha.a@gmail.com"],  # исправь адрес
                fail_silently=True,
            )

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
