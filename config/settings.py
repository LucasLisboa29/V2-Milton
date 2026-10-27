"""Configurações do projeto Custos por Serviço.

Segredos e opções de produção vêm de variáveis de ambiente (RNF-05: nenhum
segredo no repositório). Os valores padrão servem só para desenvolvimento.
"""

import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# A Vercel define VERCEL=1 nos deploys. Lá o padrão é produção: DEBUG desligado,
# senão qualquer erro mostraria configurações internas para quem acessar o site.
NA_VERCEL = os.environ.get('VERCEL') == '1'

DEBUG = os.environ.get('DJANGO_DEBUG', '0' if NA_VERCEL else '1') == '1'

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-apenas-nao-usar-em-producao')
if not DEBUG and SECRET_KEY.startswith('dev-'):
    raise RuntimeError('Defina DJANGO_SECRET_KEY em produção.')

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
if NA_VERCEL:
    ALLOWED_HOSTS.append('.vercel.app')  # domínio fixo e endereços de cada deploy
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if o]

# A Vercel recebe o HTTPS e repassa ao Django; este cabeçalho diz que a conexão original era segura.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'servicos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # serve o CSS em produção
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # RNF-05/06: nenhuma tela fica acessível sem login.
    'servicos.middleware.LoginObrigatorioMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Em produção, DATABASE_URL aponta para um PostgreSQL (ex.: Neon). Sem ela, usa SQLite local.
# Na Vercel o disco é apagado a cada requisição, então SQLite lá perderia todos os dados.
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=0 if NA_VERCEL else 60,
    )
}
if NA_VERCEL and DATABASES['default']['ENGINE'].endswith('sqlite3'):
    raise RuntimeError('Defina DATABASE_URL (PostgreSQL) nas variáveis de ambiente da Vercel.')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# RS-04 / RNF-09: português do Brasil, horário de São Paulo.
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
# Serve direto das pastas static/ dos apps, sem depender de collectstatic no build.
WHITENOISE_USE_FINDERS = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'servicos:lista'
LOGOUT_REDIRECT_URL = 'login'

# UC01: sessão expira após 7 dias sem uso (celular pessoal).
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
