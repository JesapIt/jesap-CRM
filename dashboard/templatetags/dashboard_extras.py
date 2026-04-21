from django import template

register = template.Library()


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