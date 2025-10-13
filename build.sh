#!/usr/bin/env bash
set -o errexit

# Обновляем pip
pip install --upgrade pip

# Устанавливаем зависимости
pip install -r requirements.txt

# Собираем статические файлы
python manage.py collectstatic --noinput --clear

# Применяем миграции
python manage.py migrate