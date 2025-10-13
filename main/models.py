# main/models.py
from django.db import models

class Service(models.Model):
    SERVICE_TYPES = [
        ('installation', 'Монтаж, проектирование и обслуживание'),
        ('design', 'Для решения задач в области проектирования и безопасности'),
        ('special', 'Специальные технические условия'),
    ]
    
    name = models.CharField(max_length=255, verbose_name="Название услуги")
    description = models.TextField(verbose_name="Описание")
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPES, verbose_name="Тип услуги", default='installation')
    has_kp = models.BooleanField(default=False, verbose_name="Возможность заказа КП")
    icon = models.CharField(max_length=50, default='settings', verbose_name="Иконка")

    def __str__(self):
        return self.name

class Project(models.Model):
    OBJECT_TYPES = [
        ('residential', 'Жилой комплекс'),
        ('commercial', 'Торговый центр'),
        ('industrial', 'Промышленный объект'),
        ('medical', 'Медицинское учреждение'),
        ('sports', 'Спортивный объект'),
    ]
    
    title = models.CharField(max_length=255, verbose_name="Название проекта")
    description = models.TextField(verbose_name="Описание")
    object_type = models.CharField(max_length=20, choices=OBJECT_TYPES, verbose_name="Тип объекта", default='commercial')
    area = models.CharField(max_length=100, blank=True, verbose_name="Площадь")
    location = models.CharField(max_length=255, verbose_name="Местоположение", default='г. Тюмень')  # ← ЭТО ПОЛЕ ДОЛЖНО БЫТЬ
    image = models.ImageField(upload_to='projects/', verbose_name="Изображение", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def __str__(self):
        return self.title


class Client(models.Model):
    company_name = models.CharField(max_length=255, verbose_name="Название компании")
    contact_person = models.CharField(max_length=255, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(verbose_name="Email")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def __str__(self):
        return self.company_name

class Request(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('kp_ready', 'КП готово'),
        ('completed', 'Завершено'),
    ]
    
    OBJECT_TYPES = [
        ('residential', 'Жильё'),
        ('commercial', 'Торговый центр'),
        ('industrial', 'Промышленный'),
    ]
    
    client = models.ForeignKey(Client, on_delete=models.CASCADE, verbose_name="Клиент")
    object_type = models.CharField(max_length=20, choices=OBJECT_TYPES, verbose_name="Тип объекта")
    object_description = models.TextField(verbose_name="Характеристика объекта")
    services = models.ManyToManyField(Service, verbose_name="Услуги")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name="Статус")
    attached_file = models.FileField(upload_to='requests/', blank=True, null=True, verbose_name="Прикрепленный файл")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    def __str__(self):
        return f"Заявка от {self.client.company_name}"