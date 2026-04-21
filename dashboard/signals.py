from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

from .audit import diff, snapshot, write_log
from .models import Partnership, PartnershipNonFin, Progetti


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    """Send a welcome email when a new User is created."""
    if not created:
        return

    login_url = getattr(settings, 'LOGIN_URL_ABSOLUTE', 'http://localhost:8000/login/')

    context = {
        'user': instance,
        'login_url': login_url,
    }

    text_body = render_to_string('registration/welcome_email.txt', context)
    html_body = render_to_string('registration/welcome_email.html', context)

    msg = EmailMultiAlternatives(
        subject='Benvenuto su JESAP ERP!',
        body=text_body,
        from_email=None,  # uses DEFAULT_FROM_EMAIL
        to=[instance.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=True)


AUDITED_MODELS = (Partnership, PartnershipNonFin, Progetti)


@receiver(pre_save)
def _capture_previous_state(sender, instance, **kwargs):
    if sender not in AUDITED_MODELS:
        return
    if instance.pk is None:
        instance._audit_previous = None
        return
    try:
        previous = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._audit_previous = None
    else:
        instance._audit_previous = snapshot(previous)


@receiver(post_save)
def _log_save(sender, instance, created, **kwargs):
    if sender not in AUDITED_MODELS:
        return
    new_state = snapshot(instance)
    previous = getattr(instance, '_audit_previous', None)
    if created:
        write_log(instance, 'create', changes=diff(None, new_state))
    else:
        changes = diff(previous, new_state)
        if changes:
            write_log(instance, 'update', changes=changes)


@receiver(post_delete)
def _log_delete(sender, instance, **kwargs):
    if sender not in AUDITED_MODELS:
        return
    write_log(instance, 'delete', changes=diff(snapshot(instance), {}))
