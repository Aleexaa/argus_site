from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone 
from django.conf import settings
from django.core.exceptions import ValidationError
import re

class ManagerProfile(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Владелец'),
        ('manager', 'Менеджер'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='managerprofile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='manager')
    corporate_email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class Client(models.Model):  
    company_name = models.CharField(
        max_length=255, 
        verbose_name='Название компании'
    )
    contact_person = models.CharField(
        max_length=255, 
        verbose_name='Контактное лицо', 
        blank=True, 
        null=True
    )
    phone = models.CharField(
        max_length=20, 
        verbose_name='Телефон'
    )
    email = models.EmailField(
        verbose_name='Email', 
        blank=True, 
        null=True
    )
    created_at = models.DateTimeField(
        verbose_name='Дата создания',
        default=timezone.now
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['company_name']
        unique_together = [
            ('company_name', 'phone'),
        ]

    def __str__(self):
        return self.company_name

    @property
    def requests(self):
        """Связь с заявками через main.Request"""
        from main.models import Request
        return Request.objects.filter(client_id=self.id)

    @property
    def requests_count(self):
        """Количество заявок клиента"""
        return self.requests.count()

    @property
    def active_requests_count(self):
        """Количество активных заявок (new, in_progress)"""
        return self.requests.filter(status__in=['new', 'in_progress']).count()

    @staticmethod
    def normalize_phone(phone):
        """Нормализация телефонного номера"""
        if not phone:
            return None
        # Оставляем только цифры
        digits = re.sub(r'\D', '', str(phone))
        # Если номер начинается с 7 или 8 и имеет 11 цифр, оставляем последние 10
        if len(digits) == 11 and digits[0] in ['7', '8']:
            return digits[1:]
        # Если номер имеет 10 цифр, возвращаем как есть
        elif len(digits) == 10:
            return digits
        return digits
    
    @staticmethod
    def normalize_email(email):
        """Нормализация email"""
        if not email:
            return None
        return email.lower().strip()

    def clean(self):
        """Валидация при сохранении"""
        errors = {}
        
        # Проверяем дубликаты по нормализованному телефону
        if self.phone:
            normalized_phone = Client.normalize_phone(self.phone)
            if normalized_phone:
                duplicates = Client.objects.filter(
                    models.Q(phone__contains=normalized_phone) |
                    models.Q(phone__contains=self.phone)
                ).exclude(pk=self.pk if self.pk else None)
                
                if duplicates.exists():
                    errors['phone'] = f'Клиент с таким телефоном уже существует: {", ".join([c.company_name for c in duplicates])}'
        
        # Проверяем дубликаты по email
        if self.email:
            normalized_email = Client.normalize_email(self.email)
            if normalized_email:
                duplicates = Client.objects.filter(
                    models.Q(email__iexact=normalized_email)
                ).exclude(pk=self.pk if self.pk else None)
                
                if duplicates.exists():
                    errors['email'] = f'Клиент с таким email уже существует: {", ".join([c.company_name for c in duplicates])}'
        
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Нормализуем телефон перед сохранением
        if self.phone:
            self.phone = Client.normalize_phone(self.phone)
        
        # Нормализуем email перед сохранением
        if self.email:
            self.email = Client.normalize_email(self.email)
        
        # Полная валидация перед сохранением
        self.full_clean()
        super().save(*args, **kwargs)


class ViewedRequest(models.Model):
    """Модель для отслеживания просмотренных заявок"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request = models.ForeignKey('main.Request', on_delete=models.CASCADE) 
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'request']  # Одна запись на пользователя и заявку
        
    def __str__(self):
        return f"{self.user.username} просмотрел заявку #{self.request.id}"


class Comment(models.Model):
    request = models.ForeignKey(
        'main.Request',
        on_delete=models.CASCADE,
        related_name='crm_comments',
        verbose_name='Заявка'
    )
    author = models.ForeignKey(
        'ManagerProfile',
        on_delete=models.CASCADE,
        verbose_name='Автор'
    )
    text = models.TextField('Текст комментария')
    created_at = models.DateTimeField('Дата создания', default=timezone.now)

    def __str__(self):
        return f'Комментарий от {self.author.user.username} к заявке #{self.request.id}'


class Vacancy(models.Model):
    title = models.CharField(max_length=255, verbose_name="Название вакансии")
    
    # Разбиваем описание на отдельные поля
    salary = models.CharField(
        max_length=100, 
        verbose_name="Зарплата",
        blank=True,
        null=True,
        help_text="Например: от 50 000 руб., договорная"
    )
    
    employment_type = models.CharField(
        max_length=100,
        verbose_name="Тип занятости",
        blank=True,
        null=True,
        help_text="Например: Полная занятость, удаленная работа"
    )
    
    experience = models.CharField(
        max_length=100,
        verbose_name="Опыт работы",
        blank=True,
        null=True,
        help_text="Например: от 1 года, без опыта"
    )
    
    responsibilities = models.TextField(
        verbose_name="Обязанности",
        blank=True,
        null=True,
        help_text="Перечислите основные обязанности"
    )
    
    requirements = models.TextField(
        verbose_name="Требования",
        blank=True,
        null=True,
        help_text="Требования к кандидату"
    )
    
    conditions = models.TextField(
        verbose_name="Условия",
        blank=True,
        null=True,
        help_text="Условия работы, бонусы, преимущества"
    )
    
    # Общее описание (оставляем для обратной совместимости)
    description = models.TextField(
        verbose_name="Общее описание",
        blank=True,
        null=True
    )
    
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Вакансия"
        verbose_name_plural = "Вакансии"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Автоматически формируем общее описание из отдельных полей
        if not self.description:
            description_parts = []
            if self.salary:
                description_parts.append(f"💰 Зарплата: {self.salary}")
            if self.employment_type:
                description_parts.append(f"📊 Тип занятости: {self.employment_type}")
            if self.experience:
                description_parts.append(f"🎯 Опыт работы: {self.experience}")
            if self.responsibilities:
                description_parts.append(f"🎯 Обязанности: {self.responsibilities}")
            if self.requirements:
                description_parts.append(f"📋 Требования: {self.requirements}")
            if self.conditions:
                description_parts.append(f"🏆 Условия: {self.conditions}")
            
            self.description = "\n\n".join(description_parts)
        
        super().save(*args, **kwargs)


class Candidate(models.Model):
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, verbose_name="Вакансия")
    name = models.CharField(max_length=255, verbose_name="Имя кандидата")
    phone_number = models.CharField(max_length=15, verbose_name="Телефон")
    comment = models.TextField(blank=True, null=True, verbose_name="Комментарий кандидата")
    admin_notes = models.TextField(blank=True, null=True, verbose_name="Заметки админа")
    applied_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отклика")
    
    # ✅ Добавляем поле для согласия на обработку ПД
    pd_agreed = models.BooleanField(
        default=False,
        verbose_name="Согласие на обработку персональных данных"
    )
    pd_agreed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата согласия на обработку ПД"
    )

    def __str__(self):
        return f"{self.name} - {self.vacancy.title}"

    class Meta:
        verbose_name = "Кандидат"
        verbose_name_plural = "Кандидаты"
        ordering = ['-applied_at']
    


class Feedback(models.Model):
    STATUS_CHOICES = [
        ('new', '🆕 Новое'),
        ('processed', '📨 Обработано'),
        ('spam', '🗑️ Спам'),
    ]
    
    # Основные поля из формы
    name = models.CharField(
        max_length=150,
        verbose_name='Имя'
    )
    
    contact = models.CharField(
        max_length=100,
        verbose_name='Контактные данные'
    )
    
    message = models.TextField(
        verbose_name='Сообщение'
    )
    
    # ✅ ДОБАВЛЯЕМ ПОЛЕ ДЛЯ СОГЛАСИЯ НА ОБРАБОТКУ ПД
    pd_agreed = models.BooleanField(
        default=False,
        verbose_name='Согласие на обработку персональных данных'
    )
    
    pd_agreed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата согласия на обработку ПД'
    )
    
    # Дополнительные поля для доказательства согласия
    ip_address = models.GenericIPAddressField(
        blank=True,
        null=True,
        verbose_name='IP-адрес'
    )
    
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent'
    )
    
    policy_version = models.CharField(
        max_length=20,
        default='1.0',
        verbose_name='Версия политики'
    )
    
    # Статус обработки
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new',
        verbose_name='Статус'
    )
    
    # Системные поля
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Дата создания'
    )
    
    is_viewed = models.BooleanField(
        default=False,
        verbose_name='Просмотрено'
    )
    
    class Meta:
        verbose_name = 'Обратная связь'
        verbose_name_plural = 'Обратная связь'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.created_at.strftime('%d.%m.%Y')}"
    
    def save(self, *args, **kwargs):
        """Автоматически устанавливаем дату создания для новых записей"""
        if not self.id:
            self.created_at = timezone.now()
        super().save(*args, **kwargs)

# models.py - обновленная модель PromoBlock
class PromoBlock(models.Model):
    STATUS_CHOICES = [
        ('active', 'Активно'),
        ('inactive', 'Неактивно'),
    ]
    
    LAYOUT_CHOICES = [
        ('text_left', 'Текст слева, изображение справа'),
        ('text_right', 'Текст справа, изображение слева'),
        ('text_top', 'Текст сверху, изображение снизу'),
        ('text_bottom', 'Текст снизу, изображение сверху'),
        ('text_overlay', 'Текст поверх изображения'),
        ('text_only', 'Только текст'),
        ('image_only', 'Только изображение'),
    ]
    
    FONT_CHOICES = [
        ('inter', 'Inter'),
        ('roboto', 'Roboto'),
        ('opensans', 'Open Sans'),
        ('montserrat', 'Montserrat'),
        ('playfair', 'Playfair Display'),
        ('lora', 'Lora'),
        ('raleway', 'Raleway'),
        ('ubuntu', 'Ubuntu'),
    ]
    
    TEXT_ALIGN_CHOICES = [
        ('left', 'Слева'),
        ('center', 'По центру'),
        ('right', 'Справа'),
    ]
    
    # Основной контент
    title = models.CharField(max_length=255, verbose_name="Заголовок", blank=True)
    text = models.TextField(verbose_name="Текст", blank=True)
    image = models.ImageField(upload_to='promo/', blank=True, null=True, verbose_name="Изображение")
    video_url = models.URLField(blank=True, verbose_name="URL видео")
    
    # Кнопка
    button_text = models.CharField(max_length=50, blank=True, verbose_name="Текст кнопки")
    button_url = models.CharField(max_length=200, blank=True, verbose_name="Ссылка кнопки")
    
    # Макет и расположение
    layout = models.CharField(max_length=20, choices=LAYOUT_CHOICES, default='text_left', verbose_name="Макет")
    text_align = models.CharField(max_length=10, choices=TEXT_ALIGN_CHOICES, default='left', verbose_name="Выравнивание текста")
    content_position = models.CharField(max_length=20, default='center', verbose_name="Позиция контента")
    use_image_as_background = models.BooleanField(default=False, verbose_name="Использовать изображение как фон")
    background_overlay = models.BooleanField(default=False, verbose_name="Наложение на фон")
    background_overlay_opacity = models.DecimalField(max_digits=3, decimal_places=2, default=0.5, verbose_name="Прозрачность наложения")
    
    # Цвета
    background_color = models.CharField(max_length=7, default='#1E3A8A', verbose_name="Цвет фона")
    text_color = models.CharField(max_length=7, default='#FFFFFF', verbose_name="Цвет текста")
    button_color = models.CharField(max_length=7, default='#C9A96A', verbose_name="Цвет кнопки")
    button_text_color = models.CharField(max_length=7, default='#FFFFFF', verbose_name="Цвет текста кнопки")
    overlay_color = models.CharField(max_length=7, default='#000000', verbose_name="Цвет наложения")
    
    # Шрифты
    font_family = models.CharField(max_length=20, choices=FONT_CHOICES, default='inter', verbose_name="Шрифт")
    title_font_size = models.PositiveIntegerField(default=24, verbose_name="Размер шрифта заголовка")
    text_font_size = models.PositiveIntegerField(default=16, verbose_name="Размер шрифта текста")
    button_font_size = models.PositiveIntegerField(default=16, verbose_name="Размер шрифта кнопки")
    custom_font_url = models.URLField(blank=True, verbose_name="URL кастомного шрифта")
    
    # Размеры и отступы
    block_height = models.PositiveIntegerField(default=300, verbose_name="Высота блока")
    block_width = models.CharField(max_length=20, default='100%', verbose_name="Ширина блока")
    padding_top = models.PositiveIntegerField(default=40, verbose_name="Отступ сверху")
    padding_bottom = models.PositiveIntegerField(default=40, verbose_name="Отступ снизу")
    padding_left = models.PositiveIntegerField(default=40, verbose_name="Отступ слева")
    padding_right = models.PositiveIntegerField(default=40, verbose_name="Отступ справа")
    
    # Эффекты
    background_gradient = models.BooleanField(default=False, verbose_name="Градиентный фон")
    gradient_start = models.CharField(max_length=7, default='#1E3A8A', verbose_name="Начало градиента")
    gradient_end = models.CharField(max_length=7, default='#3B82F6', verbose_name="Конец градиента")
    gradient_angle = models.IntegerField(default=135, verbose_name="Угол градиента")
    shadow_effect = models.BooleanField(default=False, verbose_name="Тень")
    border_radius = models.PositiveIntegerField(default=12, verbose_name="Скругление углов")
    
    # Состояние
    is_active = models.BooleanField(default=False, verbose_name="Активно")
    start_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата начала показа")
    end_date = models.DateTimeField(blank=True, null=True, verbose_name="Дата окончания показа")
    
    # Системные поля
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Промо-блок"
        verbose_name_plural = "Промо-блоки"
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f"Промо-блок #{self.id}"

    def is_currently_active(self):
        """Проверяет, активно ли промо в текущий момент времени"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_date and self.start_date > now:
            return False
        if self.end_date and self.end_date < now:
            return False
            
        return True
    
    def get_css_styles(self):
        """Генерирует CSS стили для блока"""
        styles = []
        
        # Фон
        if self.use_image_as_background and self.image:
            styles.append(f"background-image: url('{self.image.url}');")
            styles.append("background-size: cover;")
            styles.append("background-position: center;")
            if self.background_overlay:
                styles.append(f"position: relative;")
        elif self.background_gradient:
            styles.append(f"background: linear-gradient({self.gradient_angle}deg, {self.gradient_start}, {self.gradient_end});")
        else:
            styles.append(f"background-color: {self.background_color};")
        
        # Тень
        if self.shadow_effect:
            styles.append("box-shadow: 0 10px 30px rgba(0,0,0,0.15);")
        
        # Скругление
        styles.append(f"border-radius: {self.border_radius}px;")
        
        # Размеры
        styles.append(f"height: {self.block_height}px;")
        styles.append(f"width: {self.block_width};")
        
        # Отступы
        styles.append(f"padding: {self.padding_top}px {self.padding_right}px {self.padding_bottom}px {self.padding_left}px;")
        
        return " ".join(styles)
    
    # Добавьте в конец файла crm/models.py

class InternalNotification(models.Model):
    """
    Модель для внутренних уведомлений в CRM системе.
    Позволяет отправлять уведомления между сотрудниками внутри системы.
    """
    NOTIFICATION_TYPES = [
        ('new_request', '🆕 Новая заявка'),
        ('request_assigned', '👤 Назначение заявки'),
        ('status_changed', '🔄 Изменение статуса'),
        ('new_comment', '💬 Новый комментарий'),
        ('new_feedback', '📨 Новое сообщение'),
        ('new_candidate', '🎯 Новый кандидат'),
        ('system', '⚙️ Системное уведомление'),
    ]
    
    recipient = models.ForeignKey(
        ManagerProfile, 
        on_delete=models.CASCADE, 
        related_name='notifications', 
        verbose_name='Получатель'
    )
    notification_type = models.CharField(
        max_length=50, 
        choices=NOTIFICATION_TYPES, 
        verbose_name='Тип уведомления'
    )
    title = models.CharField(
        max_length=255, 
        verbose_name='Заголовок'
    )
    message = models.TextField(
        verbose_name='Сообщение'
    )
    link = models.CharField(
        max_length=500, 
        blank=True, 
        null=True, 
        verbose_name='Ссылка'
    )
    is_read = models.BooleanField(
        default=False, 
        verbose_name='Прочитано'
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name='Дата создания'
    )
    related_object_id = models.PositiveIntegerField(
        blank=True, 
        null=True, 
        verbose_name='ID связанного объекта'
    )
    related_object_type = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name='Тип связанного объекта'
    )
    
    class Meta:
        verbose_name = 'Внутреннее уведомление'
        verbose_name_plural = 'Внутренние уведомления'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()}: {self.title} -> {self.recipient.user.username}"
    
    def mark_as_read(self):
        """Отметить уведомление как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
            return True
        return False
    
    @classmethod
    def get_unread_count(cls, recipient):
        """Получить количество непрочитанных уведомлений для пользователя"""
        return cls.objects.filter(recipient=recipient, is_read=False).count()
    
    @classmethod
    def mark_all_as_read(cls, recipient):
        """Отметить все уведомления пользователя как прочитанные"""
        return cls.objects.filter(recipient=recipient, is_read=False).update(is_read=True)