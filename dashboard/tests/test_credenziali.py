"""Area CREDENZIALI: accesso solo CdA + responsabili, cifratura, audit."""
import json

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from dashboard.models import AuditLog, Credenziale, Soci
from dashboard.permissions import can_access_credenziali

User = get_user_model()

PASSWORD = 'S3gret0-Canva!'
NOTE = 'codici recupero: 1111 2222'


def _user_for(client, id_, nome, cognome, ruolo, status='Associato', area='BD'):
    socio = Soci(id=id_, nome_1=nome, cognome=cognome, ruolo=ruolo,
                 status=status, area_di_appartenenza=area)
    socio.save()
    user = User.objects.create_user(username=f'{nome}.{cognome}'.lower(), email=socio.email_jesap, password='Pwd!1234')
    client.force_login(user)
    return user


@pytest.fixture
def head_client(client, db):
    _user_for(client, 1, 'Anna', 'Verdi', 'Head of')
    return client


@pytest.fixture
def cred(db):
    c = Credenziale(area='M&C', servizio='Canva', username='mc@jesap.it')
    c.password = PASSWORD
    c.note = NOTE
    c.save()
    return c


# ============================================================
# Permessi
# ============================================================

@pytest.mark.django_db
@pytest.mark.parametrize('ruolo,status,atteso', [
    ('President', 'Associato', True),
    ('Vice President and Secretary General', 'Associato', True),  # ruolo combinato reale in SOCI
    ('Treasurer', 'Associato', True),
    ('International Manager', 'Associato', True),
    ('Head of', 'Associato', True),
    ('Deputy Manager', 'Associato', False),
    ('Junior Consultant', 'Associato', False),
    ('Head of', 'Alumnus', False),  # ex responsabile: fuori
])
def test_accesso_per_ruolo(client, ruolo, status, atteso):
    user = _user_for(client, 10, 'Test', 'Utente', ruolo, status=status)
    assert can_access_credenziali(user) is atteso
    resp = client.get(reverse('credenziali'))
    assert resp.status_code == (200 if atteso else 403)


@pytest.mark.django_db
def test_superuser_senza_socio_non_accede(client):
    admin = User.objects.create_superuser('admin', 'admin@example.com', 'Pwd!1234')
    client.force_login(admin)
    assert client.get(reverse('credenziali')).status_code == 403


@pytest.mark.django_db
def test_anonimo_rediretto_al_login(client):
    resp = client.get(reverse('credenziali'))
    assert resp.status_code == 302
    assert reverse('login') in resp['Location']


@pytest.mark.django_db
def test_link_nav_solo_per_chi_ha_accesso(client):
    _user_for(client, 20, 'Luca', 'Neri', 'Junior Consultant')
    assert reverse('credenziali') not in client.get(reverse('tasks')).content.decode()

    client.logout()
    _user_for(client, 21, 'Sara', 'Blu', 'President')
    assert reverse('credenziali') in client.get(reverse('tasks')).content.decode()


@pytest.mark.django_db
def test_utente_senza_accesso_non_puo_rivelare(client, cred):
    _user_for(client, 30, 'Luca', 'Neri', 'Junior Consultant')
    assert client.post(reverse('credenziale_reveal', args=[cred.pk])).status_code == 403
    assert client.get(reverse('credenziale_update', args=[cred.pk])).status_code == 403
    assert client.post(reverse('credenziale_delete', args=[cred.pk])).status_code == 403
    assert Credenziale.objects.exists()


# ============================================================
# Cifratura
# ============================================================

@pytest.mark.django_db
def test_create_cifra_password_e_note(head_client):
    resp = head_client.post(reverse('credenziale_create'), {
        'area': 'BD', 'servizio': 'LinkedIn', 'url': 'https://linkedin.com',
        'username': 'bd@jesap.it', 'password': PASSWORD, 'note': NOTE,
    })
    assert resp.status_code == 302
    c = Credenziale.objects.get()
    assert PASSWORD not in c.password_cifrata
    assert NOTE not in c.note_cifrate
    assert c.password == PASSWORD
    assert c.note == NOTE
    assert c.modificato_da == 'Anna Verdi'


@pytest.mark.django_db
def test_create_richiede_password(head_client):
    resp = head_client.post(reverse('credenziale_create'), {'area': 'BD', 'servizio': 'X', 'password': ''})
    assert resp.status_code == 200
    assert not Credenziale.objects.exists()


@pytest.mark.django_db
def test_update_password_vuota_mantiene_la_vecchia(head_client, cred):
    vecchio_token_note = cred.note_cifrate
    resp = head_client.post(reverse('credenziale_update', args=[cred.pk]), {
        'area': 'M&C', 'servizio': 'Canva Pro', 'url': '', 'username': 'mc@jesap.it',
        'password': '', 'note': NOTE,
    })
    assert resp.status_code == 302
    cred.refresh_from_db()
    assert cred.servizio == 'Canva Pro'
    assert cred.password == PASSWORD
    assert cred.note_cifrate == vecchio_token_note  # note invariate → non ri-cifrate


@pytest.mark.django_db
def test_lista_non_contiene_segreti_e_non_va_in_cache(head_client, cred):
    resp = head_client.get(reverse('credenziali'))
    html = resp.content.decode()
    assert 'Canva' in html
    assert PASSWORD not in html
    assert NOTE not in html
    assert 'no-store' in resp['Cache-Control'] or 'max-age=0' in resp['Cache-Control']


# ============================================================
# Rivela + audit
# ============================================================

@pytest.mark.django_db
def test_rivela_restituisce_segreti_e_registra_accesso(head_client, cred):
    resp = head_client.post(reverse('credenziale_reveal', args=[cred.pk]))
    assert resp.status_code == 200
    assert json.loads(resp.content) == {'password': PASSWORD, 'note': NOTE}

    log = AuditLog.objects.filter(action=AuditLog.ACTION_VIEW).get()
    assert log.user_repr == 'anna.verdi'
    assert log.object_pk == str(cred.pk)


@pytest.mark.django_db
def test_rivela_solo_post(head_client, cred):
    assert head_client.get(reverse('credenziale_reveal', args=[cred.pk])).status_code == 405


@pytest.mark.django_db
def test_audit_log_mai_in_chiaro(head_client, cred):
    head_client.post(reverse('credenziale_update', args=[cred.pk]), {
        'area': 'M&C', 'servizio': 'Canva', 'url': '', 'username': 'mc@jesap.it',
        'password': 'NuovaPassword!', 'note': NOTE,
    })
    dump = json.dumps(list(AuditLog.objects.values('changes')))
    assert PASSWORD not in dump
    assert 'NuovaPassword!' not in dump
    assert NOTE not in dump
    assert cred.password_cifrata not in dump
    update = AuditLog.objects.filter(action=AuditLog.ACTION_UPDATE).get()
    assert 'password_cifrata' in update.changes  # la modifica è tracciata (solo impronta)


# ============================================================
# Chiave mancante
# ============================================================

@pytest.mark.django_db
def test_senza_chiave_il_crm_non_si_rompe(head_client, cred):
    with override_settings(CREDENTIALS_ENCRYPTION_KEY=''):
        resp = head_client.get(reverse('credenziali'))
        assert resp.status_code == 200
        assert 'CREDENTIALS_ENCRYPTION_KEY' in resp.content.decode()

        resp = head_client.get(reverse('credenziale_create'))
        assert resp.status_code == 302

        resp = head_client.post(reverse('credenziale_reveal', args=[cred.pk]))
        assert resp.status_code == 503

        assert head_client.get(reverse('tasks')).status_code == 200
