"""
Django settings for setup project.
"""

from pathlib import Path
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
import dj_database_url

# Project root (parent of this package). Load .env only from here so CWD / IDE cwd never matters.
BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=True)

# Quick-start development settings
DEBUG = os.getenv('DEBUG', 'True') == 'True'

secret_key_env = os.getenv('SECRET_KEY')
if not DEBUG and not secret_key_env:
    raise ImproperlyConfigured("A SECRET_KEY deve estar configurada em produção!")
SECRET_KEY = secret_key_env or 'chave-insegura-apenas-para-dev-local-jesap'

# ALLOWED_HOSTS
if DEBUG:
    ALLOWED_HOSTS = ['*']
else:
    hosts_env = os.getenv('ALLOWED_HOSTS', '')
    if not hosts_env:
        raise ImproperlyConfigured("ALLOWED_HOSTS must be configured in production")
    ALLOWED_HOSTS = [host.strip() for host in hosts_env.split(',')]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dashboard',
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
    'dashboard.audit.CurrentUserMiddleware',
]

ROOT_URLCONF = 'setup.urls'

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

WSGI_APPLICATION = 'setup.wsgi.application'

# Database
FORCE_SQLITE = os.getenv("USE_SQLITE", "").lower() in {"1", "true", "yes", "y", "on"}
FORCE_POSTGRES = os.getenv("USE_POSTGRES", "").lower() in {"1", "true", "yes", "y", "on"}
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_DIRECT_DB_HOST = os.getenv("SUPABASE_DIRECT_DB_HOST") 

if FORCE_POSTGRES and not DATABASE_URL:
    raise ImproperlyConfigured("USE_POSTGRES / FORCE_POSTGRES is set but DATABASE_URL is missing.")

if FORCE_SQLITE or not DATABASE_URL:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    if not DATABASE_URL:
        raise ImproperlyConfigured("DATABASE_URL must be set when USE_POSTGRES is enabled.")

    if SUPABASE_DIRECT_DB_HOST:
        try:
            parsed = urlparse(DATABASE_URL)
            if parsed.hostname and parsed.hostname != SUPABASE_DIRECT_DB_HOST:
                DATABASE_URL = DATABASE_URL.replace(parsed.hostname, SUPABASE_DIRECT_DB_HOST, 1)
        except Exception:
            pass

    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
        )
    }
    
    engine = DATABASES["default"].get("ENGINE", "")
    if engine.endswith("postgresql") or engine.endswith("postgresql_psycopg2") or engine.endswith("postgresql_psycopg"):
        DATABASES["default"].setdefault("OPTIONS", {})
        DATABASES["default"]["OPTIONS"].setdefault("sslmode", os.getenv("PGSSLMODE", "require"))

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'it' # Messo in italiano per i messaggi base di Django
TIME_ZONE = 'Europe/Rome'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise: compressed + manifest hashing per cache-busting
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Auth redirects
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"

# Sessione/Cookie hardening: HttpOnly sempre, Secure+SameSite in prod (DEBUG=False).
# Django usa session cookies (server-side), nessun token in localStorage.
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Railway/proxy: TLS terminato a monte, header X-Forwarded-Proto indica https reale
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Domini accettati per richieste POST/CSRF (CSV via env)
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv(
        'CSRF_TRUSTED_ORIGINS',
        'https://*.up.railway.app'
    ).split(',') if o.strip()
]

# Login con username o email (case-insensitive)
AUTHENTICATION_BACKENDS = [
    "dashboard.auth_backends.EmailOrUsernameModelBackend",
]

# Email: console backend automatico quando SMTP non configurato (dev senza crash).
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'JESAP ERP <noreply@jesap.it>')

_default_email_backend = (
    'django.core.mail.backends.smtp.EmailBackend'
    if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD
    else 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', _default_email_backend)
LOGOUT_REDIRECT_URL = "login"

# Logging: stdout (Railway raccoglie automaticamente)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': os.getenv('LOG_LEVEL', 'INFO')},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'django.request': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}