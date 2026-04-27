"""Test della fonte unica di verità: dashboard/choices.py."""
import pytest

from dashboard import choices as ch


# Mappatura nome → (lista valori attesi, lista choices esposta dal modulo).
# I valori sono COPIA LETTERALE dalla planilha ufficiale (case + accenti).
EXPECTED = {
    'tipologia_cliente': (
        ['Startup', 'Piccola impresa', 'Media impresa', 'Grande impresa',
         'Organizzazione no profit', 'Pubblica amministrazione', 'altro'],
        ch.TIPOLOGIA_CLIENTE_CHOICES,
        ch.TIPOLOGIA_CLIENTE_VALUES,
    ),
    'tipologia_progetto': (
        ['Progetto Interno', 'Progetto Esterno'],
        ch.TIPOLOGIA_PROGETTO_CHOICES,
        ch.TIPOLOGIA_PROGETTO_VALUES,
    ),
    'stato_progetto': (
        ['In corso', 'In avvio', 'Concluso', 'Annullato', 'Stand-by'],
        ch.STATO_PROGETTO_CHOICES,
        ch.STATO_PROGETTO_VALUES,
    ),
    'area_pertinenza': (
        ['M&C', 'BD', 'HR', 'D&A', 'Board', 'Delega Advisory', 'Delega Eventi',
         'Delega Accademy', 'Delega Sito Web', 'Delega PA', 'D&A-HR'],
        ch.AREA_PERTINENZA_CHOICES,
        ch.AREA_PERTINENZA_VALUES,
    ),
    'provenienza': (
        ['JESAPer', 'Interno', 'Alumnus', 'Commerciale', 'Network'],
        ch.PROVENIENZA_CHOICES,
        ch.PROVENIENZA_VALUES,
    ),
    'partnership_tipologia': (
        ['JE italiana', 'JE estera', 'Ente pubblico', 'Azienda'],
        ch.PARTNERSHIP_TIPOLOGIA_CHOICES,
        ch.PARTNERSHIP_TIPOLOGIA_VALUES,
    ),
    'partnership_oggetto': (
        ['Progetto', 'Visibilità', 'Formazione', 'Altro'],
        ch.PARTNERSHIP_OGGETTO_CHOICES,
        ch.PARTNERSHIP_OGGETTO_VALUES,
    ),
    'partnership_durata': (
        ['1 anno', '2 anni', 'Indeterminata', '3 anni',
         "Circoscritta all'evento", '6 mesi'],
        ch.PARTNERSHIP_DURATA_CHOICES,
        ch.PARTNERSHIP_DURATA_VALUES,
    ),
    'partnership_rinnovo': (
        ['Rinnovo tacito', 'Comunicare intenzione di rinnovo', 'Indefinito'],
        ch.PARTNERSHIP_RINNOVO_CHOICES,
        ch.PARTNERSHIP_RINNOVO_VALUES,
    ),
}


@pytest.mark.parametrize('name', list(EXPECTED.keys()))
def test_choices_contains_empty_first(name):
    """Ogni lista CHOICES inizia con la riga vuota '---------'."""
    _, choices, _ = EXPECTED[name]
    assert choices[0] == ('', '---------')


@pytest.mark.parametrize('name', list(EXPECTED.keys()))
def test_choices_count_matches_expected(name):
    """Il numero di opzioni reali (escluso vuoto) corrisponde alla planilha."""
    expected_values, choices, values_const = EXPECTED[name]
    assert len(values_const) == len(expected_values)
    # +1 per l'EMPTY_CHOICE iniziale
    assert len(choices) == len(expected_values) + 1


@pytest.mark.parametrize('name', list(EXPECTED.keys()))
def test_choices_values_are_exact_strings(name):
    """Match letterale (case + accenti) coi valori della planilha."""
    expected_values, _, values_const = EXPECTED[name]
    assert values_const == expected_values


@pytest.mark.parametrize('name', list(EXPECTED.keys()))
def test_choices_tuple_structure(name):
    """Ogni choice è (value, label) con value == label per i non-vuoti."""
    expected_values, choices, _ = EXPECTED[name]
    for v, l in choices[1:]:
        assert v == l
        assert v in expected_values


def test_partnership_status_includes_lead():
    """'In trattativa' è la 4ª opzione tecnica per la tab Lead."""
    values_in_choices = [v for v, _ in ch.PARTNERSHIP_STATUS_CHOICES if v]
    assert 'Attiva' in values_in_choices
    assert 'Conclusa' in values_in_choices
    assert 'In fase di rinnovo' in values_in_choices
    assert 'In trattativa' in values_in_choices
    assert ch.PARTNERSHIP_STATUS_INTERNAL_LEAD == 'In trattativa'


def test_partnership_status_official_excludes_lead():
    """Il subset 'official' esclude 'In trattativa' (per il dropdown filtro)."""
    assert 'In trattativa' not in ch.PARTNERSHIP_STATUS_OFFICIAL_VALUES
    assert ch.PARTNERSHIP_STATUS_OFFICIAL_VALUES == [
        'Attiva', 'Conclusa', 'In fase di rinnovo',
    ]


def test_partnership_status_lead_label_is_informative():
    """La label di 'In trattativa' indica esplicitamente che è un Lead."""
    label = dict(ch.PARTNERSHIP_STATUS_CHOICES)['In trattativa']
    assert 'Lead' in label


def test_bool_choices_shape():
    assert ch.BOOL_SI_NO_CHOICES == [
        ('', '---------'), ('True', 'Sì'), ('False', 'No'),
    ]


# ---- normalize_to_choice ----

@pytest.mark.parametrize('raw,expected', [
    ('in corso', 'In corso'),
    ('IN CORSO', 'In corso'),
    ('In Corso', 'In corso'),
    ('  in corso  ', 'In corso'),
    ('CONCLUSO', 'Concluso'),
    ('stand-by', 'Stand-by'),
])
def test_normalize_to_choice_case_insensitive(raw, expected):
    assert ch.normalize_to_choice(raw, ch.STATO_PROGETTO_VALUES) == expected


@pytest.mark.parametrize('raw', ['', None])
def test_normalize_to_choice_returns_empty_for_blank(raw):
    assert ch.normalize_to_choice(raw, ch.STATO_PROGETTO_VALUES) == raw


def test_normalize_to_choice_returns_raw_when_no_match():
    """Se il valore non matcha alcun choice, ritorna il raw (sarà rifiutato dal form)."""
    out = ch.normalize_to_choice('Aspettando', ch.STATO_PROGETTO_VALUES)
    assert out == 'Aspettando'


def test_normalize_to_choice_only_whitespace():
    """Stringa di soli spazi → ritorna raw invariato."""
    assert ch.normalize_to_choice('   ', ch.STATO_PROGETTO_VALUES) == '   '


def test_normalize_to_choice_partnership_status_with_internal_lead():
    """'in trattativa' (lead interno) viene normalizzato come 'In trattativa'."""
    out = ch.normalize_to_choice('IN TRATTATIVA', ch.PARTNERSHIP_STATUS_VALUES)
    assert out == 'In trattativa'


def test_normalize_to_choice_partnership_durata_with_apostrophe():
    """Match anche su valori con apostrofo."""
    out = ch.normalize_to_choice(
        "circoscritta all'evento", ch.PARTNERSHIP_DURATA_VALUES
    )
    assert out == "Circoscritta all'evento"
