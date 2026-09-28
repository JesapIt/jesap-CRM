"""Cifratura simmetrica (Fernet) dei segreti dell'area Credenziali.

La chiave vive SOLO nell'env `CREDENTIALS_ENCRYPTION_KEY` (Railway), mai nel DB:
un dump di Supabase espone solo token cifrati.
Rotazione: più chiavi separate da virgola → la prima cifra, tutte decifrano.

Generare una chiave:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from cryptography.fernet import Fernet, InvalidToken, MultiFernet  # noqa: F401 (InvalidToken ri-esportato)
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


class CryptoNotConfigured(ImproperlyConfigured):
    pass


def _fernet():
    raw = getattr(settings, 'CREDENTIALS_ENCRYPTION_KEY', '') or ''
    keys = [k.strip() for k in raw.split(',') if k.strip()]
    if not keys:
        raise CryptoNotConfigured('CREDENTIALS_ENCRYPTION_KEY non configurata.')
    try:
        return MultiFernet([Fernet(k) for k in keys])
    except ValueError as exc:
        raise CryptoNotConfigured('CREDENTIALS_ENCRYPTION_KEY non valida.') from exc


def is_configured():
    try:
        _fernet()
    except CryptoNotConfigured:
        return False
    return True


def encrypt(plaintext):
    if not plaintext:
        return ''
    return _fernet().encrypt(plaintext.encode('utf-8')).decode('ascii')


def decrypt(token):
    if not token:
        return ''
    return _fernet().decrypt(token.encode('ascii')).decode('utf-8')
