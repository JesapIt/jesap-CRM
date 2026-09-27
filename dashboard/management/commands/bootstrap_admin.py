from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

DEV_PASSWORD = 'jesap2026'


class Command(BaseCommand):
    help = "Crea/aggiorna un superuser di sviluppo (idempotente)."

    def add_arguments(self, parser):
        parser.add_argument('--username', default='admin')
        parser.add_argument('--email', default='admin@jesap.it')
        parser.add_argument('--password', default=DEV_PASSWORD)

    def handle(self, *args, **opts):
        User = get_user_model()
        username = opts['username']
        email = opts['email']
        password = opts['password']
        if password == DEV_PASSWORD and not settings.DEBUG:
            raise CommandError(
                "Password di sviluppo non ammessa con DEBUG=False: passa --password."
            )

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email, 'is_staff': True, 'is_superuser': True, 'is_active': True},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        action = 'creato' if created else 'aggiornato'
        self.stdout.write(self.style.SUCCESS(
            f"Superuser {action}: username={username} email={email} password={password}"
        ))
