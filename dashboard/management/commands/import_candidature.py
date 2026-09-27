"""Importa le risposte al form di candidatura (export CSV del foglio risposte).

Uso:
    python manage.py import_candidature risposte.csv --sessione "Spring REC 26" --dry-run
    python manage.py import_candidature risposte.csv --sessione "Spring REC 26" --crea-sessione

- Intestazioni riconosciute come nel webhook (vedi dashboard/recruitment/intake.py).
- Idempotente: le righe già importate vengono saltate; stessa email ricandidata → 'Doppione'.
- NON invia email ai candidati.
"""
import csv

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dashboard.models import RecruitmentSessione
from dashboard.recruitment.intake import RispostaNonValida, registra_candidatura


class Command(BaseCommand):
    help = 'Importa candidature da un CSV esportato dal foglio risposte del form.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--sessione', required=True, help='Nome della sessione (es. "Spring REC 26").')
        parser.add_argument('--crea-sessione', action='store_true', help='Crea la sessione se non esiste (chiusa).')
        parser.add_argument('--dry-run', action='store_true', help='Mostra cosa farebbe senza scrivere nel DB.')

    def handle(self, csv_path, sessione, crea_sessione, dry_run, **options):
        try:
            with open(csv_path, newline='', encoding='utf-8-sig') as fh:
                righe = list(csv.DictReader(fh))
        except OSError as exc:
            raise CommandError(f'Impossibile leggere {csv_path}: {exc}')

        conteggi = {'creato': 0, 'doppione': 0, 'duplicato': 0}
        errori = []
        with transaction.atomic():
            sess = RecruitmentSessione.objects.filter(nome=sessione).first()
            if sess is None:
                if not crea_sessione:
                    raise CommandError(f'Sessione "{sessione}" inesistente. Usa --crea-sessione per crearla.')
                sess = RecruitmentSessione.objects.create(nome=sessione, aperta=False)
            for n, riga in enumerate(righe, start=2):
                if not any((v or '').strip() for v in riga.values() if isinstance(v, str)):
                    continue
                try:
                    _, stato = registra_candidatura(sess, riga)
                except RispostaNonValida as exc:
                    errori.append(f'riga {n}: {exc}')
                    continue
                conteggi[stato] += 1
            if dry_run:
                transaction.set_rollback(True)

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}{sess.nome}: {conteggi["creato"]} candidature importate, '
            f'{conteggi["doppione"]} doppioni (segnati "Doppione"), {conteggi["duplicato"]} già presenti.'
        ))
        for e in errori:
            self.stdout.write(self.style.WARNING(e))
