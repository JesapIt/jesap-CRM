"""Settings dedicate ai test.

- Stub `dotenv.load_dotenv` PRIMA che `setup.settings` lo invochi, così il
  `.env` di produzione non sovrascrive l'ambiente.
- Forza SQLite in-memory: i test non devono mai toccare Supabase.
"""
import os

import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: True

os.environ["USE_SQLITE"] = "1"
os.environ.pop("DATABASE_URL", None)
os.environ.pop("USE_POSTGRES", None)

from setup.settings import *  # noqa: F401,F403,E402

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# I test girano senza `collectstatic`: niente manifest né STATIC_ROOT per WhiteNoise.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MIDDLEWARE = [m for m in MIDDLEWARE if not m.startswith("whitenoise.")]  # noqa: F405

# Chiave usa-e-getta per i test dell'area Credenziali.
from cryptography.fernet import Fernet  # noqa: E402

CREDENTIALS_ENCRYPTION_KEY = Fernet.generate_key().decode()

# Recruitment: niente pause tra gli invii nei test
RECRUITMENT_EMAIL_PAUSE = 0
RECRUITMENT_WEBHOOK_TOKEN = 'test-token'
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
