import os
import sys
import django

# Указываем настройки Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'argus_site.settings')

# Добавляем путь к проекту (если нужно)
sys.path.append('C:/Users/afana/Desktop/диплом прога/argus_site')

# Инициализируем Django
django.setup()

from django.contrib.auth.models import User
from django.contrib.auth.hashers import make_password
import psycopg2

def update_admin_credentials():
    # Новые данные
    NEW_USERNAME = 'admin'  # Оставьте admin или измените
    NEW_PASSWORD = 'admin123'  # Новый пароль
    
    try:
        # Способ 1: через Django ORM (рекомендуется)
        admin = User.objects.get(username='admin')
        admin.set_password(NEW_PASSWORD)
        admin.save()
        
        print(f"✅ Пароль для пользователя '{admin.username}' изменен на '{NEW_PASSWORD}'")
        
    except User.DoesNotExist:
        print("❌ Пользователь admin не найден")
        print("Создаем нового...")
        User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password=NEW_PASSWORD
        )
        print(f"✅ Создан новый администратор: admin / {NEW_PASSWORD}")

if __name__ == '__main__':
    update_admin_credentials()