"""
Invia un'email di prova tramite il backend Django configurato in settings.
Usa: python manage.py send_test_email destinatario@esempio.com
"""

from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Invia un'email di prova tramite Django send_mail."

    def add_arguments(self, parser):
        parser.add_argument('to', help='Indirizzo email destinatario')

    def handle(self, *args, **options):
        to = options['to']
        self.stdout.write(f"Invio email di prova a {to} …")

        send_mail(
            subject='Test SMTP — JESAP ERP',
            message='Se leggi questo messaggio, la configurazione SMTP è corretta.',
            from_email=None,   # usa DEFAULT_FROM_EMAIL
            recipient_list=[to],
            fail_silently=False,
        )

        self.stdout.write(self.style.SUCCESS(f"OK — email inviata a {to}"))
