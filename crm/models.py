from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone 
from django.conf import settings  # Добавьте этот импорт
from main.models import Request
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
    company_name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.company_name


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
    'main.Request',  # Если модель в приложении main
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