from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


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
