import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _
import dj_database_url

# === БАЗОВАЯ КОНФИГУРАЦИЯ ===
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'please-set-DJANGO_SECRET_KEY-in-env')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['honest-transformation.up.railway.app', '.railway.app', '127.0.0.1', 'localhost']

# === ПРИЛОЖЕНИЯ ===
INSTALLED_APPS = [
    # Django стандарт
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Библиотеки
    'widget_tweaks',

    # Наши приложения
    'main',
    'crm',
]

# === MIDDLEWARE ===
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware',  # включи на продакшне
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# === URL и шаблоны ===
ROOT_URLCONF = 'argus_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # глобальные шаблоны
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'argus_site.wsgi.application'

# === БАЗА ДАННЫХ ===
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('POSTGRES_DB', 'argus_db'),
#         'USER': os.getenv('POSTGRES_USER', 'argus_user'),
#         'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'strong_password'),
#         'HOST': os.getenv('POSTGRES_HOST', 'localhost'),
#         'PORT': os.getenv('POSTGRES_PORT', '5432'),
#         'OPTIONS': {'client_encoding': 'UTF8'},
#     }

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}
# === ВАЛИДАЦИЯ ПАРОЛЕЙ ===
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# === ЛОКАЛИЗАЦИЯ ===
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# === СТАТИКА И МЕДИА ===
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# === КРАСИВЫЙ CRM HEADER ===
ADMIN_SITE_HEADER = _("CRM Аргус")
ADMIN_SITE_TITLE = _("CRM Аргус — панель управления")
ADMIN_INDEX_TITLE = _("Добро пожаловать в систему управления проектами")

# === EMAIL (уведомления менеджерам и клиентам) ===
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_USER', 'afanaseva.sasha.a@gmail.com')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_PASSWORD', 'alki anyf excw jckq')  # обязательно замени!
DEFAULT_FROM_EMAIL = 'Аргус <noreply@argus.ru>'

# 💡 Для локальной отладки:
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# === ЛОГИ ===
LOG_LEVEL = os.getenv('DJANGO_LOG_LEVEL', 'INFO')
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'root': {'handlers': ['console'], 'level': LOG_LEVEL},
}

# === БЕЗОПАСНОСТЬ ===
SECURE_SSL_REDIRECT = os.getenv('DJANGO_SECURE_SSL_REDIRECT', 'False') == 'True'
CSRF_COOKIE_SECURE = os.getenv('DJANGO_CSRF_COOKIE_SECURE', 'False') == 'True'
SESSION_COOKIE_SECURE = os.getenv('DJANGO_SESSION_COOKIE_SECURE', 'False') == 'True'
SECURE_HSTS_SECONDS = int(os.getenv('DJANGO_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv('DJANGO_HSTS_INCLUDE_SUBDOMAINS', 'False') == 'True'
SECURE_HSTS_PRELOAD = os.getenv('DJANGO_HSTS_PRELOAD', 'False') == 'True'

# === DEFAULT FIELD ===
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = '/crm/'
LOGOUT_REDIRECT_URL = '/login/'
LOGIN_URL = '/login/'