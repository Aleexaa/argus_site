from django.db import models
from django.contrib.auth.models import User


class Client(models.Model):
    company_name = models.CharField(max_length=255, verbose_name="Название компании")
    contact_person = models.CharField(max_length=255, blank=True, null=True, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=50, verbose_name="Телефон")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    telegram_id = models.BigIntegerField(blank=True, null=True, verbose_name="Telegram ID")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.company_name


class Service(models.Model):
    name = models.CharField(max_length=255, verbose_name="Услуга")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    base_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Базовая цена")
    has_kp = models.BooleanField(default=False, verbose_name="Включать в КП")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Request(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новая'),
        ('in_progress', 'В работе'),
        ('kp_ready', 'КП готово'),
        ('closed', 'Закрыта'),
    ]

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='requests', verbose_name="Клиент")
    object_type = models.CharField(max_length=100, verbose_name="Тип объекта")
    object_address = models.TextField(blank=True, null=True, verbose_name="Адрес объекта")
    area = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Площадь, м²")
    
    description = models.TextField(blank=True, null=True, verbose_name="Описание клиента")  # 💬 новое поле
    
    services = models.ManyToManyField(Service, through='RequestService', verbose_name="Услуги")
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='new', verbose_name="Статус")
    responsible_manager = models.ForeignKey(
        'crm.ManagerProfile',  # ИЗМЕНИТЕ НА ManagerProfile
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Менеджер"
    )
    attached_file = models.FileField(
        upload_to='kp_files/',
        blank=True,
        null=True,
        verbose_name="Прикрепленный файл"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Заявка #{self.id} от {self.client.company_name}"


class RequestService(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.RESTRICT)

    class Meta:
        unique_together = ('request', 'service')


class ManagerComment(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='comments')
    manager_user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField(verbose_name="Комментарий")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Комментарий {self.manager_user} к заявке {self.request_id}"


class Notification(models.Model):
    CHANNEL_CHOICES = [
        ('telegram', 'Telegram'),
        ('email', 'Email'),
    ]

    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True)
    request = models.ForeignKey(Request, on_delete=models.SET_NULL, null=True, blank=True)
    channel = models.CharField(max_length=50, choices=CHANNEL_CHOICES)
    message = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default='sent')

    def __str__(self):
        return f"{self.channel} -> {self.client or 'не указан'}"

class Project(models.Model):
    OBJECT_TYPES = [
        ('residential', 'Жилые'),
        ('commercial', 'Коммерческие'),
        ('industrial', 'Промышленные'),
        ('medical', 'Медицинские'),
        ('sports', 'Спортивные'),
        ('other', 'Прочие'),
    ]

    title = models.CharField(max_length=255, verbose_name="Название проекта")
    description = models.TextField(verbose_name="Описание")
    object_type = models.CharField(max_length=50, choices=OBJECT_TYPES, default='other', verbose_name="Тип объекта")
    address = models.CharField(max_length=255, blank=True, null=True, verbose_name="Адрес")
    image = models.ImageField(upload_to='projects/', blank=True, null=True, verbose_name="Изображение проекта")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title