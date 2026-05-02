"""Form-level tests: Choice/Select widgets, validation, legacy normalization."""
import pytest
from django import forms

from dashboard import choices as ch
from dashboard.forms import PartnershipForm, ProgettoForm
from dashboard.models import Partnership, Progetti

# ModelForm.is_valid() chiama validate_unique() che fa una SELECT.
# Tutti i test in questo modulo che istanziano un form e ne chiamano
# is_valid()/validate hanno bisogno della test DB.
pytestmark = pytest.mark.django_db


# ============================================================
# Helpers
# ============================================================

PROGETTO_REQUIRED_BASE = {
    'codice_progetto': 'PROG-TEST-001',
    'nome_progetto': 'Test',
    'cliente': 'ACME',
    'pm': 'Mario',
    'mese_inizio': '',
    'anno': '',
    'n_risorse_coinvolte': '',
    'fatturato_senza_iva_field': '',
    'iva': '',
    'costi': '',
    'profitti': '',
    'descrizione_servizio_offerto': '',
    'soddisfazione_team_in_field': '',
    'soddisfazione_cliente_in_field': '',
    'data_primo_contatto': '',
    'data_firma_contratto': '',
    'data_inizio': '2023-09-27',
    'data_fine_contratto': '',
}

PARTNERSHIP_REQUIRED_BASE = {
    'partnership': 'TestPartner',
    'id_codice': 'P001',
    'data_firma': '',
    'anno': '',
    'data_ultimo_rinnovo': '',
    'data_fine_prevista': '',
    'numero_progetti': '',
    'numero_partecipanti': '',
    'contatti': '',
    'cartella_sul_drive': '',
    'url_cartella': '',
    'vantaggi_partner': '',
    'compenso_economico': '',
}


def _progetto_data(**overrides):
    data = dict(PROGETTO_REQUIRED_BASE)
    # Default valid choice values:
    data.setdefault('tipologia_cliente', 'Startup')
    data.setdefault('tipologia_di_progetto', 'Progetto Interno')
    data.setdefault('stato', 'In corso')
    data.setdefault('area_di_pertinenza', 'BD')
    data.setdefault('provenienza', 'Interno')
    data.setdefault('coinvolgimento_della_pubblica_amministrazione', '')
    for i in range(1, 21):
        data.setdefault(f'risorsa_{i}', '')
    data.update(overrides)
    return data


def _partnership_data(**overrides):
    data = dict(PARTNERSHIP_REQUIRED_BASE)
    data.setdefault('tipologia', 'Azienda')
    data.setdefault('oggetto_primario', 'Progetto')
    data.setdefault('status_partnership', 'Attiva')
    data.setdefault('durata', '1 anno')
    data.setdefault('rinnovo', 'Rinnovo tacito')
    data.update(overrides)
    return data


# ============================================================
# Field type & widget
# ============================================================

PROGETTO_CHOICE_FIELDS = [
    ('tipologia_cliente', ch.TIPOLOGIA_CLIENTE_CHOICES),
    ('tipologia_di_progetto', ch.TIPOLOGIA_PROGETTO_CHOICES),
    ('stato', ch.STATO_PROGETTO_CHOICES),
    ('area_di_pertinenza', ch.AREA_PERTINENZA_CHOICES),
    ('provenienza', ch.PROVENIENZA_CHOICES),
]

PARTNERSHIP_CHOICE_FIELDS = [
    ('tipologia', ch.PARTNERSHIP_TIPOLOGIA_CHOICES),
    ('oggetto_primario', ch.PARTNERSHIP_OGGETTO_CHOICES),
    ('status_partnership', ch.PARTNERSHIP_STATUS_CHOICES),
    ('durata', ch.PARTNERSHIP_DURATA_CHOICES),
    ('rinnovo', ch.PARTNERSHIP_RINNOVO_CHOICES),
]


@pytest.mark.parametrize('field_name,expected_choices', PROGETTO_CHOICE_FIELDS)
def test_progetto_field_is_choicefield_with_select(field_name, expected_choices):
    form = ProgettoForm()
    field = form.fields[field_name]
    assert isinstance(field, forms.ChoiceField)
    assert isinstance(field.widget, forms.Select)
    assert list(field.choices) == list(expected_choices)


@pytest.mark.parametrize('field_name,expected_choices', PARTNERSHIP_CHOICE_FIELDS)
def test_partnership_field_is_choicefield_with_select(field_name, expected_choices):
    form = PartnershipForm()
    field = form.fields[field_name]
    assert isinstance(field, forms.ChoiceField)
    assert isinstance(field.widget, forms.Select)
    assert list(field.choices) == list(expected_choices)


# ============================================================
# Validation: rejects out-of-set values
# ============================================================

@pytest.mark.parametrize('field_name,_', PROGETTO_CHOICE_FIELDS)
def test_progetto_rejects_unknown_value(field_name, _):
    form = ProgettoForm(_progetto_data(**{field_name: 'XXX_NOT_VALID_XXX'}))
    assert not form.is_valid()
    assert field_name in form.errors


@pytest.mark.parametrize('field_name,_', PARTNERSHIP_CHOICE_FIELDS)
def test_partnership_rejects_unknown_value(field_name, _):
    form = PartnershipForm(_partnership_data(**{field_name: 'XXX_NOT_VALID_XXX'}))
    assert not form.is_valid()
    assert field_name in form.errors


# ============================================================
# Validation: accepts every official value
# ============================================================

@pytest.mark.parametrize('field_name,value', [
    (fname, v)
    for fname, choices_list in PROGETTO_CHOICE_FIELDS
    for v in [c[0] for c in choices_list if c[0]]
])
def test_progetto_accepts_official_value(field_name, value):
    form = ProgettoForm(_progetto_data(**{field_name: value}))
    assert form.is_valid(), f'{field_name}={value!r} → {form.errors.as_json()}'


@pytest.mark.parametrize('field_name,value', [
    (fname, v)
    for fname, choices_list in PARTNERSHIP_CHOICE_FIELDS
    for v in [c[0] for c in choices_list if c[0]]
])
def test_partnership_accepts_official_value(field_name, value):
    form = PartnershipForm(_partnership_data(**{field_name: value}))
    assert form.is_valid(), f'{field_name}={value!r} → {form.errors.as_json()}'


def test_partnership_accepts_in_trattativa_for_lead_backcompat():
    """'In trattativa' continua valido (lead tab)."""
    form = PartnershipForm(_partnership_data(status_partnership='In trattativa'))
    assert form.is_valid(), form.errors.as_json()


# ============================================================
# Legacy normalization in __init__
# ============================================================

@pytest.mark.parametrize('legacy,canonical', [
    ('In Corso', 'In corso'),
    ('IN CORSO', 'In corso'),
    ('  concluso  ', 'Concluso'),
    ('stand-by', 'Stand-by'),
])
def test_progetto_init_normalizes_legacy_stato(legacy, canonical):
    instance = Progetti(codice_progetto='X', stato=legacy)
    form = ProgettoForm(instance=instance)
    assert form.initial['stato'] == canonical


def test_progetto_init_normalizes_all_choice_fields():
    instance = Progetti(
        codice_progetto='X',
        tipologia_cliente='STARTUP',
        tipologia_di_progetto='progetto interno',
        stato='in corso',
        area_di_pertinenza='m&c',
        provenienza='jesaper',
    )
    form = ProgettoForm(instance=instance)
    assert form.initial['tipologia_cliente'] == 'Startup'
    assert form.initial['tipologia_di_progetto'] == 'Progetto Interno'
    assert form.initial['stato'] == 'In corso'
    assert form.initial['area_di_pertinenza'] == 'M&C'
    assert form.initial['provenienza'] == 'JESAPer'


def test_progetto_init_keeps_unknown_value_raw():
    """Valore totalmente fuori set: lasciato raw (form mostrerà vuoto + forza scelta)."""
    instance = Progetti(codice_progetto='X', stato='Aspettando')
    form = ProgettoForm(instance=instance)
    assert form.initial['stato'] == 'Aspettando'
    # E il form rifiuta su submit con quel valore:
    submitted = ProgettoForm(_progetto_data(stato='Aspettando'), instance=instance)
    assert not submitted.is_valid()


@pytest.mark.parametrize('legacy,canonical', [
    ('je italiana', 'JE italiana'),
    ('JE ITALIANA', 'JE italiana'),
    ('AZIENDA', 'Azienda'),
])
def test_partnership_init_normalizes_tipologia(legacy, canonical):
    instance = Partnership(partnership='X', tipologia=legacy)
    form = PartnershipForm(instance=instance)
    assert form.initial['tipologia'] == canonical


def test_partnership_init_normalizes_all_choice_fields():
    instance = Partnership(
        partnership='X',
        tipologia='AZIENDA',
        oggetto_primario='visibilità',
        status_partnership='in fase di rinnovo',
        durata='1 ANNO',
        rinnovo='RINNOVO TACITO',
    )
    form = PartnershipForm(instance=instance)
    assert form.initial['tipologia'] == 'Azienda'
    assert form.initial['oggetto_primario'] == 'Visibilità'
    assert form.initial['status_partnership'] == 'In fase di rinnovo'
    assert form.initial['durata'] == '1 anno'
    assert form.initial['rinnovo'] == 'Rinnovo tacito'


def test_partnership_init_normalizes_in_trattativa_lead():
    instance = Partnership(partnership='X', status_partnership='in trattativa')
    form = PartnershipForm(instance=instance)
    assert form.initial['status_partnership'] == 'In trattativa'


def test_progetto_accepts_valid_url_drive():
    form = ProgettoForm(_progetto_data(url_drive='https://drive.google.com/drive/folders/abc123'))
    assert 'url_drive' not in form.errors
    assert form.is_valid(), form.errors


def test_progetto_rejects_invalid_url_drive():
    form = ProgettoForm(_progetto_data(url_drive='not-a-url'))
    assert 'url_drive' in form.errors


def test_progetto_url_drive_optional():
    form = ProgettoForm(_progetto_data(url_drive=''))
    assert 'url_drive' not in form.errors


# ============================================================
# CODICE PROGETTO: hidden in creation, readonly in edit
# ============================================================

def test_form_creation_hides_codice_field():
    form = ProgettoForm()
    assert 'codice_progetto' not in form.fields


def test_form_edit_shows_codice_readonly():
    instance = Progetti.objects.create(
        codice_progetto='CE0923', nome_progetto='Cesop', data_inizio='27/09/2023',
    )
    form = ProgettoForm(instance=instance)
    assert 'codice_progetto' in form.fields
    attrs = form.fields['codice_progetto'].widget.attrs
    assert attrs.get('readonly') == 'readonly'


def test_form_creation_requires_nome_and_data_inizio():
    form = ProgettoForm()
    assert form.fields['nome_progetto'].required is True
    assert form.fields['data_inizio'].required is True


def test_form_creation_fails_without_nome():
    form = ProgettoForm(_progetto_data(nome_progetto=''))
    assert not form.is_valid()
    assert 'nome_progetto' in form.errors


def test_form_creation_fails_without_data_inizio():
    form = ProgettoForm(_progetto_data(data_inizio=''))
    assert not form.is_valid()
    assert 'data_inizio' in form.errors


def test_form_creation_succeeds_and_generates_codice():
    form = ProgettoForm(_progetto_data(nome_progetto='Cesop 2', data_inizio='2023-09-27'))
    assert form.is_valid(), form.errors.as_json()
    inst = form.save()
    assert inst.codice_progetto == 'CE0923'


def test_form_edit_ignores_client_side_codice_change():
    instance = Progetti.objects.create(
        codice_progetto='CE0923', nome_progetto='Cesop', data_inizio='27/09/2023',
    )
    form = ProgettoForm(
        _progetto_data(codice_progetto='HACKED', nome_progetto='Cesop', data_inizio='2023-09-27'),
        instance=instance,
    )
    assert form.is_valid(), form.errors.as_json()
    assert form.cleaned_data['codice_progetto'] == 'CE0923'
