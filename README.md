# Argus Site

Django проект с приложениями:
- main - главное приложение
- crm - система управления клиентами

## Установка

1. Клонируйте репозиторий
2. Создайте виртуальное окружение
3. Установите зависимости: `pip install -r requirements.txt`
4. Выполните миграции: `python manage.py migrate`
5. Создайте суперпользователя: `python manage.py createsuperuser`
6. Запустите сервер: `python manage.py runserver`