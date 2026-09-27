"""Sezione TASK: permessi (tutti i loggati), CRUD, filtri, import Notion."""
from datetime import date, timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse

from dashboard import choices as ch
from dashboard.models import Soci, Task

User = get_user_model()


# ============================================================
# Fixtures
# ============================================================

def _socio(id_, nome, cognome, ruolo='Junior Consultant', area='D&A', status='Associato'):
    s = Soci(id=id_, nome_1=nome, cognome=cognome, ruolo=ruolo,
             area_di_appartenenza=area, status=status)
    s.save()
    return s


@pytest.fixture
def mario(db):
    return _socio(1, 'Mario', 'Rossi', area='D&A')


@pytest.fixture
def giulia(db):
    return _socio(2, 'Giulia', 'Bianchi', area='BD')


@pytest.fixture
def mario_client(client, mario):
    # Utente semplice (non editor/staff): per decisione deve poter fare tutto sulle task
    user = User.objects.create_user(username='mario.rossi', email=mario.email_jesap, password='Pwd!1234')
    client.force_login(user)
    return client


def _task(**kw):
    kw.setdefault('titolo', 'Task di prova')
    kw.setdefault('area', 'D&A')
    assegnatari = kw.pop('assegnatari', [])
    t = Task.objects.create(**kw)
    t.assegnatari.set(assegnatari)
    return t


def _post_data(**overrides):
    data = {
        'titolo': 'Aggiornare foglio soci',
        'area': 'D&A',
        'competenza': 'Data,  data , Automations',
        'stato': 'Da iniziare',
        'priorita': 'Alta',
        'effort': 'Small',
        'scadenza': '2030-01-31',
        'altri_assegnatari': '',
        'descrizione': 'Descrizione',
        'link': 'https://docs.google.com/a\n\nhttps://example.com/b',
    }
    data.update(overrides)
    return data


# ============================================================
# Model
# ============================================================

@pytest.mark.django_db
def test_scaduta_solo_se_non_completata():
    ieri = date.today() - timedelta(days=1)
    assert _task(scadenza=ieri).scaduta is True
    assert _task(scadenza=ieri, stato=ch.TASK_STATO_COMPLETATA).scaduta is False
    assert _task(scadenza=date.today()).scaduta is False
    assert _task(scadenza=None).scaduta is False


# ============================================================
# Permessi
# ============================================================

@pytest.mark.django_db
def test_lista_richiede_login(client):
    resp = client.get(reverse('tasks'))
    assert resp.status_code == 302
    assert reverse('login') in resp['Location']


@pytest.mark.django_db
def test_utente_semplice_puo_creare_modificare_eliminare(mario_client, mario, giulia):
    resp = mario_client.post(reverse('task_create'), _post_data(assegnatari=[mario.pk, giulia.pk]))
    assert resp.status_code == 302
    assert resp['Location'] == reverse('tasks') + '?tab=da'

    task = Task.objects.get()
    assert set(task.assegnatari.values_list('pk', flat=True)) == {mario.pk, giulia.pk}
    assert task.creato_da == 'Mario Rossi'
    assert task.competenza == 'Data, Automations'
    assert task.link == 'https://docs.google.com/a\nhttps://example.com/b'

    resp = mario_client.post(reverse('task_update', args=[task.pk]),
                             _post_data(titolo='Nuovo titolo', area='BD', assegnatari=[giulia.pk]))
    assert resp.status_code == 302
    task.refresh_from_db()
    assert task.titolo == 'Nuovo titolo'
    assert list(task.assegnatari.all()) == [giulia]

    resp = mario_client.post(reverse('task_delete', args=[task.pk]))
    assert resp.status_code == 302
    assert not Task.objects.exists()


@pytest.mark.django_db
def test_link_non_http_rifiutato(mario_client):
    resp = mario_client.post(reverse('task_create'), _post_data(link='javascript:alert(1)'))
    assert resp.status_code == 200
    assert not Task.objects.exists()
    assert 'Link non valido' in resp.content.decode()


# ============================================================
# Lista / filtri
# ============================================================

@pytest.mark.django_db
def test_tab_default_mie_task(mario_client, mario, giulia):
    _task(titolo='Mia task', assegnatari=[mario])
    _task(titolo='Task di Giulia', area='BD', assegnatari=[giulia])
    resp = mario_client.get(reverse('tasks'))
    assert resp.context['current_tab'] == 'mie'
    titoli = [t.titolo for t in resp.context['tasks']]
    assert titoli == ['Mia task']


@pytest.mark.django_db
def test_tab_area_e_filtro_aperte(mario_client, mario):
    _task(titolo='Aperta DA', area='D&A')
    _task(titolo='Chiusa DA', area='D&A', stato=ch.TASK_STATO_COMPLETATA)
    _task(titolo='Aperta BD', area='BD')

    resp = mario_client.get(reverse('tasks'), {'tab': 'da'})
    assert [t.titolo for t in resp.context['tasks']] == ['Aperta DA']
    assert resp.context['kpi']['completate'] == 1

    resp = mario_client.get(reverse('tasks'), {'tab': 'da', 'stato': ''})
    assert {t.titolo for t in resp.context['tasks']} == {'Aperta DA', 'Chiusa DA'}


@pytest.mark.django_db
def test_ricerca_per_assegnatario(mario_client, mario, giulia):
    _task(titolo='Uno', assegnatari=[giulia])
    _task(titolo='Due', altri_assegnatari='Ex Socio')
    _task(titolo='Tre')
    resp = mario_client.get(reverse('tasks'), {'tab': 'da', 'q': 'bianchi'})
    assert [t.titolo for t in resp.context['tasks']] == ['Uno']
    resp = mario_client.get(reverse('tasks'), {'tab': 'da', 'q': 'ex socio'})
    assert [t.titolo for t in resp.context['tasks']] == ['Due']


@pytest.mark.django_db
def test_nav_mostra_task(mario_client):
    html = mario_client.get(reverse('tasks')).content.decode()
    assert reverse('tasks') in html


# ============================================================
# Cambio stato rapido
# ============================================================

@pytest.mark.django_db
def test_set_stato(mario_client):
    task = _task()
    resp = mario_client.post(reverse('task_set_stato', args=[task.pk]),
                             {'stato': ch.TASK_STATO_IN_CORSO, 'next': reverse('tasks') + '?tab=da'})
    assert resp.status_code == 302
    assert resp['Location'] == reverse('tasks') + '?tab=da'
    task.refresh_from_db()
    assert task.stato == ch.TASK_STATO_IN_CORSO
    assert task.modificato_da == 'Mario Rossi'


@pytest.mark.django_db
def test_set_stato_invalido_e_next_esterno(mario_client):
    task = _task()
    resp = mario_client.post(reverse('task_set_stato', args=[task.pk]),
                             {'stato': 'Boh', 'next': 'https://evil.example.com/'})
    assert resp.status_code == 302
    assert 'evil.example.com' not in resp['Location']
    task.refresh_from_db()
    assert task.stato == ch.TASK_STATO_DA_INIZIARE


@pytest.mark.django_db
def test_set_stato_solo_post(mario_client):
    task = _task()
    assert mario_client.get(reverse('task_set_stato', args=[task.pk])).status_code == 405


# ============================================================
# Import Notion
# ============================================================

NOTION_CSV = (
    'Task name,Assignee,Blocked by,Competenza,Created by,Created time,Description,Due date,Effort level,'
    'Is blocking,Last edited by,Last edited time,Link del file,Parent-task,Past due,Priorità,Status,Sub-tasks,Task type\n'
    'Completamento questionario,Mario Rossi,,Audit,Giulia Bianchi,"January 15, 2025 4:54 PM",Ultimare,30/01/2025,Small,,'
    'Mario Rossi,"February 1, 2025 2:34 PM",https://docs.google.com/x,,⏰ Past Due,High,Done,,\n'
    'Dashboard,"mario rossi, Ex Socio",,"Auditor, Data",Giulia Bianchi,"May 1, 2025 7:10 PM","riga 1\nriga 2",'
    '02/05/2025 12:00 AM (GMT+2),,,Giulia Bianchi,"May 1, 2025 7:23 PM",'
    '"https://a.example.com/1, https://b.example.com/2",,⏰ Past Due,Low,In progress,,\n'
    # Stesso titolo + stesso minuto, assegnatari diversi: sono task distinte (caso reale "KPI")
    'KPI,Mario Rossi,,Auditor,Giulia Bianchi,"January 20, 2025 2:39 PM",,03/02/2025,Small,,Mario Rossi,"March 3, 2025 7:37 PM",,,,High,Done,,\n'
    'KPI,Giulia Bianchi,,Auditor,Giulia Bianchi,"January 20, 2025 2:39 PM",,03/02/2025,Small,,Mario Rossi,"March 3, 2025 7:37 PM",,,,High,Done,,\n'
)


@pytest.fixture
def notion_csv(tmp_path):
    p = tmp_path / 'tasks.csv'
    p.write_text(NOTION_CSV, encoding='utf-8')
    return str(p)


@pytest.mark.django_db
def test_import_notion(notion_csv, mario, giulia):
    out = StringIO()
    call_command('import_notion_tasks', notion_csv, '--area', 'D&A', stdout=out)

    assert Task.objects.count() == 4
    assert Task.objects.filter(titolo='KPI').count() == 2
    t1 = Task.objects.get(titolo='Completamento questionario')
    assert t1.stato == ch.TASK_STATO_COMPLETATA
    assert t1.priorita == 'Alta'
    assert t1.effort == 'Small'
    assert t1.scadenza == date(2025, 1, 30)
    assert list(t1.assegnatari.all()) == [mario]
    assert t1.creato_da == 'Giulia Bianchi'
    assert (t1.creato_il.year, t1.creato_il.month, t1.creato_il.day) == (2025, 1, 15)
    assert t1.scaduta is False  # completata: mai scaduta (Notion la segnava "Past Due")

    t2 = Task.objects.get(titolo='Dashboard')
    assert t2.stato == ch.TASK_STATO_IN_CORSO
    assert t2.scadenza == date(2025, 5, 2)
    assert t2.competenza == 'Auditor, Data'
    assert list(t2.assegnatari.all()) == [mario]
    assert t2.altri_assegnatari == 'Ex Socio'
    assert t2.link_list == ['https://a.example.com/1', 'https://b.example.com/2']
    assert t2.descrizione == 'riga 1\nriga 2'
    assert 'Ex Socio' in out.getvalue()

    # Idempotente
    out = StringIO()
    call_command('import_notion_tasks', notion_csv, '--area', 'D&A', stdout=out)
    assert Task.objects.count() == 4
    assert '0 task importate, 4 già presenti' in out.getvalue()


@pytest.mark.django_db
def test_import_notion_dry_run(notion_csv, mario):
    out = StringIO()
    call_command('import_notion_tasks', notion_csv, '--area', 'D&A', '--dry-run', stdout=out)
    assert Task.objects.count() == 0
    assert '[DRY-RUN]' in out.getvalue()
