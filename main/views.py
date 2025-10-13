# main/views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Service, Project, Partner
from .forms import RequestForm
from django.http import HttpResponse

def home(request):
    services = Service.objects.all()[:8]
    featured_projects = Project.objects.all()[:3]
    
    context = {
        'services': services,
        'featured_projects': featured_projects
    }
    return render(request, 'main/home.html', context)

def partners_new(request):
    return HttpResponse("НОВАЯ версия партнеров работает!")

def about(request):
    stats = [
        {'value': '20+', 'label': 'лет на рынке', 'icon': 'award'},
        {'value': '500+', 'label': 'реализованных проектов', 'icon': 'target'},
        {'value': '100+', 'label': 'квалифицированных специалистов', 'icon': 'users'},
        {'value': '98%', 'label': 'довольных клиентов', 'icon': 'trending-up'},
    ]
    
    advantages = [
        {
            'icon': 'shield-check',
            'title': 'Надежность',
            'description': 'Все работы выполняются в строгом соответствии с нормативами и требованиями пожарной безопасности.'
        },
        {
            'icon': 'award',
            'title': 'Опыт и экспертиза',
            'description': 'Более 20 лет успешной работы в сфере пожарной безопасности.'
        },
        {
            'icon': 'users',
            'title': 'Профессиональная команда',
            'description': 'Наши специалисты регулярно проходят обучение и повышение квалификации.'
        },
        {
            'icon': 'briefcase',
            'title': 'Комплексный подход',
            'description': 'Предоставляем полный цикл услуг: от проектирования до технического обслуживания.'
        },
    ]
    
    context = {
        'stats': stats,
        'advantages': advantages
    }
    return render(request, 'main/about.html', context)

def services(request):
    section1_services = [
        {
            'id': '1.1',
            'title': 'Системы автоматического пожаротушения',
            'description': 'Проектирование, монтаж и обслуживание автоматических систем пожаротушения (водяные, порошковые, газовые, аэрозольные). Полное соответствие нормам и стандартам пожарной безопасности. Работаем с объектами любой сложности.'
        },
        {
            'id': '1.2', 
            'title': 'Автоматическая пожарная сигнализация',
            'description': 'Установка современных систем оповещения и управления эвакуацией людей при пожаре. Интеграция с системами контроля доступа и видеонаблюдения. Техническое обслуживание и модернизация существующих систем.'
        },
        {
            'id': '1.3',
            'title': 'Электромонтажные работы',
            'description': 'Полный комплекс электромонтажных работ: внутренние и наружные сети, освещение, силовое оборудование. Проектирование электроснабжения объектов. Пуско-наладочные работы и испытания.'
        },
        {
            'id': '1.4',
            'title': 'Системы вентиляции и кондиционирования',
            'description': 'Проектирование и монтаж систем вентиляции, кондиционирования и отопления. Противодымная защита зданий. Энергоэффективные решения для комфортного микроклимата.'
        },
        {
            'id': '1.5',
            'title': 'Огнезащита строительных конструкций',
            'description': 'Огнезащитная обработка металлических и деревянных конструкций, воздуховодов, кабельных линий. Использование сертифицированных материалов. Выдача документов о проведенных работах.'
        },
        {
            'id': '1.6',
            'title': 'Системы оповещения и управления эвакуацией (СОУЭ)',
            'description': 'Проектирование и монтаж систем оповещения людей о пожаре всех типов. Звуковые и световые оповещатели. Интеграция с автоматической пожарной сигнализацией.'
        },
        {
            'id': '1.7',
            'title': 'Техническое обслуживание систем безопасности',
            'description': 'Регулярное техническое обслуживание установленных систем. Диагностика и устранение неисправностей. Замена оборудования и модернизация систем.'
        },
        {
            'id': '1.8',
            'title': 'Монтаж систем видеонаблюдения и контроля доступа',
            'description': 'Установка современных систем видеонаблюдения и СКУД. Интеграция с системами пожарной безопасности. Удаленный мониторинг и управление.'
        },
    ]

    section2_services = [
        {
            'id': '2.1',
            'title': 'Независимая оценка пожарного риска (пожарный аудит)',
            'description': 'Экспертная оценка соответствия объекта требованиям пожарной безопасности. Расчет пожарных рисков. Разработка комплекса мер для обеспечения безопасности объекта. Подготовка заключения для предоставления в органы государственного пожарного надзора.'
        },
        {
            'id': '2.2',
            'title': 'Разработка проектной документации',
            'description': 'Проектирование систем пожарной безопасности, электроснабжения, вентиляции. Разработка разделов ИТМ ГО и ЧС, ПОС, ППР. Согласование проектной документации в надзорных органах.'
        },
        {
            'id': '2.3',
            'title': 'Экспертиза проектной документации',
            'description': 'Проверка проектной документации на соответствие нормам и требованиям пожарной безопасности. Выявление недостатков и разработка рекомендаций по их устранению. Сопровождение на всех этапах согласования.'
        },
        {
            'id': '2.4',
            'title': 'Консультационные услуги',
            'description': 'Консультации по вопросам пожарной безопасности, подготовки к проверкам надзорных органов. Обучение персонала мерам пожарной безопасности. Помощь в подготовке документации.'
        },
    ]

    context = {
        'section1_services': section1_services,
        'section2_services': section2_services,
    }
    return render(request, 'main/services.html', context)


def projects(request):
    projects_list = Project.objects.all()
    
    # Фильтры
    object_types = ['all', 'residential', 'commercial', 'industrial', 'medical', 'sports']
    active_filter = request.GET.get('filter', 'all')
    
    if active_filter != 'all':
        projects_list = projects_list.filter(object_type=active_filter)
    
    context = {
        'projects': projects_list,
        'active_filter': active_filter,
        'object_types': object_types
    }
    return render(request, 'main/projects.html', context)
'''def partners(request):
    partners_list = Partner.objects.all()
    context = {
        'partners': partners_list
    }
    return render(request, 'main/partners.html', context)
'''
def partners(request):
    # Максимально простая версия без БД и сложной логики
    return HttpResponse("Партнеры - базовая страница работает!")
def contacts(request):
    if request.method == 'POST':
        # Обработка формы оSбратной связи
        name = request.POST.get('name')
        contact = request.POST.get('contact')
        message = request.POST.get('message')
        
        # Здесь можно добавить логику отправки email или сохранения в базу
        messages.success(request, 'Сообщение отправлено! Мы свяжемся с вами в ближайшее время.')
        return redirect('contacts')
    
    return render(request, 'main/contacts.html')

def order_kp(request):
    if request.method == 'POST':
        form = RequestForm(request.POST, request.FILES)
        if form.is_valid():
            # Упрощенное сохранение без создания клиента
            request_obj = form.save()
            messages.success(request, 'Заявка успешно отправлена! Мы свяжемся с вами в ближайшее время.')
            return redirect('order_success')
    else:
        form = RequestForm()
    
    context = {
        'form': form
    }
    return render(request, 'main/order_kp.html', context)

def order_success(request):
    return render(request, 'main/order_success.html')