import os
import re
import sys
from pathlib import Path

import environ

from core.utils import CustomJsonEncoder

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

sys.path.append(str(BASE_DIR / 'apps'))

# Load environment variables from .env file
env = environ.Env()
env.read_env(os.path.join(BASE_DIR, '.env'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env(
    'SECRET_KEY',
    default='django-insecure-3472^sitrt^-xx#!u-t_4bi2ac5&6^i8%0s9!3!zyy#uf#rq44',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['*'])

SITE_ID = 1

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.postgres',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    # Third party apps
    'django_vite',
    'inertia',
    'import_export',
    'django_q',
    # Local apps
    'contas',
    'chat',
    'respostas_canonicas',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'inertia.middleware.InertiaMiddleware',
    'core.middleware.DataShareMiddleware',
]
if DEBUG:
    MIDDLEWARE.insert(0, 'core.middleware.FlushStdoutMiddleware')

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'frontend'],
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

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

if 'DATABASE_URL' in env:
    DATABASES = {'default': env.db()}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'chatbot-integracar',
            'USER': 'postgres',
            'PASSWORD': 'postgres',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTH_USER_MODEL = 'contas.Usuario'

AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
]

LOGIN_URL = 'entrar'


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'static'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# If use HMR or not.
DJANGO_VITE = {
    'default': {
        'dev_mode': DEBUG,
        'dev_server_host': env.str(
            'DJANGO_VITE_DEV_SERVER_HOST', default='localhost'
        ),
        'dev_server_port': env.int(
            'DJANGO_VITE_DEV_SERVER_PORT', default=5173
        ),
    }
}
# Where ViteJS assets are built.
DJANGO_VITE_ASSETS_PATH = BASE_DIR / 'frontend' / 'dist'
STATICFILES_DIRS = [DJANGO_VITE_ASSETS_PATH, BASE_DIR / 'frontend' / 'static']

INERTIA_LAYOUT = 'base.html'
INERTIA_SSR_URL = env.str(
    'INERTIA_SSR_URL',
    default='http://localhost:13714',
)
INERTIA_SSR_ENABLED = env.bool('INERTIA_SSR_ENABLED', default=False)
INERTIA_JSON_ENCODER = CustomJsonEncoder

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# http://whitenoise.evans.io/en/stable/django.html#WHITENOISE_IMMUTABLE_FILE_TEST
def immutable_file_test(path, url):
    # Match vite (rollup)-generated hashes, à la, `some_file-CSliV9zW.js`
    return re.match(r'^.+[.-][0-9a-zA-Z_-]{8,12}\..+$', url)


WHITENOISE_IMMUTABLE_FILE_TEST = immutable_file_test

OPENAI_API_KEY = env.str('OPENAI_API_KEY', default='')
INTEGRACAR_CHAT_MODEL = env.str(
    'INTEGRACAR_CHAT_MODEL',
    default='gpt-6-luna',
)

# Upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

Q_CLUSTER = {
    'name': 'chatbot-integracar',
    'workers': 2,
    'timeout': 100,
    'retry': 120,
    'queue_limit': 50,
    'max_attempts': 1,
    'orm': 'default',
}
