"""
Django settings for setup project.
"""

from pathlib import Path
import os
import sys
from urllib.parse import urlparse
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured
import dj_database_url

# Project root (parent of this package). Load .env only from here so CWD / IDE cwd never matters.
BASE_DIR = Path(__file__).resolve().parent.parent
_ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=_ENV_FILE, override=True)


def _env(key: str, default: str = "") -> str:
    """Legge env var, strippa whitespace + virgolette letterali."""
    return (os.getenv(key) or default).strip().strip('"').strip("'")


# Diagnostica: stampa quali env critiche sono presenti (solo nomi, no valori)
_critical_keys = ["DEBUG", "SECRET_KEY", "DATABASE_URL", "USE_POSTGRES",
                  "ALLOWED_HOSTS", "CSRF_TRUSTED_ORIGINS", "RAILWAY_ENVIRONMENT",
                  "RAILWAY_PROJECT_ID", "PORT"]
_present = [k for k in _critical_keys if os.getenv(k)]
_missing = [k for k in _critical_keys if not os.getenv(k)]
print(f"[settings:env] presenti={_present} mancanti={_missing}",
      file=sys.stderr, flush=True)

# Detect Railway runtime — se siamo lì, DATABASE_URL è OBBLIGATORIA
ON_RAILWAY = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"))

# Default sicuro: su Railway senza DEBUG esplicito → produzione.
DEBUG = _env('DEBUG', 'False' if ON_RAILWAY else 'True') == 'True'

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
    # Railway healthcheck hostname must always be allowed
    if 'healthcheck.railway.app' not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append('healthcheck.railway.app')

# Application definition
INSTALLED_APPS = [
    # Prima di admin/auth: i template `registration/*` custom devono avere precedenza
    # su quelli built-in (email reset password, subject).
    'dashboard',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'anymail',
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
FORCE_SQLITE = _env("USE_SQLITE").lower() in {"1", "true", "yes", "y", "on"}
FORCE_POSTGRES = _env("USE_POSTGRES").lower() in {"1", "true", "yes", "y", "on"}
DATABASE_URL = _env("DATABASE_URL")
SUPABASE_DIRECT_DB_HOST = _env("SUPABASE_DIRECT_DB_HOST") or None

# Fail-fast su Railway: se DATABASE_URL manca, esplodi subito con errore
# chiaro nei log invece di cadere su SQLite (che produce errori criptici).
if ON_RAILWAY and not DATABASE_URL:
    raise ImproperlyConfigured(
        "RAILWAY DEPLOY: DATABASE_URL è VUOTA o mancante. "
        "Vai su Railway → tuo servizio → Variables → aggiungi DATABASE_URL "
        "col valore postgresql://...supabase.co.../postgres "
        "Quindi redeploya."
    )

# Validazione esplicita: scheme deve essere postgresql/postgres/sqlite ecc.
# Senza questo, dj_database_url solleva "Scheme '://' is unknown" criptico.
if DATABASE_URL and "://" in DATABASE_URL:
    _scheme = DATABASE_URL.split("://", 1)[0].strip()
    if not _scheme:
        raise ImproperlyConfigured(
            f"DATABASE_URL malformata: scheme vuoto. "
            f"Valore ricevuto inizia con: {DATABASE_URL[:30]!r}. "
            f"Atteso es. 'postgresql://user:pass@host:port/db'."
        )

if FORCE_POSTGRES and not DATABASE_URL:
    raise ImproperlyConfigured("USE_POSTGRES / FORCE_POSTGRES is set but DATABASE_URL is missing.")

# Guard di produzione: in prod (DEBUG=False) NON è permesso il fallback silenzioso
# a SQLite. È quasi sempre un errore di configurazione (DATABASE_URL non arriva).
if not DEBUG and (FORCE_SQLITE or not DATABASE_URL):
    raise ImproperlyConfigured(
        "Produzione: DATABASE_URL deve essere settata e USE_SQLITE deve essere off. "
        "Configura DATABASE_URL nelle env vars del provider (Railway/Heroku/...)."
    )

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

# Startup log: quale DB sta usando l'app. Visibile nei Deploy Logs Railway.
_engine = DATABASES["default"].get("ENGINE", "?")
_host = DATABASES["default"].get("HOST", "(file)")
print(
    f"[settings] DB engine={_engine} host={_host} DEBUG={DEBUG} "
    f"USE_POSTGRES={FORCE_POSTGRES} DATABASE_URL_set={bool(DATABASE_URL)}",
    file=sys.stderr, flush=True,
)

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

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

# Link reset password valido 24h (come dichiarato nel testo dell'email).
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

# Sessione/Cookie hardening: HttpOnly sempre, Secure+SameSite in prod (DEBUG=False).
# Django usa session cookies (server-side), nessun token in localStorage.
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
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

# URL pubblica del sito (usata in email transazionali). Senza slash finale.
SITE_URL = os.getenv('SITE_URL', 'http://localhost:8000').rstrip('/')

# Login con username o email (case-insensitive)
AUTHENTICATION_BACKENDS = [
    "dashboard.auth_backends.EmailOrUsernameModelBackend",
]

# Email: Resend via HTTP API (django-anymail). Bypassa block SMTP outbound Railway.
# Fallback console backend in dev se RESEND_API_KEY non settata.
RESEND_API_KEY = _env('RESEND_API_KEY', '')
DEFAULT_FROM_EMAIL = _env('DEFAULT_FROM_EMAIL', 'JESAP CRM <onboarding@resend.dev>')

if RESEND_API_KEY:
    EMAIL_BACKEND = 'anymail.backends.resend.EmailBackend'
    ANYMAIL = {
        'RESEND_API_KEY': RESEND_API_KEY,
    }
else:
    EMAIL_BACKEND = _env('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

print(f"[settings:email] backend={EMAIL_BACKEND} resend_key={'<SET>' if RESEND_API_KEY else '<EMPTY>'} "
      f"from={DEFAULT_FROM_EMAIL}",
      file=sys.stderr, flush=True)
LOGOUT_REDIRECT_URL = "login"

# Area Credenziali: chiave Fernet (vedi dashboard/crypto.py). Mai nel DB.
# Assente → il resto del CRM funziona, l'area Credenziali mostra un errore.
CREDENTIALS_ENCRYPTION_KEY = _env('CREDENTIALS_ENCRYPTION_KEY', '')
print(f"[settings:credenziali] encryption_key={'<SET>' if CREDENTIALS_ENCRYPTION_KEY else '<EMPTY>'}",
      file=sys.stderr, flush=True)

# Recruitment
# Token condiviso con l'Apps Script del foglio risposte (webhook candidature).
RECRUITMENT_WEBHOOK_TOKEN = _env('RECRUITMENT_WEBHOOK_TOKEN', '')
# Mittente / risposte delle email ai candidati (vuoto → DEFAULT_FROM_EMAIL, nessun reply-to).
RECRUITMENT_FROM_EMAIL = _env('RECRUITMENT_FROM_EMAIL', '')
RECRUITMENT_REPLY_TO = _env('RECRUITMENT_REPLY_TO', '')
# Invii in blocco: max email per click + pausa tra un invio e l'altro (rate limit Resend).
RECRUITMENT_EMAIL_BATCH = 40
RECRUITMENT_EMAIL_PAUSE = 0.5
# Le tabelle recruitment si salvano in blocco (una riga = ~15 campi).
DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000
print(f"[settings:recruitment] webhook_token={'<SET>' if RECRUITMENT_WEBHOOK_TOKEN else '<EMPTY>'} "
      f"reply_to={RECRUITMENT_REPLY_TO or '<EMPTY>'}", file=sys.stderr, flush=True)

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