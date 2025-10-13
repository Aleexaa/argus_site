#!/usr/bin/env bash
# Скрипт сборки для Render.com

set -o errexit

# Установка зависимостей
pip install -r requirements.txt

# Применение миграций базы данных
python manage.py migrate

# Сборка статических файлов
python manage.py collectstatic --noinput