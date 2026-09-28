"""Da una risposta al form (dict {intestazione colonna: valore}) a un Candidato.

Usato dal webhook (Apps Script sul foglio risposte) e dal comando di import.
Le intestazioni sono riconosciute ignorando maiuscole, accenti e punteggiatura;
le colonne sconosciute finiscono in `altre_risposte` (nessun dato perso).
"""
import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from dashboard.models import Candidato

TZ = ZoneInfo('Europe/Rome')


def normalizza(testo):
    testo = unicodedata.normalize('NFKD', str(testo or ''))
    testo = ''.join(c for c in testo if not unicodedata.combining(c))
    testo = re.sub(r'[^a-z0-9]+', ' ', testo.casefold())
    return ' '.join(testo.split())


# campo Candidato → intestazioni possibili nel foglio (già normalizzate)
_ALIAS = {
    'data_candidatura': ['informazioni cronologiche', 'timestamp', 'marca temporale', 'data ora', 'data candidatura',
                         'data invio'],
    'email': ['indirizzo di mail', 'indirizzo email', 'indirizzo e mail', 'email', 'e mail', 'mail'],
    'nome': ['nome'],
    'cognome': ['cognome'],
    'data_nascita': ['data di nascita'],
    'telefono': ['n telefono', 'telefono', 'numero di telefono', 'cellulare', 'numero di cellulare'],
    'ateneo': ['ateneo', 'universita'],
    'facolta': ['facolta', 'dipartimento'],
    'corso_laurea': ['corso di laurea', 'corso di studi', 'corso di studio'],
    'cv_url': ['curriculum', 'cv', 'curriculum vitae', 'link cv'],
    'anno_frequenza': ['anno frequenza', 'anno di frequenza', 'anno di corso'],
    'residenza': ['residenza', 'citta di residenza'],
    'area_1': ['area 1', 'prima area', 'area preferita', 'prima area di preferenza'],
    'area_2': ['area 2', 'seconda area', 'seconda area di preferenza'],
    'fonte': ['fonte conoscenza jesap', 'come hai conosciuto jesap'],
    'motivazione': ['motivazione jesap', 'motivazione', 'perche vuoi entrare in jesap'],
    'conosce_jesap': ['conosci associati jesap'],
    'conosce_je_italy': ['conosci associati je italy', 'conosci network je italy'],
}
# Form del sito: canale ("Come hai conosciuto JESAP") + dettaglio ("Fonte") → un solo campo `fonte`.
_FONTE_DETTAGLIO = {'fonte', 'specifica la fonte'}
_URL_PREFIX = ('http://', 'https://')
_ALIAS_INDEX = {alias: campo for campo, aliases in _ALIAS.items() for alias in aliases}

_AREE = {
    'bd': 'BD', 'business development': 'BD',
    'm c': 'M&C', 'marketing communication': 'M&C', 'marketing and communication': 'M&C', 'marketing e comunicazione': 'M&C',
    'd a': 'D&A', 'data automation': 'D&A', 'data and automation': 'D&A', 'data analytics': 'D&A',
    'hr': 'HR', 'human resources': 'HR', 'risorse umane': 'HR',
    'legal': 'Legal', 'it': 'IT', 'information technology': 'IT',
}

_MAX_LEN = {f.name: f.max_length for f in Candidato._meta.concrete_fields if getattr(f, 'max_length', None)}


def area_da_testo(valore):
    return _AREE.get(normalizza(valore), '')


def parse_data_ora(valore):
    if not valore:
        return None
    if isinstance(valore, datetime):
        dt = valore
    else:
        s = str(valore).strip()
        dt = None
        try:
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H.%M.%S', '%d/%m/%Y %H:%M', '%d/%m/%Y'):
                try:
                    dt = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
        if dt is None:
            return None
    if timezone.is_naive(dt):
        dt = dt.replace(tzinfo=TZ)
    return dt


def mappa_risposta(risposta):
    """{intestazione: valore} → (campi Candidato, altre_risposte)."""
    campi, altre = {}, {}
    fonte_dettaglio = ''
    for intestazione, valore in (risposta or {}).items():
        if valore is None:
            continue
        valore_txt = valore if isinstance(valore, datetime) else str(valore).strip()
        chiave = normalizza(intestazione)
        if chiave in _FONTE_DETTAGLIO:
            fonte_dettaglio = valore_txt
            continue
        campo = _ALIAS_INDEX.get(chiave)
        # "Curriculum" nel form del sito è testo libero: il link al CV sta nella colonna "CV".
        if campo == 'cv_url' and not str(valore_txt).lower().startswith(_URL_PREFIX):
            campo = None
        if campo is None or campo in campi:
            if valore_txt not in ('', None):
                altre[str(intestazione)] = str(valore_txt)
            continue
        campi[campo] = valore_txt

    if fonte_dettaglio:
        campi['fonte'] = ' – '.join(v for v in (campi.get('fonte'), fonte_dettaglio) if v)
    if 'data_candidatura' in campi:
        raw = campi['data_candidatura']
        campi['data_candidatura'] = parse_data_ora(raw)
        if campi['data_candidatura'] is None and raw:
            altre['Data candidatura (originale)'] = str(raw)
    for campo in ('area_1', 'area_2'):
        if campo in campi:
            raw = campi[campo]
            campi[campo] = area_da_testo(raw)
            if raw and not campi[campo]:
                altre[f'{campo.replace("_", " ").title()} (originale)'] = raw
    if 'email' in campi:
        campi['email'] = campi['email'].lower()
    for campo, valore in list(campi.items()):
        if isinstance(valore, str) and campo in _MAX_LEN:
            campi[campo] = valore[:_MAX_LEN[campo]]
    return campi, altre


class RispostaNonValida(ValueError):
    pass


@transaction.atomic
def registra_candidatura(sessione, risposta):
    """
    Crea il Candidato. Ritorna (candidato, stato) con stato in:
      'creato'      nuova candidatura
      'doppione'    stessa email già candidata in sessione → esito screening 'Doppione'
      'duplicato'   stessa risposta già ricevuta (retry del sync) → nessuna creazione
    """
    campi, altre = mappa_risposta(risposta)
    email = campi.get('email', '')
    if not email or '@' not in email:
        raise RispostaNonValida('email mancante o non valida')
    if not campi.get('nome') and not campi.get('cognome'):
        raise RispostaNonValida('nome e cognome mancanti')

    esistenti = Candidato.objects.select_for_update().filter(sessione=sessione, email__iexact=email)
    data = campi.get('data_candidatura')
    for c in esistenti:
        stessa_data = (c.data_candidatura == data) if data else True
        if stessa_data and c.nome == campi.get('nome', '') and c.cognome == campi.get('cognome', ''):
            return c, 'duplicato'

    candidato = Candidato(sessione=sessione, altre_risposte=altre, **campi)
    stato = 'creato'
    if esistenti.exists():
        candidato.esito_screening = 'Doppione'
        stato = 'doppione'
    candidato.save()
    return candidato, stato
