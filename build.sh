#!/usr/bin/env bash
# build.sh

echo "Building Django project..."
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate