"""Importa un export CSV del "Tasks Tracker" Notion nella tabella TASKS.

Uso (una volta per area):
    python manage.py import_notion_tasks "Tasks Tracker ..._all.csv" --area "D&A" --dry-run
    python manage.py import_notion_tasks "Tasks Tracker ..._all.csv" --area "D&A"

- Assegnatari: match per nome su SOCI (case/spazi/accenti ignorati); chi non è
  in SOCI finisce in `altri_assegnatari` (nessun nome perso).
- Idempotente: salta le task già presenti (stessa area + titolo + data creazione
  + assegnatari: Notion ha task omonime create nello stesso minuto).
- Colonne Notion ignorate: Past due (ricalcolata), Blocked by, Is blocking,
  Parent-task, Sub-tasks, Task type.
"""
import csv
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from dashboard import choices as ch
from dashboard.models import Soci, Task

NOTION_TZ = ZoneInfo('Europe/Rome')

STATO_MAP = {
    'not started': ch.TASK_STATO_DA_INIZIARE,
    'in progress': ch.TASK_STATO_IN_CORSO,
    'done': ch.TASK_STATO_COMPLETATA,
}
PRIORITA_MAP = {'high': 'Alta', 'medium': 'Media', 'low': 'Bassa'}

_DUE_RE = re.compile(r'^(\d{1,2})/(\d{1,2})/(\d{4})')
_LINK_SPLIT_RE = re.compile(r',\s*(?=https?://)')


def _norm_name(value):
    value = unicodedata.normalize('NFKD', value or '')
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(value.casefold().split())


def _split_names(raw):
    return [n.strip() for n in (raw or '').split(',') if n.strip()]


def _assignee_key(socio_pks, altri):
    return frozenset(socio_pks), frozenset(_norm_name(n) for n in altri)


def parse_due_date(raw):
    """'30/01/2025' o '02/05/2025 12:00 AM (GMT+2)' → date."""
    m = _DUE_RE.match((raw or '').strip())
    if not m:
        return None
    day, month, year = (int(g) for g in m.groups())
    try:
        return datetime(year, month, day).date()
    except ValueError:
        return None


def parse_notion_datetime(raw):
    """'January 15, 2025 4:54 PM' → datetime aware (Europe/Rome)."""
    raw = (raw or '').strip()
    if not raw:
        return None
    for fmt in ('%B %d, %Y %I:%M %p', '%B %d, %Y'):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=NOTION_TZ)
        except ValueError:
            continue
    return None


class Command(BaseCommand):
    help = 'Importa le task da un export CSV Notion (Tasks Tracker) per una area.'

    def add_arguments(self, parser):
        parser.add_argument('csv_path')
        parser.add_argument('--area', required=True, choices=ch.TASK_AREA_VALUES)
        parser.add_argument('--dry-run', action='store_true', help='Mostra cosa farebbe senza scrivere nel DB.')

    def handle(self, csv_path, area, dry_run, **options):
        try:
            with open(csv_path, newline='', encoding='utf-8-sig') as fh:
                rows = list(csv.DictReader(fh))
        except OSError as exc:
            raise CommandError(f'Impossibile leggere {csv_path}: {exc}')
        if rows and 'Task name' not in rows[0]:
            raise CommandError('Colonna "Task name" assente: non sembra un export del Tasks Tracker Notion.')

        soci_by_name = {}
        for socio in Soci.objects.all():
            full = socio.nome_e_cognome or ' '.join(p for p in (socio.nome_1, socio.nome_2, socio.cognome) if p)
            short = ' '.join(p for p in (socio.nome_1, socio.cognome) if p)
            for key in (full, short):
                if key:
                    soci_by_name.setdefault(_norm_name(key), socio)

        created = skipped = 0
        unmatched = set()
        warnings = []

        with transaction.atomic():
            for n, row in enumerate(rows, start=2):
                titolo = (row.get('Task name') or '').strip()
                if not titolo:
                    continue
                creato_il = parse_notion_datetime(row.get('Created time'))

                assegnatari, altri = [], []
                for name in _split_names(row.get('Assignee')):
                    socio = soci_by_name.get(_norm_name(name))
                    if socio:
                        assegnatari.append(socio)
                    else:
                        altri.append(name)
                        unmatched.add(name)

                if creato_il:
                    key = _assignee_key((s.pk for s in assegnatari), altri)
                    esistenti = Task.objects.filter(area=area, titolo=titolo, creato_il=creato_il).prefetch_related('assegnatari')
                    if any(_assignee_key((s.pk for s in t.assegnatari.all()), _split_names(t.altri_assegnatari)) == key
                           for t in esistenti):
                        skipped += 1
                        continue

                stato_raw = (row.get('Status') or '').strip().lower()
                stato = STATO_MAP.get(stato_raw, ch.TASK_STATO_DA_INIZIARE)
                if stato_raw and stato_raw not in STATO_MAP:
                    warnings.append(f'riga {n}: stato "{row.get("Status")}" sconosciuto → {stato}')

                effort = (row.get('Effort level') or '').strip()
                if effort and effort not in ch.TASK_EFFORT_VALUES:
                    warnings.append(f'riga {n}: effort "{effort}" ignorato')
                    effort = ''

                links = _LINK_SPLIT_RE.split((row.get('Link del file') or '').strip())

                task = Task(
                    titolo=titolo[:255],
                    area=area,
                    competenza=', '.join(_split_names(row.get('Competenza'))),
                    stato=stato,
                    priorita=PRIORITA_MAP.get((row.get('Priorità') or '').strip().lower(), ''),
                    effort=effort,
                    scadenza=parse_due_date(row.get('Due date')),
                    descrizione=(row.get('Description') or '').strip(),
                    link='\n'.join(l.strip() for l in links if l.strip()),
                    altri_assegnatari=', '.join(altri),
                    creato_da=(row.get('Created by') or '').strip(),
                    modificato_da=(row.get('Last edited by') or '').strip(),
                )
                task.save()
                task.assegnatari.set(assegnatari)

                # auto_now/auto_now_add ignorano i valori passati: date originali Notion via update()
                storico = {}
                if creato_il:
                    storico['creato_il'] = creato_il
                modificato_il = parse_notion_datetime(row.get('Last edited time'))
                if modificato_il:
                    storico['modificato_il'] = modificato_il
                if storico:
                    Task.objects.filter(pk=task.pk).update(**storico)
                created += 1

            if dry_run:
                transaction.set_rollback(True)

        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}{area}: {created} task importate, {skipped} già presenti (saltate).'
        ))
        if unmatched:
            self.stdout.write(self.style.WARNING(
                f'{len(unmatched)} assegnatari non trovati in SOCI (salvati in "Altri assegnatari"): '
                + ', '.join(sorted(unmatched, key=str.lower))
            ))
        for w in warnings:
            self.stdout.write(self.style.WARNING(w))
