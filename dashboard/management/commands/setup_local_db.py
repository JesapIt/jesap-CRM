"""Solo sviluppo locale: prepara db.sqlite3 per girare senza Supabase.

I modelli business (PROGETTI, PARTNERSHIP, LEADS, SOCI, ...) sono managed=False:
`migrate` non crea le loro tabelle. Questo comando le crea in SQLite e, con
--demo, inserisce pochi record fittizi per navigare il gestionale.
Uso: python manage.py migrate && python manage.py setup_local_db --demo
"""
import datetime
from decimal import Decimal

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from dashboard.models import Lead, Partnership, Progetti, Soci


class Command(BaseCommand):
    help = "Crea in SQLite le tabelle dei modelli Supabase (managed=False) e opzionalmente dati demo."

    def add_arguments(self, parser):
        parser.add_argument('--demo', action='store_true', help='Inserisce dati demo se le tabelle sono vuote.')

    def handle(self, *args, demo=False, **options):
        if connection.vendor != 'sqlite':
            raise CommandError('setup_local_db gira solo su SQLite locale: mai contro Supabase.')

        existing = set(connection.introspection.table_names())
        missing = [
            m for m in apps.get_app_config('dashboard').get_models()
            if not m._meta.managed and not m._meta.proxy and m._meta.db_table not in existing
        ]
        if missing:
            with connection.schema_editor() as editor:
                for model in missing:
                    editor.create_model(model)
            self._fix_percent_columns(missing)
        self.stdout.write(
            f"Tabelle create: {', '.join(m._meta.db_table for m in missing) or 'nessuna (già presenti)'}"
        )

        if demo:
            self._seed_demo()

    def _fix_percent_columns(self, models):
        """db_column '... (in %%)' = '%' letterale (escape inspectdb). Il CREATE TABLE
        SQLite non interpola e crea '%%', le query cercano '%': rinomina."""
        qn = connection.ops.quote_name
        with connection.cursor() as cursor:
            for model in models:
                for field in model._meta.local_fields:
                    if '%%' in field.column:
                        cursor.execute(
                            f'ALTER TABLE {qn(model._meta.db_table)} RENAME COLUMN '
                            f'{qn(field.column)} TO {qn(field.column.replace("%%", "%"))}'
                        )

    @transaction.atomic
    def _seed_demo(self):
        seeded = []
        if not Progetti.objects.exists():
            for codice, nome, stato, fatturato, inizio in (
                ('DE0925', 'Demo Analisi di mercato', 'In corso', '€ 1200,00', '01/09/2025'),
                ('DE1024', 'Demo Business plan', 'Concluso', '€ 880,00', '15/10/2024'),
                ('DE0126', 'Demo Sito web', 'In avvio', '', '10/01/2026'),
            ):
                Progetti(
                    codice_progetto=codice, nome_progetto=nome, cliente='Cliente Demo',
                    stato=stato, pm='PM Demo', provenienza='Network',
                    fatturato_senza_iva_field=fatturato, data_inizio=inizio,
                ).save()
            seeded.append('progetti')

        if not Partnership.objects.exists():
            for nome, status in (
                ('Demo Partner Attiva', Partnership.STATUS_ATTIVA),
                ('Demo Partner Conclusa', Partnership.STATUS_CONCLUSA),
                ('Demo Lead Partnership', Partnership.STATUS_TRATTATIVA),
                ('Demo Non Finalizzata', Partnership.STATUS_NON_FINALIZZATA),
            ):
                Partnership.objects.create(
                    partnership=nome, status_partnership=status,
                    tipologia=Partnership.TIPOLOGIA_AZIENDA, anno=2025, data_firma='01/03/2025',
                )
            seeded.append('partnership')

        if not Lead.objects.exists():
            today = datetime.date.today()
            for n, (azienda, fase, stato, valore, prob) in enumerate((
                ('Demo Startup Srl', 'Qualificato', 'Attiva', '5000', 40),
                ('Demo PMI Spa', 'Proposta inviata', 'Attiva', '12000', 60),
                ('Demo Corp', 'Vinta', 'Vinta', '8000', 100),
            ), start=1):
                Lead.objects.create(
                    lead_id=f'LEAD-DEMO-{n}', azienda=azienda, fase_attuale=fase, stato_lead=stato,
                    valore_stimato=Decimal(valore), probabilita=prob, owner='Owner Demo',
                    data_creazione=today, data_prossima_azione=today + datetime.timedelta(days=7 * n),
                )
            seeded.append('leads')

        if not Soci.objects.exists():
            for nome, cognome, ruolo, area in (
                ('Anna', 'Demo', 'President', 'Board'),
                ('Luca', 'Demo', 'Head of', 'BD'),
                ('Sara', 'Demo', 'Consultant', 'D&A'),
                ('Marco', 'Demo', 'Junior Consultant', 'HR'),
                ('Giulia', 'Demo', 'Senior Consultant', 'M&C'),
            ):
                Soci(
                    nome_1=nome, cognome=cognome, ruolo=ruolo, area_di_appartenenza=area,
                    status='Associato', data_entrata='01/10/2024',
                ).save()
            seeded.append('soci')

        self.stdout.write(f"Dati demo inseriti: {', '.join(seeded) or 'nessuno (tabelle già popolate)'}")
