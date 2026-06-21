"""Choices ufficiali per Progetti e Partnership.

Fonte di verità: planilha Google Sheets ufficiale JESAP.
Modificare solo se la planilha cambia. Stringhe (case + accenti) IDENTICHE
a quelle del foglio.
"""

EMPTY_CHOICE = ('', '---------')


def _build(values):
    return [EMPTY_CHOICE] + [(v, v) for v in values]


# ============================================================
# PROGETTI
# ============================================================

TIPOLOGIA_CLIENTE_VALUES = [
    'Startup',
    'Piccola impresa',
    'Media impresa',
    'Grande impresa',
    'Organizzazione no profit',
    'Pubblica amministrazione',
    'altro',
]
TIPOLOGIA_CLIENTE_CHOICES = _build(TIPOLOGIA_CLIENTE_VALUES)

TIPOLOGIA_PROGETTO_VALUES = [
    'Progetto Interno',
    'Progetto Esterno',
]
TIPOLOGIA_PROGETTO_CHOICES = _build(TIPOLOGIA_PROGETTO_VALUES)

STATO_PROGETTO_VALUES = [
    'In corso',
    'In avvio',
    'Concluso',
    'Annullato',
    'Stand-by',
]
STATO_PROGETTO_CHOICES = _build(STATO_PROGETTO_VALUES)

AREA_PERTINENZA_VALUES = [
    'M&C',
    'BD',
    'HR',
    'D&A',
    'Board',
    'Delega Advisory',
    'Delega Eventi',
    'Delega Accademy',
    'Delega Sito Web',
    'Delega PA',
    'D&A-HR',
]
AREA_PERTINENZA_CHOICES = _build(AREA_PERTINENZA_VALUES)

PROVENIENZA_VALUES = [
    'JESAPer',
    'Interno',
    'Alumnus',
    'Commerciale',
    'Network',
]
PROVENIENZA_CHOICES = _build(PROVENIENZA_VALUES)


# ============================================================
# PARTNERSHIP
# ============================================================

PARTNERSHIP_TIPOLOGIA_VALUES = [
    'JE italiana',
    'JE estera',
    'Ente pubblico',
    'Azienda',
]
PARTNERSHIP_TIPOLOGIA_CHOICES = _build(PARTNERSHIP_TIPOLOGIA_VALUES)

PARTNERSHIP_OGGETTO_VALUES = [
    'Progetto',
    'Visibilità',
    'Formazione',
    'Altro',
]
PARTNERSHIP_OGGETTO_CHOICES = _build(PARTNERSHIP_OGGETTO_VALUES)

# Valori ufficiali del foglio:
PARTNERSHIP_STATUS_OFFICIAL_VALUES = [
    'Attiva',
    'Conclusa',
    'In fase di rinnovo',
]
# 'In trattativa' NON è nel foglio ufficiale: è una categoria INTERNA usata
# da `views.py` per separare i record Lead dalla tab Partnership
# (vedi filtri `status_partnership__iexact='In trattativa'`).
# Va mantenuta come 4° valore finché esiste la logica Lead lato applicativo.
PARTNERSHIP_STATUS_INTERNAL_LEAD = 'In trattativa'
PARTNERSHIP_STATUS_VALUES = (
    PARTNERSHIP_STATUS_OFFICIAL_VALUES + [PARTNERSHIP_STATUS_INTERNAL_LEAD]
)
PARTNERSHIP_STATUS_CHOICES = [
    EMPTY_CHOICE,
    ('Attiva', 'Attiva'),
    ('Conclusa', 'Conclusa'),
    ('In fase di rinnovo', 'In fase di rinnovo'),
    ('In trattativa', 'In trattativa (Lead)'),
]
# Versione "solo dropdown filtro tab Partnership": esclude i Lead.
PARTNERSHIP_STATUS_FILTER_CHOICES = _build(PARTNERSHIP_STATUS_OFFICIAL_VALUES)

PARTNERSHIP_DURATA_VALUES = [
    '1 anno',
    '2 anni',
    'Indeterminata',
    '3 anni',
    "Circoscritta all'evento",
    '6 mesi',
]
PARTNERSHIP_DURATA_CHOICES = _build(PARTNERSHIP_DURATA_VALUES)

PARTNERSHIP_RINNOVO_VALUES = [
    'Rinnovo tacito',
    'Comunicare intenzione di rinnovo',
    'Indefinito',
]
PARTNERSHIP_RINNOVO_CHOICES = _build(PARTNERSHIP_RINNOVO_VALUES)


# ============================================================
# BOOLEAN
# ============================================================

BOOL_SI_NO_CHOICES = [
    ('', '---------'),
    ('True', 'Sì'),
    ('False', 'No'),
]


# ============================================================
# LEADS (BD Lead Control)
# ============================================================

LEAD_FASE_VALUES = [
    'Nuovo',
    'Qualificato',
    'Proposta inviata',
    'Negoziazione',
    'Vinta',
    'Persa',
]
LEAD_FASE_CHOICES = _build(LEAD_FASE_VALUES)

LEAD_STATO_VALUES = [
    'Attiva',
    'In pausa',
    'Vinta',
    'Persa',
    'Archiviata',
]
LEAD_STATO_CHOICES = _build(LEAD_STATO_VALUES)

LEAD_CONTRATTO_VALUES = [
    'Da preparare',
    'Bozza',
    'In revisione',
    'Firmato',
    'Rifiutato',
    'Annullato',
]
LEAD_CONTRATTO_CHOICES = _build(LEAD_CONTRATTO_VALUES)

LEAD_PRIORITA_VALUES = [
    'Alta',
    'Media',
    'Bassa',
]
LEAD_PRIORITA_CHOICES = _build(LEAD_PRIORITA_VALUES)


# ============================================================
# UTIL
# ============================================================

def normalize_to_choice(raw, valid_values):
    """Mappa un valore legacy al valore canonico (case esatto del foglio).

    Match case-insensitive su lowercase+strip. Se non trova match,
    ritorna il raw originale (sarà rifiutato dal ChoiceField → l'utente
    deve scegliere un valore valido prima del salvataggio).
    """
    if raw in (None, ''):
        return raw
    needle = str(raw).strip().lower()
    if not needle:
        return raw
    for v in valid_values:
        if v.lower() == needle:
            return v
    return raw
