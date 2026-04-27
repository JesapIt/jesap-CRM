"""Integration tests via Django test client.

I model unmanaged Progetti/Partnership vengono resi managed=True dal
conftest globale, così la test DB sqlite ha realmente le tabelle.
"""
import html
import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from dashboard import choices as ch

User = get_user_model()


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def editor_user(db):
    return User.objects.create_user(
        username='editor', email='editor@jesap.it',
        password='Pwd!1234', is_staff=True,
    )


@pytest.fixture
def auth_client(client, editor_user):
    client.force_login(editor_user)
    return client


# ============================================================
# Helpers
# ============================================================

def _select_options(markup, name):
    """Estrae le option di un <select name="..."> dall'HTML."""
    pattern = re.compile(
        rf'<select[^>]*name="{re.escape(name)}"[^>]*>(.*?)</select>',
        re.DOTALL,
    )
    m = pattern.search(markup)
    assert m, f'<select name="{name}"> non trovato nell\'HTML'
    raw = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>', m.group(1))
    # Django escape '&' → '&amp;', '\'' → '&#x27;', etc. nei value.
    return [html.unescape(v) for v in raw]


def _progetto_post_data(**overrides):
    data = {
        'codice_progetto': 'PROG-INT-001',
        'nome_progetto': 'Test Project',
        'cliente': 'ACME',
        'tipologia_cliente': 'Startup',
        'tipologia_di_progetto': 'Progetto Interno',
        'stato': 'In corso',
        'area_di_pertinenza': 'BD',
        'pm': 'Mario',
        'provenienza': 'Interno',
        'data_primo_contatto': '',
        'data_firma_contratto': '',
        'data_inizio': '',
        'mese_inizio': '',
        'data_fine_contratto': '',
        'anno': '',
        'n_risorse_coinvolte': '',
        'fatturato_senza_iva_field': '',
        'iva': '',
        'costi': '',
        'profitti': '',
        'descrizione_servizio_offerto': '',
        'coinvolgimento_della_pubblica_amministrazione': '',
        'soddisfazione_team_in_field': '',
        'soddisfazione_cliente_in_field': '',
    }
    for i in range(1, 21):
        data[f'risorsa_{i}'] = ''
    data.update(overrides)
    return data


def _partnership_post_data(**overrides):
    data = {
        'partnership': 'TestPartner',
        'id_codice': 'P001',
        'tipologia': 'Azienda',
        'oggetto_primario': 'Progetto',
        'status_partnership': 'Attiva',
        'data_firma': '',
        'anno': '',
        'durata': '1 anno',
        'rinnovo': 'Rinnovo tacito',
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
    data.update(overrides)
    return data


# ============================================================
# GET form pages render with proper <select>
# ============================================================

PROGETTO_SELECT_FIELDS = [
    ('tipologia_cliente', ch.TIPOLOGIA_CLIENTE_VALUES),
    ('tipologia_di_progetto', ch.TIPOLOGIA_PROGETTO_VALUES),
    ('stato', ch.STATO_PROGETTO_VALUES),
    ('area_di_pertinenza', ch.AREA_PERTINENZA_VALUES),
    ('provenienza', ch.PROVENIENZA_VALUES),
]

PARTNERSHIP_SELECT_FIELDS = [
    ('tipologia', ch.PARTNERSHIP_TIPOLOGIA_VALUES),
    ('oggetto_primario', ch.PARTNERSHIP_OGGETTO_VALUES),
    ('durata', ch.PARTNERSHIP_DURATA_VALUES),
    ('rinnovo', ch.PARTNERSHIP_RINNOVO_VALUES),
]


@pytest.mark.django_db
def test_get_progetto_create_renders_200(auth_client):
    r = auth_client.get(reverse('progetto_create'))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('field_name,expected_values', PROGETTO_SELECT_FIELDS)
def test_get_progetto_create_has_select_with_official_values(
    auth_client, field_name, expected_values,
):
    r = auth_client.get(reverse('progetto_create'))
    html = r.content.decode('utf-8')
    options = _select_options(html, field_name)
    # Empty option + tutti i valori ufficiali
    assert '' in options
    for v in expected_values:
        assert v in options, f'{v!r} mancante in <select name="{field_name}">'


@pytest.mark.django_db
def test_get_partnership_create_renders_200(auth_client):
    r = auth_client.get(reverse('partnership_create'))
    assert r.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('field_name,expected_values', PARTNERSHIP_SELECT_FIELDS)
def test_get_partnership_create_has_select_with_official_values(
    auth_client, field_name, expected_values,
):
    r = auth_client.get(reverse('partnership_create'))
    html = r.content.decode('utf-8')
    options = _select_options(html, field_name)
    assert '' in options
    for v in expected_values:
        assert v in options, f'{v!r} mancante in <select name="{field_name}">'


@pytest.mark.django_db
def test_get_partnership_create_status_includes_official_and_lead(auth_client):
    """Il select di status_partnership include i 3 valori ufficiali + 'In trattativa'."""
    r = auth_client.get(reverse('partnership_create'))
    html = r.content.decode('utf-8')
    options = _select_options(html, 'status_partnership')
    for v in ['Attiva', 'Conclusa', 'In fase di rinnovo', 'In trattativa']:
        assert v in options


# ============================================================
# POST create — happy path
# ============================================================

@pytest.mark.django_db
def test_post_progetto_create_valid_redirects_and_persists(auth_client):
    from dashboard.models import Progetti
    r = auth_client.post(reverse('progetto_create'), _progetto_post_data())
    assert r.status_code == 302
    assert Progetti.objects.filter(codice_progetto='PROG-INT-001').exists()


@pytest.mark.django_db
def test_post_partnership_create_valid_redirects_and_persists(auth_client):
    from dashboard.models import Partnership
    r = auth_client.post(reverse('partnership_create'), _partnership_post_data())
    assert r.status_code == 302
    assert Partnership.objects.filter(partnership='TestPartner').exists()


# ============================================================
# POST create — invalid choice
# ============================================================

@pytest.mark.django_db
def test_post_progetto_invalid_stato_returns_200_with_form_error(auth_client):
    r = auth_client.post(
        reverse('progetto_create'),
        _progetto_post_data(stato='Aspettando'),
    )
    assert r.status_code == 200
    assert 'stato' in r.context['form'].errors


@pytest.mark.django_db
def test_post_partnership_invalid_durata_returns_200_with_form_error(auth_client):
    r = auth_client.post(
        reverse('partnership_create'),
        _partnership_post_data(durata='5 anni'),
    )
    assert r.status_code == 200
    assert 'durata' in r.context['form'].errors


# ============================================================
# Filter dropdowns sourced from choices.py
# ============================================================

@pytest.mark.django_db
def test_progetti_list_filter_uses_choices_py(auth_client):
    r = auth_client.get(reverse('progetti'))
    assert r.status_code == 200
    assert list(r.context['stati']) == ch.STATO_PROGETTO_VALUES


@pytest.mark.django_db
def test_partnerships_list_filter_uses_choices_py(auth_client):
    r = auth_client.get(reverse('partnerships') + '?tab=partnership')
    assert r.status_code == 200
    assert list(r.context['stati_partnership']) == \
        ch.PARTNERSHIP_STATUS_OFFICIAL_VALUES


@pytest.mark.django_db
def test_partnerships_list_filter_excludes_in_trattativa(auth_client):
    r = auth_client.get(reverse('partnerships') + '?tab=partnership')
    assert 'In trattativa' not in list(r.context['stati_partnership'])


# ============================================================
# Lead tab still works
# ============================================================

@pytest.mark.django_db
def test_lead_tab_filters_in_trattativa(auth_client):
    """Crea una partnership con status='In trattativa' e verifica che appaia
    nella tab Lead, non nella tab Partnership."""
    from dashboard.models import Partnership
    Partnership.objects.create(
        partnership='LeadCo', status_partnership='In trattativa',
    )
    Partnership.objects.create(
        partnership='ActiveCo', status_partnership='Attiva',
    )

    r_lead = auth_client.get(reverse('partnerships') + '?tab=lead')
    assert r_lead.status_code == 200
    leads = list(r_lead.context['leads'])
    assert any(p.partnership == 'LeadCo' for p in leads)
    assert not any(p.partnership == 'ActiveCo' for p in leads)

    r_part = auth_client.get(reverse('partnerships') + '?tab=partnership')
    parts = list(r_part.context['partnerships'])
    assert any(p.partnership == 'ActiveCo' for p in parts)
    assert not any(p.partnership == 'LeadCo' for p in parts)
