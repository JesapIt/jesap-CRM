"""Regression tests per i bug emersi dall'audit (settembre 2026).

Ogni test riproduce un difetto osservato: data loss, crash 500, email
sbagliate, permessi, ordinamenti e rendering.
"""
import datetime
import re
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from dashboard.forms import LeadForm, ProgettoForm, _parse_money_to_decimal
from dashboard.models import AuditLog, Lead, Partnership, Progetti, Soci

User = get_user_model()


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def editor_client(client, db):
    user = User.objects.create_user(
        username='editor', email='editor@jesap.it', password='Pwd!1234', is_staff=True,
    )
    client.force_login(user)
    return client


@pytest.fixture
def member_client(client, db):
    """Utente loggato senza privilegi editor/admin."""
    user = User.objects.create_user(
        username='mario.rossi', email='mario.rossi@jesap.it', password='Pwd!1234',
    )
    client.force_login(user)
    return client


def _sql(ctx, prefix):
    return [q['sql'] for q in ctx.captured_queries if q['sql'].startswith(prefix)]


# ============================================================
# LEADS — data loss / DB-managed columns
# ============================================================

def test_lead_edit_form_renders_iso_dates_for_date_inputs():
    lead = Lead(
        lead_id='LEAD-X', azienda='ACME',
        data_primo_contatto=datetime.date(2026, 6, 22),
        data_prossima_azione=datetime.date(2026, 7, 1),
    )
    form = LeadForm(instance=lead)
    assert 'value="2026-06-22"' in str(form['data_primo_contatto'])
    assert 'value="2026-07-01"' in str(form['data_prossima_azione'])


@pytest.mark.django_db
def test_lead_form_clearing_valore_stimato_sets_none():
    lead = Lead.objects.create(lead_id='LEAD-1', azienda='ACME', valore_stimato=Decimal('500'))
    form = LeadForm({'azienda': 'ACME', 'valore_stimato_input': ''}, instance=lead)
    assert form.is_valid(), form.errors
    assert form.save(commit=False).valore_stimato is None


@pytest.mark.django_db
def test_lead_create_blank_fase_and_stato_use_db_defaults(editor_client):
    # Il browser invia la <select> vuota come stringa vuota, non la omette.
    editor_client.post(reverse('lead_create'), {'azienda': 'ACME', 'fase_attuale': '', 'stato_lead': ''})
    lead = Lead.objects.get(azienda='ACME')
    assert lead.fase_attuale == 'Nuovo'
    assert lead.stato_lead == 'Attiva'


DB_MANAGED_COLUMNS = ('"valore_ponderato"', '"alert_follow_up"', '"ultimo_aggiornamento"', '"created_at"')


@pytest.mark.django_db
def test_lead_insert_skips_generated_and_trigger_columns(editor_client):
    with CaptureQueriesContext(connection) as ctx:
        editor_client.post(reverse('lead_create'), {'azienda': 'ACME'})
    inserts = _sql(ctx, 'INSERT INTO "LEADS"')
    assert inserts, 'nessuna INSERT su LEADS'
    for col in DB_MANAGED_COLUMNS + ('"data_creazione"',):
        assert col not in inserts[0], f'{col} non deve essere scritto in INSERT'


@pytest.mark.django_db
def test_lead_update_skips_generated_and_trigger_columns(editor_client):
    Lead.objects.create(lead_id='LEAD-1', azienda='ACME')
    with CaptureQueriesContext(connection) as ctx:
        editor_client.post(reverse('lead_update', args=['LEAD-1']), {'azienda': 'ACME 2'})
    updates = _sql(ctx, 'UPDATE "LEADS"')
    assert updates, 'nessuna UPDATE su LEADS'
    for col in DB_MANAGED_COLUMNS + ('"storico_aggiornamenti"',):
        assert col not in updates[0], f'{col} non deve essere scritto in UPDATE'
    assert Lead.objects.get(pk='LEAD-1').azienda == 'ACME 2'


@pytest.mark.django_db
def test_lead_create_never_overwrites_existing_lead_on_id_collision(editor_client, monkeypatch):
    Lead.objects.create(lead_id='LEAD-EXIST', azienda='Vecchia')
    ids = iter(['LEAD-EXIST', 'LEAD-NEW'])
    monkeypatch.setattr('dashboard.forms._generate_lead_id', lambda: next(ids))
    editor_client.post(reverse('lead_create'), {'azienda': 'Nuova'})
    assert Lead.objects.get(pk='LEAD-EXIST').azienda == 'Vecchia'
    assert Lead.objects.get(pk='LEAD-NEW').azienda == 'Nuova'


@pytest.mark.django_db
def test_lead_create_is_audited(editor_client):
    editor_client.post(reverse('lead_create'), {'azienda': 'ACME'})
    lead = Lead.objects.get(azienda='ACME')
    assert AuditLog.objects.filter(action='create', object_pk=lead.pk).exists()


@pytest.mark.django_db
def test_success_message_shown_on_leads_page(editor_client):
    r = editor_client.post(reverse('lead_create'), {'azienda': 'ACME'}, follow=True)
    assert 'Lead creata con successo!' in r.content.decode()


# ============================================================
# PROGETTI — date/money parsing, sort, collisioni PK, rendering
# ============================================================

@pytest.mark.parametrize('raw', ['2023-09-01', '01/09/2023', '1/9/2023', '01-09-2023'])
def test_progetto_edit_form_keeps_date_in_any_stored_format(raw):
    p = Progetti(codice_progetto='AB0923', nome_progetto='Abc', data_inizio=raw)
    assert ProgettoForm(instance=p).initial['data_inizio'] == '2023-09-01'


@pytest.mark.parametrize('raw, expected', [
    ('880', Decimal('880')),
    ('€ 1.234', Decimal('1234')),
    ('1.234.567', Decimal('1234567')),
    ('€ 1.234,56', Decimal('1234.56')),
    ('1234,56', Decimal('1234.56')),
    ('1.5', Decimal('1.5')),
    ('12.50', Decimal('12.50')),
])
def test_parse_money_handles_italian_thousands(raw, expected):
    assert _parse_money_to_decimal(raw) == expected


def _progetti_names_in_order(content):
    return re.findall(r'<td data-sort-key="progetto">([^<]+)</td>', content)


@pytest.mark.django_db
def test_progetti_sort_by_fatturato(editor_client):
    for code, name, money in [('A1', 'Aaa', '€ 100,00'), ('B1', 'Bbb', '€ 2000,00'), ('C1', 'Ccc', '€ 30,00')]:
        Progetti(codice_progetto=code, nome_progetto=name, fatturato_senza_iva_field=money).save()
    r = editor_client.get(reverse('progetti'), {'sort': 'fatturato', 'dir': 'asc'})
    assert _progetti_names_in_order(r.content.decode()) == ['Ccc', 'Aaa', 'Bbb']


@pytest.mark.django_db
def test_progetti_list_without_named_rows_shows_empty_state(editor_client):
    Progetti(codice_progetto='X1', nome_progetto=None).save()
    Progetti(codice_progetto='X2', nome_progetto='None').save()
    r = editor_client.get(reverse('progetti'))
    assert 'Nessun progetto trovato.' in r.content.decode()


@pytest.mark.django_db
def test_progetti_money_formatted_server_side(editor_client):
    Progetti(codice_progetto='M1', nome_progetto='Money', fatturato_senza_iva_field='1234.5').save()
    r = editor_client.get(reverse('progetti'))
    assert '1.234,50 €' in r.content.decode()


@pytest.mark.django_db
def test_progetto_create_code_collision_does_not_overwrite(editor_client, monkeypatch):
    Progetti(codice_progetto='AB0923', nome_progetto='Vecchio').save()
    monkeypatch.setattr(
        'dashboard.utils.codice_generator.generate_codice_progetto', lambda *a, **k: 'AB0923',
    )
    r = editor_client.post(reverse('progetto_create'), {
        'nome_progetto': 'Abc', 'data_inizio': '2023-09-01',
    })
    assert r.status_code == 200
    assert Progetti.objects.get(pk='AB0923').nome_progetto == 'Vecchio'


# ============================================================
# PARTNERSHIP — PK con "/", ordinamento testo, form per kind
# ============================================================

@pytest.mark.django_db
def test_partnerships_list_with_slash_in_name_renders(editor_client):
    Partnership.objects.create(partnership='ACME / Beta', status_partnership='Attiva')
    r = editor_client.get(reverse('partnerships'))
    assert r.status_code == 200
    assert 'ACME / Beta' in r.content.decode()


@pytest.mark.django_db
def test_partnership_with_slash_in_name_is_editable(editor_client):
    Partnership.objects.create(partnership='ACME / Beta', status_partnership='Attiva')
    r = editor_client.get(reverse('partnership_update', args=['ACME / Beta']))
    assert r.status_code == 200


@pytest.mark.django_db
def test_text_sort_ignores_digits_inside_names(editor_client):
    for name in ('Beta 2', 'Alfa'):
        Partnership.objects.create(partnership=name, status_partnership='In trattativa')
    r = editor_client.get(reverse('partnerships'), {'tab': 'lead', 'sort': 'nome', 'dir': 'asc'})
    content = r.content.decode()
    assert content.index('Alfa') < content.index('Beta 2')


@pytest.mark.django_db
def test_lead_partnership_form_renders_only_its_fields(editor_client):
    r = editor_client.get(reverse('partnership_create_kind', args=['lead']))
    assert '<label for=""' not in r.content.decode()


# ============================================================
# AUTH — registrazione, reset password, permessi
# ============================================================

@pytest.mark.django_db
def test_password_reset_email_uses_custom_templates(client):
    User.objects.create_user(username='mario.rossi', email='mario.rossi@jesap.it', password='Pwd!1234')
    mail.outbox.clear()  # email di benvenuto inviata alla creazione utente
    client.post(reverse('password_reset'), {'email': 'mario.rossi@jesap.it'})
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert 'JESAP Gestionale' in msg.subject
    assert '<html' not in msg.body
    assert 'JESAP Gestionale' in msg.body
    assert msg.alternatives and msg.alternatives[0][1] == 'text/html'


def _step2_url(email='mario.rossi@jesap.it'):
    return reverse('register_step2', args=[signing.TimestampSigner().sign(email)])


@pytest.mark.django_db
def test_register_step2_missing_password_does_not_crash(client):
    r = client.post(_step2_url(), {})
    assert r.status_code == 200
    assert not User.objects.exists()


@pytest.mark.django_db
def test_register_step2_rejects_weak_password(client):
    r = client.post(_step2_url(), {'password': '12345678', 'password_confirm': '12345678'})
    assert r.status_code == 200
    assert not User.objects.exists()


@pytest.mark.django_db
def test_register_step2_accepts_strong_password(client):
    r = client.post(_step2_url(), {'password': 'Zq8!vLmw2', 'password_confirm': 'Zq8!vLmw2'})
    assert r.status_code == 302
    assert User.objects.filter(username='mario.rossi', email='mario.rossi@jesap.it').exists()


@pytest.mark.django_db
def test_admin_promote_invalid_user_id_does_not_crash(editor_client):
    r = editor_client.post(reverse('admin_promote'), {'user_id': 'abc'})
    assert r.status_code == 302


@pytest.mark.django_db
def test_admin_promote_rejects_get(editor_client):
    target = User.objects.create_user(username='x', email='x@jesap.it', password='Pwd!1234')
    editor_client.get(reverse('admin_promote'), {'user_id': target.pk})
    target.refresh_from_db()
    assert not target.is_staff


@pytest.mark.django_db
def test_admin_tab_hidden_from_non_staff(member_client):
    r = member_client.get(reverse('soci'), {'tab': 'admin'})
    assert r.context['current_tab'] != 'admin'
    assert 'admin_users' not in r.context


@pytest.mark.django_db
def test_non_editor_gets_403_on_editor_pages(member_client):
    r = member_client.get(reverse('progetto_create'))
    assert r.status_code == 403


@pytest.mark.django_db
def test_anonymous_redirected_to_login_on_editor_pages(client):
    r = client.get(reverse('progetto_create'))
    assert r.status_code == 302
    assert r.url.startswith(reverse('login'))


# ============================================================
# SOCI
# ============================================================

@pytest.mark.django_db
@pytest.mark.parametrize('ruolo', ['President', 'Vice President', 'Treasurer', 'Secretary General'])
def test_board_tab_includes_board_roles(editor_client, ruolo):
    Soci(nome_1='Mario', cognome='Rossi', ruolo=ruolo, status='Associato').save()
    r = editor_client.get(reverse('soci'), {'tab': 'board'})
    assert 'Mario Rossi' in r.content.decode()


# ============================================================
# OPS
# ============================================================

@pytest.mark.django_db
def test_healthz_does_not_leak_exception_details(client, monkeypatch):
    class _Broken:
        def cursor(self):
            raise RuntimeError('db.secret-host.supabase.co refused')

    monkeypatch.setattr('dashboard.views.connection', _Broken())
    r = client.get(reverse('healthz'))
    assert r.status_code == 503
    assert 'secret-host' not in r.content.decode()


@pytest.mark.django_db
def test_bootstrap_admin_refuses_default_password_outside_debug(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command('bootstrap_admin')
    assert not User.objects.exists()


@pytest.mark.django_db
def test_soci_save_computes_age_from_sheet_date_format():
    """Il sync Sheets scrive DD/MM/YYYY: ETÀ e PERMANENZA non devono azzerarsi."""
    s = Soci(nome_1='Mario', cognome='Rossi', data_di_nascita='15/03/2000', data_entrata='01/10/2023')
    s.save()
    assert s.etα is not None
    assert s.permanenza_mesi_field is not None


# ============================================================
# DEV LOCALE
# ============================================================

@pytest.mark.django_db
def test_setup_local_db_seeds_demo_data_idempotently():
    call_command('setup_local_db', demo=True)
    counts = (Progetti.objects.count(), Partnership.objects.count(), Lead.objects.count(), Soci.objects.count())
    assert all(counts)
    call_command('setup_local_db', demo=True)
    assert (Progetti.objects.count(), Partnership.objects.count(),
            Lead.objects.count(), Soci.objects.count()) == counts
