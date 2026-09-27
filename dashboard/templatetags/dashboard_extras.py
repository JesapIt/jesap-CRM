from django import template

from dashboard.utils.parsing import format_eur, parse_money

register = template.Library()


@register.filter
def eur(value):
    """'€ 1234,5' / '1.234,56' / '1234.5' → '1.234,50 €'. Testo non numerico invariato."""
    try:
        amount = parse_money(value)
    except ValueError:
        return value
    return format_eur(amount) if amount is not None else value


@register.filter
def split(value, sep=' '):
    if value is None:
        return []
    return str(value).split(sep)


@register.filter
def get_field(form, name):
    try:
        return form[name]
    except KeyError:
        return ''


@register.filter
def format_username(value):
    """
    'daniele.tegliucci' -> 'Daniele Tegliucci'
    """
    if not value:
        return value
    formatted = value.replace('.', ' ').replace('_', ' ')
    return formatted.title()


@register.filter
def user_initials(user):
    """
    Return uppercase initials. Tries first_name/last_name first,
    falls back to parsing 'name.surname' from the email local part.
    """
    fn = (getattr(user, 'first_name', '') or '').strip()
    ln = (getattr(user, 'last_name', '') or '').strip()

    if fn and ln:
        return (fn[0] + ln[0]).upper()

    email = (getattr(user, 'email', '') or '').strip()
    if email and '@' in email:
        local = email.split('@')[0]
        parts = local.replace('_', '.').split('.')
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        if parts and parts[0]:
            return parts[0][0].upper()

    username = (getattr(user, 'username', '') or '').strip()
    if username:
        parts = username.replace('_', '.').split('.')
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return username[0].upper()

    return 'JE'


@register.filter
def user_first_name(user):
    """
    Return user's first name. Falls back to extracting the first
    part of 'name.surname' from email or username, title-cased.
    """
    fn = (getattr(user, 'first_name', '') or '').strip()
    if fn:
        return fn

    email = (getattr(user, 'email', '') or '').strip()
    if email and '@' in email:
        local = email.split('@')[0]
        parts = local.replace('_', '.').split('.')
        if parts and parts[0]:
            return parts[0].title()

    username = (getattr(user, 'username', '') or '').strip()
    if username:
        parts = username.replace('_', '.').split('.')
        if parts and parts[0]:
            return parts[0].title()

    return 'Socio'

@register.filter
def can_access_credenziali(user):
    """True se l'utente è CdA o responsabile (vedi dashboard/permissions.py)."""
    from dashboard.permissions import can_access_credenziali as _check
    return _check(user)


@register.filter
def is_http_url(value):
    """Solo link http(s) diventano <a href>: blocca `javascript:` & co."""
    return str(value or '').strip().lower().startswith(('http://', 'https://'))


@register.filter
def can_access_recruitment(user):
    """True se l'utente può vedere la sezione Recruitment."""
    from dashboard.permissions import can_access_recruitment as _check
    return _check(user)
