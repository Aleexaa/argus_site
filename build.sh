#!/bin/bash
set -e

echo "=== Установка зависимостей ==="
pip install -r requirements.txt

echo "=== Создание миграций ==="
python manage.py makemigrations --noinput

echo "=== Применение миграций ==="
python manage.py migrate --noinput

echo "=== Сборка статических файлов ==="
python manage.py collectstatic --noinput

echo "=== Сборка завершена ==="