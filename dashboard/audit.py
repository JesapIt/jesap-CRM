import threading

from django.contrib.contenttypes.models import ContentType

_state = threading.local()


def set_current_user(user):
    _state.user = user


def get_current_user():
    return getattr(_state, 'user', None)


def clear_current_user():
    if hasattr(_state, 'user'):
        del _state.user


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        set_current_user(getattr(request, 'user', None))
        try:
            return self.get_response(request)
        finally:
            clear_current_user()


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def snapshot(instance):
    data = {}
    for field in instance._meta.concrete_fields:
        data[field.name] = _serialize(getattr(instance, field.attname, None))
    return data


def diff(old, new):
    if old is None:
        return {k: {'old': None, 'new': v} for k, v in new.items() if v not in (None, '')}
    changes = {}
    keys = set(old.keys()) | set(new.keys())
    for key in keys:
        o = old.get(key)
        n = new.get(key)
        if o != n:
            changes[key] = {'old': o, 'new': n}
    return changes


def write_log(instance, action, changes=None):
    from .models import AuditLog

    user = get_current_user()
    authenticated = bool(user and getattr(user, 'is_authenticated', False))

    try:
        ct = ContentType.objects.get_for_model(instance.__class__)
    except Exception:
        ct = None

    AuditLog.objects.create(
        user=user if authenticated else None,
        user_repr=(user.get_username() if authenticated else 'system/anonymous'),
        action=action,
        content_type=ct,
        object_pk=str(instance.pk) if instance.pk is not None else '',
        object_repr=str(instance)[:255],
        changes=changes or {},
    )
