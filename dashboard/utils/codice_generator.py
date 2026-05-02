"""Generazione automatica del CODICE PROGETTO.

Replica la formula del Google Sheet:
    =SE(L="";"";MAIUSC(SINISTRA(B;2)) & TESTO(L;"MMYY") & contatore_se_duplicato)

Regole:
- Prefisso: 2 prime lettere alfabetiche di NOME PROGETTO, uppercase, senza accenti.
- Suffisso data: data_inizio formattata "MMYY" (es. 09/2023 -> "0923").
- Contatore: assente sul primo record con quel prefisso+data; "1", "2", ...
  sui successivi. Si calcola come MAX(suffisso_numerico_esistente)+1
  per evitare collisioni di PK dopo eventuali DELETE.
- Edge case: 1 sola lettera alfabetica nel nome -> padding con "X".
- Edge case: 0 lettere alfabetiche -> ValueError.
"""
import re
import unicodedata
from datetime import date, datetime


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _extract_prefix(nome_progetto: str) -> str:
    if not nome_progetto or not str(nome_progetto).strip():
        raise ValueError('Il NOME PROGETTO è obbligatorio per generare il CODICE.')
    cleaned = _strip_accents(str(nome_progetto))
    letters = [c for c in cleaned if c.isalpha()]
    if not letters:
        raise ValueError(
            'Il NOME PROGETTO deve contenere almeno una lettera per generare il CODICE.'
        )
    if len(letters) == 1:
        return (letters[0] + 'X').upper()
    return (letters[0] + letters[1]).upper()


def _extract_mmyy(data_inizio) -> str:
    if data_inizio in (None, ''):
        raise ValueError('La DATA INIZIO è obbligatoria per generare il CODICE.')
    if isinstance(data_inizio, datetime):
        return data_inizio.strftime('%m%y')
    if isinstance(data_inizio, date):
        return data_inizio.strftime('%m%y')
    s = str(data_inizio).strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(s, fmt).strftime('%m%y')
        except ValueError:
            continue
    raise ValueError('La DATA INIZIO non è in un formato riconosciuto.')


def _next_suffix(existing_codes, base: str) -> str:
    """Ritorna il codice da assegnare dato l'insieme dei codici esistenti
    che iniziano con `base` (prefisso+MMYY)."""
    suffixes = []
    base_present = False
    pattern = re.compile(r'^' + re.escape(base) + r'(\d*)$')
    for code in existing_codes:
        if not code:
            continue
        m = pattern.match(code)
        if not m:
            continue
        suf = m.group(1)
        if suf == '':
            base_present = True
            suffixes.append(0)
        else:
            try:
                suffixes.append(int(suf))
            except ValueError:
                continue
    if not suffixes:
        return base
    if not base_present and max(suffixes) == 0:
        # nessun record reale matcha; safety
        return base
    return base + str(max(suffixes) + 1)


def generate_codice_progetto(nome_progetto, data_inizio) -> str:
    """Genera CODICE PROGETTO: <PREFIX><MMYY>[<contatore>]."""
    prefix = _extract_prefix(nome_progetto)
    mmyy = _extract_mmyy(data_inizio)
    base = f'{prefix}{mmyy}'

    from dashboard.models import Progetti
    existing = Progetti.objects.filter(
        codice_progetto__startswith=base
    ).values_list('codice_progetto', flat=True)
    return _next_suffix(list(existing), base)
