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
