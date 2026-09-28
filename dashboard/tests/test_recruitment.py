"""Sezione RECRUITMENT: accessi, webhook candidature, schede, email, import."""
import json
from datetime import date, time
from decimal import Decimal
from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from dashboard import choices as ch
from dashboard.models import (
    Candidato, ColloquioIndividuale, EmailCandidato, GruppoColloquio, RecruitmentSessione, Soci,
)
from dashboard.permissions import RECRUITMENT_GROUP, can_access_recruitment
from dashboard.recruitment import emails
from dashboard.recruitment.intake import mappa_risposta

User = get_user_model()
_next_id = iter(range(100, 10_000))


# ============================================================
# Fixtures / helpers
# ============================================================

def _socio_user(nome, cognome, ruolo='Junior Consultant', area='HR', status='Associato'):
    socio = Soci(id=next(_next_id), nome_1=nome, cognome=cognome, ruolo=ruolo,
                 area_di_appartenenza=area, status=status)
    socio.save()
    user = User.objects.create_user(username=f'{nome}.{cognome}'.lower(), email=socio.email_jesap, password='Pwd!1234')
    return socio, user


@pytest.fixture
def head_hr(db):
    return _socio_user('Irene', 'Rossi', ruolo='Head of', area='HR')


@pytest.fixture
def hr_client(client, head_hr):
    client.force_login(head_hr[1])
    mail.outbox.clear()  # email di benvenuto inviata alla creazione dell'utente
    return client


@pytest.fixture
def sessione(db):
    return RecruitmentSessione.objects.create(nome='Spring REC 26', aperta=True)


def _cand(sessione, nome='Luca', cognome='Bianchi', **kw):
    kw.setdefault('email', f'{nome}.{cognome}@example.com'.lower())
    kw.setdefault('area_1', 'BD')
    return Candidato.objects.create(sessione=sessione, nome=nome, cognome=cognome, **kw)


def _formset_post(formset, modifiche):
    """POST data di un formset renderizzato, con {pk: {campo: valore}} applicato sopra."""
    data = {}
    for key, value in formset.management_form.initial.items():
        data[f'{formset.prefix}-{key}'] = value
    for form in formset.forms:
        override = modifiche.get(form.instance.pk, {})
        for name, field in form.fields.items():
            value = override.get(name, form[name].value())
            key = form.add_prefix(name)
            if isinstance(value, bool) and field.widget.input_type == 'checkbox':
                if value:
                    data[key] = 'on'
                continue
            data[key] = '' if value is None else (
                {True: 'true', False: 'false'}.get(value, value) if isinstance(value, bool) else value
            )
    return data


FORM_ROW = {
    'Informazioni cronologiche': '27/09/2026 14:03:22',
    'Indirizzo di mail': 'Mario.Verdi@Example.com ',
    'Nome': 'Mario',
    'Cognome': 'Verdi',
    'N. Telefono': '3331234567',
    'Facoltà': 'Economia',
    'Curriculum': 'https://drive.google.com/cv',
    'Area 1': 'Business Development',
    'Area 2': 'Marketing & Communication',
    'Domanda nuova del form': 'risposta libera',
}


def _api(client, payload, token='test-token'):
    return client.post(
        reverse('rec_api_candidature'), data=json.dumps(payload), content_type='application/json',
        HTTP_AUTHORIZATION=f'Bearer {token}',
    )


# ============================================================
# Accessi
# ============================================================

@pytest.mark.django_db
@pytest.mark.parametrize('ruolo,area,nel_gruppo,status,atteso', [
    ('President', 'Board', False, 'Associato', True),
    ('Head of', 'BD', False, 'Associato', True),
    ('Junior Consultant', 'HR', False, 'Associato', False),
    ('Junior Consultant', 'HR', True, 'Associato', True),     # autorizzato
    ('Junior Consultant', 'HR', True, 'Alumnus', False),      # autorizzato ma non più socio attivo
])
def test_accesso_recruitment(client, ruolo, area, nel_gruppo, status, atteso):
    _, user = _socio_user('Ada', 'Neri', ruolo=ruolo, area=area, status=status)
    if nel_gruppo:
        user.groups.add(Group.objects.get_or_create(name=RECRUITMENT_GROUP)[0])
    assert can_access_recruitment(user) is atteso
    client.force_login(user)
    assert client.get(reverse('rec_home')).status_code == (200 if atteso else 403)
    assert (reverse('rec_home') in client.get(reverse('tasks')).content.decode()) is atteso


@pytest.mark.django_db
def test_head_autorizza_solo_la_propria_area(hr_client):
    _, junior_hr = _socio_user('Sara', 'Blu', area='HR')
    _, junior_bd = _socio_user('Marco', 'Gialli', area='BD')

    resp = hr_client.get(reverse('rec_accessi'))
    scelte = [v for v, _ in resp.context['form'].fields['utente'].choices]
    assert junior_hr.pk in scelte and junior_bd.pk not in scelte

    assert hr_client.post(reverse('rec_accessi'), {'utente': junior_bd.pk}).status_code == 200  # form non valido
    assert not junior_bd.groups.filter(name=RECRUITMENT_GROUP).exists()

    assert hr_client.post(reverse('rec_accessi'), {'utente': junior_hr.pk}).status_code == 302
    assert junior_hr.groups.filter(name=RECRUITMENT_GROUP).exists()

    # Revoca di un socio di un'altra area → 403
    junior_bd.groups.add(Group.objects.get(name=RECRUITMENT_GROUP))
    resp = hr_client.post(reverse('rec_accessi'), {'azione': 'revoca', 'utente': junior_bd.pk})
    assert resp.status_code == 403

    resp = hr_client.post(reverse('rec_accessi'), {'azione': 'revoca', 'utente': junior_hr.pk})
    assert resp.status_code == 302
    assert not junior_hr.groups.filter(name=RECRUITMENT_GROUP).exists()


@pytest.mark.django_db
def test_cda_autorizza_chiunque(client):
    _, pres = _socio_user('Paola', 'Viola', ruolo='President', area='Board')
    _, junior_bd = _socio_user('Marco', 'Gialli', area='BD')
    client.force_login(pres)
    assert client.post(reverse('rec_accessi'), {'utente': junior_bd.pk}).status_code == 302
    assert junior_bd.groups.filter(name=RECRUITMENT_GROUP).exists()


@pytest.mark.django_db
def test_autorizzato_non_gestisce_accessi(client):
    _, user = _socio_user('Sara', 'Blu', area='HR')
    user.groups.add(Group.objects.get_or_create(name=RECRUITMENT_GROUP)[0])
    client.force_login(user)
    assert client.get(reverse('rec_accessi')).status_code == 403


# ============================================================
# Webhook candidature
# ============================================================

def test_mappa_risposta_intestazioni():
    campi, altre = mappa_risposta(FORM_ROW)
    assert campi['email'] == 'mario.verdi@example.com'
    assert campi['telefono'] == '3331234567'
    assert campi['facolta'] == 'Economia'
    assert campi['area_1'] == 'BD' and campi['area_2'] == 'M&C'
    assert (campi['data_candidatura'].year, campi['data_candidatura'].hour) == (2026, 14)
    assert altre == {'Domanda nuova del form': 'risposta libera'}


@pytest.mark.django_db
def test_webhook_crea_candidato_e_invia_conferma(client, sessione):
    resp = _api(client, {'risposta': FORM_ROW})
    assert resp.status_code == 201
    c = Candidato.objects.get()
    assert (c.sessione, c.nome, c.area_1, c.esito_screening) == (sessione, 'Mario', 'BD', '')
    assert len(mail.outbox) == 1 and mail.outbox[0].to == ['mario.verdi@example.com']
    assert 'Mario' in mail.outbox[0].body
    assert EmailCandidato.objects.get().tipo == 'conferma_ricezione'

    # Retry della stessa riga: nessun duplicato, nessuna nuova email
    resp = _api(client, {'risposte': [FORM_ROW]})
    assert resp.status_code == 200
    assert json.loads(resp.content)['risultati'][0]['stato'] == 'duplicato'
    assert Candidato.objects.count() == 1 and len(mail.outbox) == 1

    # Stessa email, nuova candidatura → Doppione, senza conferma
    resp = _api(client, {'risposta': {**FORM_ROW, 'Informazioni cronologiche': '28/09/2026 10:00:00'}})
    assert resp.status_code == 201
    assert Candidato.objects.filter(esito_screening='Doppione').count() == 1
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_webhook_sicurezza_e_errori(client, sessione):
    assert _api(client, {'risposta': FORM_ROW}, token='sbagliato').status_code == 401
    with override_settings(RECRUITMENT_WEBHOOK_TOKEN=''):
        assert _api(client, {'risposta': FORM_ROW}, token='').status_code == 503
    assert client.get(reverse('rec_api_candidature')).status_code == 405

    resp = _api(client, {'risposte': [{'Nome': 'Senza email'}]})
    assert resp.status_code == 200
    assert json.loads(resp.content)['risultati'][0]['stato'] == 'errore'

    sessione.aperta = False
    sessione.save()
    assert _api(client, {'risposta': FORM_ROW}).status_code == 409
    assert not Candidato.objects.exists()


@pytest.mark.django_db
def test_una_sola_sessione_aperta(sessione):
    nuova = RecruitmentSessione.objects.create(nome='Fall REC 26', aperta=True)
    sessione.refresh_from_db()
    assert nuova.aperta and not sessione.aperta


# ============================================================
# Schede e flusso
# ============================================================

@pytest.mark.django_db
def test_flusso_completo(hr_client, sessione, head_hr):
    passa = _cand(sessione, 'Luca', 'Bianchi', area_2='HR')
    scarta = _cand(sessione, 'Anna', 'Neri')

    for tab in ('candidature', 'gruppi', 'individuali', 'prova'):
        assert hr_client.get(reverse('rec_tab', args=[sessione.pk, tab])).status_code == 200

    # 1) Screening
    url = reverse('rec_tab', args=[sessione.pk, 'candidature'])
    fs = hr_client.get(url).context['formset']
    resp = hr_client.post(url, _formset_post(fs, {passa.pk: {'esito_screening': 'Passato'},
                                                  scarta.pk: {'esito_screening': 'Scartato'}}))
    assert resp.status_code == 302

    # 2) Gruppo: solo chi ha passato lo screening
    gruppo = GruppoColloquio.objects.create(sessione=sessione, numero=1, data=date(2026, 10, 13),
                                            ora=time(19, 0), luogo='meet.google.com/abc')
    url = reverse('rec_tab', args=[sessione.pk, 'gruppi'])
    resp = hr_client.get(url)
    assert [r['c'].pk for r in resp.context['righe']] == [passa.pk]
    resp = hr_client.post(url, _formset_post(resp.context['formset'], {passa.pk: {
        'gruppo': gruppo.pk, 'presenza_gruppo': True, 'punteggio_output': '2.5',
        'punteggio_soft_gruppo': '3', 'esito_gruppo': 'Ammesso',
    }}))
    assert resp.status_code == 302
    passa.refresh_from_db()
    assert passa.media_gruppo == Decimal('2.85')  # 2.5*0.3 + 3*0.7

    # 3) Individuale: riga creata in automatico; esito "Seconda scelta" → seconda riga
    url = reverse('rec_tab', args=[sessione.pk, 'individuali'])
    resp = hr_client.get(url)
    prima = ColloquioIndividuale.objects.get(candidato=passa)
    assert prima.tipo == ch.REC_TIPO_PRIMA and prima.area == 'BD'
    resp = hr_client.post(url, _formset_post(resp.context['formset'], {prima.pk: {
        'punteggio_soft': '3', 'punteggio_hard': '2', 'esito': 'Seconda scelta',
    }}))
    assert resp.status_code == 302
    resp = hr_client.get(url)
    seconda = ColloquioIndividuale.objects.get(candidato=passa, tipo=ch.REC_TIPO_SECONDA)
    assert seconda.area == 'HR'
    assert len(resp.context['righe']) == 2
    prima.refresh_from_db()
    assert prima.media_individuale == Decimal('2.50')
    assert prima.media_colloqui == Decimal('2.68')  # media(2.50, 2.85) = 2.675 → 2.68

    resp = hr_client.post(url, _formset_post(resp.context['formset'], {seconda.pk: {
        'esito': 'Ammesso', 'area_probabile': 'HR',
    }}))
    assert resp.status_code == 302

    # 4) Periodo di prova: area proposta dal colloquio decisivo
    url = reverse('rec_tab', args=[sessione.pk, 'prova'])
    resp = hr_client.get(url)
    assert [r['c'].pk for r in resp.context['righe']] == [passa.pk]
    passa.refresh_from_db()
    assert passa.area_prova == 'HR'

    # Prolungato senza settimane → errore
    resp = hr_client.post(url, _formset_post(resp.context['formset'], {passa.pk: {'esito_finale': 'Prolungato'}}))
    assert resp.status_code == 200
    assert 'Indica di quante settimane' in resp.content.decode()
    resp = hr_client.post(url, _formset_post(hr_client.get(url).context['formset'], {passa.pk: {
        'esito_finale': 'Prolungato', 'settimane_prolungamento': 2,
    }}))
    assert resp.status_code == 302
    passa.refresh_from_db()
    assert passa.fase == 'Esito finale: Prolungato'


@pytest.mark.django_db
def test_gruppo_di_altra_sessione_rifiutato(hr_client, sessione):
    c = _cand(sessione, esito_screening='Passato')
    altra = RecruitmentSessione.objects.create(nome='Altra')
    gruppo_altrui = GruppoColloquio.objects.create(sessione=altra, numero=1)
    url = reverse('rec_tab', args=[sessione.pk, 'gruppi'])
    fs = hr_client.get(url).context['formset']
    resp = hr_client.post(url, _formset_post(fs, {c.pk: {'gruppo': gruppo_altrui.pk}}))
    assert resp.status_code == 200
    c.refresh_from_db()
    assert c.gruppo is None


# ============================================================
# Email
# ============================================================

@pytest.mark.django_db
def test_invio_esiti_screening_in_blocco(hr_client, sessione):
    sessione.template_email = {'screening_passato': {'oggetto': 'Ok {nome}', 'corpo': 'Brava {nome} {cognome}!'}}
    sessione.save()
    _cand(sessione, 'Luca', 'Bianchi', esito_screening='Passato')
    _cand(sessione, 'Anna', 'Neri', esito_screening='Scartato')
    _cand(sessione, 'Dup', 'Dup', esito_screening='Doppione')
    _cand(sessione, 'Da', 'Valutare')

    url = reverse('rec_invia_email', args=[sessione.pk, emails.FASE_SCREENING])
    resp = hr_client.post(url, {'next': reverse('rec_tab', args=[sessione.pk, 'candidature'])})
    assert resp.status_code == 302
    assert sorted(m.subject for m in mail.outbox) == ['La tua candidatura a JESAP — esito screening', 'Ok Luca']
    assert any(m.body == 'Brava Luca Bianchi!' for m in mail.outbox)
    assert EmailCandidato.objects.filter(ok=True).count() == 2
    assert EmailCandidato.objects.first().inviata_da == 'Irene Rossi'

    # Secondo click: niente da inviare
    hr_client.post(url)
    assert len(mail.outbox) == 2


@pytest.mark.django_db
def test_esito_gruppo_bloccato_senza_colloquio_pianificato(hr_client, sessione):
    c = _cand(sessione, esito_screening='Passato', esito_gruppo='Ammesso')
    prima = ColloquioIndividuale.objects.create(candidato=c, tipo=ch.REC_TIPO_PRIMA)
    pronti, bloccati = emails.da_inviare(list(Candidato.objects.all()), emails.FASE_ESITO_GRUPPO)
    assert pronti == [] and bloccati == {'colloquio individuale non ancora pianificato': 1}

    prima.data, prima.ora, prima.link_meet = date(2026, 10, 21), time(18, 45), 'meet.google.com/xyz'
    prima.save()
    hr_client.post(reverse('rec_invia_email', args=[sessione.pk, emails.FASE_ESITO_GRUPPO]))
    assert len(mail.outbox) == 1
    assert '21/10/2026' in mail.outbox[0].body and '18:45' in mail.outbox[0].body
    assert 'meet.google.com/xyz' in mail.outbox[0].body


@pytest.mark.django_db
@override_settings(RECRUITMENT_EMAIL_BATCH=2)
def test_invio_a_blocchi(hr_client, sessione):
    for i in range(3):
        _cand(sessione, f'N{i}', f'C{i}', esito_screening='Passato')
    url = reverse('rec_invia_email', args=[sessione.pk, emails.FASE_SCREENING])
    resp = hr_client.post(url, follow=True)
    assert len(mail.outbox) == 2
    assert 'Ne restano 1' in resp.content.decode()
    hr_client.post(url)
    assert len(mail.outbox) == 3


@pytest.mark.django_db
def test_errore_invio_registrato(sessione):
    c = _cand(sessione, esito_screening='Passato')
    with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=RuntimeError('Resend down')):
        log = emails.invia(c, 'screening_passato', 'test')
    assert log.ok is False and 'Resend down' in log.errore
    # l'errore non conta come "inviata": resta da inviare
    pronti, _ = emails.da_inviare([Candidato.objects.prefetch_related('email_log').get()], emails.FASE_SCREENING)
    assert len(pronti) == 1


@pytest.mark.django_db
def test_esito_finale_prolungato_usa_settimane(sessione):
    c = _cand(sessione, esito_finale='Prolungato', settimane_prolungamento=2)
    emails.invia(c, 'finale_prolungato')
    assert 'di 2 settimane' in mail.outbox[0].body


# ============================================================
# Sessioni, candidato, import
# ============================================================

@pytest.mark.django_db
def test_nuova_sessione_eredita_testi_email(hr_client, sessione):
    sessione.template_email = {'conferma_ricezione': {'corpo': 'Testo nostro'}}
    sessione.save()
    resp = hr_client.post(reverse('rec_sessione_create'), {'nome': 'Fall REC 26', 'aperta': 'on', 'conferma_automatica': 'on'})
    assert resp.status_code == 302
    nuova = RecruitmentSessione.objects.get(nome='Fall REC 26')
    assert nuova.aperta and nuova.template_email == {'conferma_ricezione': {'corpo': 'Testo nostro'}}


@pytest.mark.django_db
def test_template_salva_solo_personalizzati(hr_client, sessione):
    url = reverse('rec_sessione_update', args=[sessione.pk])
    form = hr_client.get(url).context['template_form']
    data = {name: form[name].value() for name in form.fields}
    data['azione'] = 'template'
    data['corpo__screening_scartato'] = 'Ciao {nome}, purtroppo no.'
    assert hr_client.post(url, data).status_code == 302
    sessione.refresh_from_db()
    assert sessione.template_email == {'screening_scartato': {'corpo': 'Ciao {nome}, purtroppo no.'}}


@pytest.mark.django_db
def test_scheda_candidato_invio_ed_eliminazione(hr_client, sessione):
    c = _cand(sessione)
    url = reverse('rec_candidato', args=[c.pk])
    assert hr_client.get(url).status_code == 200
    assert hr_client.post(url, {'azione': 'invia_email', 'tipo': 'conferma_ricezione'}).status_code == 302
    assert len(mail.outbox) == 1
    assert hr_client.post(url, {'azione': 'elimina'}).status_code == 302
    assert not Candidato.objects.exists() and not EmailCandidato.objects.exists()


@pytest.mark.django_db
def test_import_candidature(tmp_path):
    p = tmp_path / 'risposte.csv'
    p.write_text(
        'Informazioni cronologiche,Indirizzo di mail,Nome,Cognome,Area 1,Area 2\n'
        '27/09/2026 14:03:22,a@example.com,Anna,Neri,Data & Automation,Human Resources\n'
        '27/09/2026 15:00:00,b@example.com,Bruno,Rossi,Legal,\n'
        '28/09/2026 09:00:00,a@example.com,Anna,Neri,Data & Automation,\n'
        ',,,,,\n',
        encoding='utf-8',
    )
    out = StringIO()
    call_command('import_candidature', str(p), '--sessione', 'Fall REC 25', '--crea-sessione', stdout=out)
    assert '2 candidature importate, 1 doppioni' in out.getvalue()
    s = RecruitmentSessione.objects.get(nome='Fall REC 25')
    assert s.aperta is False
    assert Candidato.objects.get(email='b@example.com').area_1 == 'Legal'
    assert len(mail.outbox) == 0

    out = StringIO()
    call_command('import_candidature', str(p), '--sessione', 'Fall REC 25', stdout=out)
    assert '0 candidature importate' in out.getvalue() and '3 già presenti' in out.getvalue()
