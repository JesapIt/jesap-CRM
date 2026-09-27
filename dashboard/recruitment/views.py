import hmac
import json
import logging
from functools import wraps
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.forms import modelformset_factory
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from dashboard import choices as ch
from dashboard.audit import write_log
from dashboard.models import (
    Candidato, ColloquioIndividuale, GruppoColloquio, RecruitmentSessione,
)
from dashboard.permissions import (
    RECRUITMENT_GROUP, can_access_recruitment, can_authorize_for_recruitment,
    can_manage_recruitment_access, display_name, get_socio, is_cda, is_responsabile,
)

from . import emails
from .forms import (
    AccessoForm, CandidatoForm, ColloquioRowForm, GruppoForm, GruppoRowForm, ProvaRowForm,
    ScreeningRowForm, SessioneForm, TemplateEmailForm, soci_choices, utenti_con_socio,
)
from .intake import RispostaNonValida, registra_candidatura

logger = logging.getLogger(__name__)

TAB_CANDIDATURE = 'candidature'
TAB_GRUPPI = 'gruppi'
TAB_INDIVIDUALI = 'individuali'
TAB_PROVA = 'prova'
TABS = [
    (TAB_CANDIDATURE, '1 · Screening CV'),
    (TAB_GRUPPI, '2 · Colloqui di gruppo'),
    (TAB_INDIVIDUALI, '3 · Colloqui individuali'),
    (TAB_PROVA, '4 · Periodo di prova'),
]
TAB_FASI_EMAIL = {
    TAB_CANDIDATURE: [emails.FASE_SCREENING],
    TAB_GRUPPI: [emails.FASE_CONVOCAZIONE_GRUPPO, emails.FASE_ESITO_GRUPPO],
    TAB_INDIVIDUALI: [emails.FASE_ESITO_INDIVIDUALE],
    TAB_PROVA: [emails.FASE_ESITO_FINALE],
}
# Etichetta breve della colonna "email" in tabella
FASE_BREVE = {
    emails.FASE_SCREENING: 'Esito',
    emails.FASE_CONVOCAZIONE_GRUPPO: 'Convocazione',
    emails.FASE_ESITO_GRUPPO: 'Esito',
    emails.FASE_ESITO_INDIVIDUALE: 'Esito',
    emails.FASE_ESITO_FINALE: 'Esito',
}


# ============================================================
# Accesso
# ============================================================

def recruitment_access_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not can_access_recruitment(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return never_cache(login_required(_wrapped, login_url='login'))


def recruitment_manager_required(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not can_manage_recruitment_access(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return never_cache(login_required(_wrapped, login_url='login'))


# ============================================================
# Helpers
# ============================================================

def _candidati(sessione):
    return (
        Candidato.objects.filter(sessione=sessione)
        .select_related('gruppo', 'sessione')
        .prefetch_related('colloqui', 'email_log')
        .order_by('cognome', 'nome', 'id')
    )


def _allinea_colloqui(sessione):
    """Crea i colloqui mancanti: prima scelta per gli ammessi al gruppo, seconda se richiesta."""
    nuovi = []
    for c in Candidato.objects.filter(sessione=sessione, esito_gruppo='Ammesso').prefetch_related('colloqui'):
        prima = c.colloquio(ch.REC_TIPO_PRIMA)
        if prima is None:
            nuovi.append(ColloquioIndividuale(candidato=c, tipo=ch.REC_TIPO_PRIMA, area=c.area_1))
        elif prima.esito == 'Seconda scelta' and c.colloquio(ch.REC_TIPO_SECONDA) is None:
            nuovi.append(ColloquioIndividuale(candidato=c, tipo=ch.REC_TIPO_SECONDA, area=c.area_2))
    if nuovi:
        ColloquioIndividuale.objects.bulk_create(nuovi, ignore_conflicts=True)


def _funnel(candidati):
    return [
        ('Candidature', len(candidati)),
        ('Screening passato', sum(1 for c in candidati if c.esito_screening == 'Passato')),
        ('Ammessi al colloquio individuale', sum(1 for c in candidati if c.esito_gruppo == 'Ammesso')),
        ('Ammessi al periodo di prova', sum(1 for c in candidati if c.esito_individuale == 'Ammesso')),
        ('Ammessi in associazione', sum(1 for c in candidati if c.esito_finale == 'Ammesso')),
    ]


def _filtra(righe, q, area, get_candidato, get_area):
    q = (q or '').strip().lower()
    out = []
    for r in righe:
        c = get_candidato(r)
        if q and q not in f'{c.nome} {c.cognome} {c.email}'.lower():
            continue
        if area and get_area(r) != area:
            continue
        out.append(r)
    return out


def _stato_email(candidato, fase):
    tipo, motivo = emails.email_dovuta(candidato, fase)
    inviate = {e.tipo: e for e in candidato.email_log.all() if e.ok}
    if tipo and tipo in inviate:
        return {'stato': 'inviata', 'label': 'Inviata', 'quando': inviate[tipo].inviata_il}
    if tipo:
        return {'stato': 'da_inviare', 'label': 'Da inviare'}
    if motivo:
        return {'stato': 'bloccata', 'label': motivo}
    return {'stato': 'nessuna', 'label': '—'}


def _tab_url(sessione, tab, request=None):
    url = reverse('rec_tab', args=[sessione.pk, tab])
    if request is not None:
        params = {k: v for k, v in request.GET.items() if k in ('q', 'area') and v}
        if params:
            url += '?' + urlencode(params)
    return url


# ============================================================
# Pagine principali
# ============================================================

@recruitment_access_required
def recruitment_home(request):
    sessione = RecruitmentSessione.objects.filter(aperta=True).first() or RecruitmentSessione.objects.first()
    if sessione is None:
        return render(request, 'dashboard/recruitment/vuoto.html', {
            'can_manage': can_manage_recruitment_access(request.user),
        })
    return redirect('rec_tab', sessione.pk, TAB_CANDIDATURE)


@recruitment_access_required
def recruitment_tab(request, sessione_id, tab):
    sessione = get_object_or_404(RecruitmentSessione, pk=sessione_id)
    if tab not in dict(TABS):
        return redirect('rec_tab', sessione.pk, TAB_CANDIDATURE)
    _allinea_colloqui(sessione)

    candidati = list(_candidati(sessione))
    q = request.GET.get('q', '')
    area = request.GET.get('area', '')
    form_kwargs = {}
    gruppi = []

    if tab == TAB_CANDIDATURE:
        righe = _filtra(candidati, q, area, lambda c: c, lambda c: c.area_1)
        FormSet = modelformset_factory(Candidato, form=ScreeningRowForm, extra=0)
        qs = Candidato.objects.filter(pk__in=[c.pk for c in righe])
    elif tab == TAB_GRUPPI:
        base = [c for c in candidati if c.esito_screening == 'Passato']
        righe = _filtra(base, q, area, lambda c: c, lambda c: c.area_1)
        FormSet = modelformset_factory(Candidato, form=GruppoRowForm, extra=0)
        qs = Candidato.objects.filter(pk__in=[c.pk for c in righe])
        gruppi = list(sessione.gruppi.select_related('recruiter_1', 'recruiter_2', 'recruiter_3').order_by('numero'))
        form_kwargs = {
            'sessione': sessione,
            'gruppi_choices': [('', '—')] + [
                (g.pk, f'{g.numero}' + (f' · {g.data:%d/%m}' if g.data else '')) for g in gruppi
            ],
        }
    elif tab == TAB_INDIVIDUALI:
        per_id = {c.pk: c for c in candidati}
        colloqui = [
            col for c in candidati if c.esito_gruppo == 'Ammesso'
            for col in sorted(c.colloqui.all(), key=lambda x: x.tipo != ch.REC_TIPO_PRIMA)
        ]
        righe = _filtra(colloqui, q, area, lambda col: per_id[col.candidato_id], lambda col: col.area)
        FormSet = modelformset_factory(ColloquioIndividuale, form=ColloquioRowForm, extra=0)
        qs = ColloquioIndividuale.objects.filter(pk__in=[col.pk for col in righe])
        form_kwargs = {'soci': soci_choices()}
    else:  # TAB_PROVA
        base = [c for c in candidati if c.esito_individuale == 'Ammesso']
        righe = _filtra(base, q, area, lambda c: c, lambda c: c.area_prova)
        FormSet = modelformset_factory(Candidato, form=ProvaRowForm, extra=0)
        qs = Candidato.objects.filter(pk__in=[c.pk for c in righe])
        # Area di prova proposta = area probabile del colloquio decisivo
        da_precompilare = [c for c in base if not c.area_prova and c.colloquio_decisivo]
        for c in da_precompilare:
            c.area_prova = c.colloquio_decisivo.area_probabile or c.colloquio_decisivo.area
        Candidato.objects.bulk_update([c for c in da_precompilare if c.area_prova], ['area_prova'])

    # Ordine righe = ordine formset
    ordine = [r.pk for r in righe]
    qs = qs.order_by()
    if request.method == 'POST':
        formset = FormSet(request.POST, queryset=qs, form_kwargs=form_kwargs)
        if formset.is_valid():
            salvati = formset.save()
            if salvati:
                messages.success(request, f'Salvate {len(salvati)} righe.')
            else:
                messages.info(request, 'Nessuna modifica da salvare.')
            return redirect(_tab_url(sessione, tab, request))
        messages.error(request, 'Alcune righe contengono errori: correggi i campi evidenziati.')
    else:
        formset = FormSet(queryset=qs, form_kwargs=form_kwargs)

    forms_per_pk = {f.instance.pk: f for f in formset.forms}
    per_cand = {c.pk: c for c in candidati}
    colloqui_per_pk = {r.pk: r for r in righe} if tab == TAB_INDIVIDUALI else {}
    fasi_tab = TAB_FASI_EMAIL[tab]
    righe_ctx = []
    for pk in ordine:
        form = forms_per_pk.get(pk)
        if form is None:
            continue
        colloquio = colloqui_per_pk.get(pk)
        cand = per_cand[colloquio.candidato_id] if colloquio else per_cand[pk]
        if colloquio:
            colloquio.candidato = cand  # media_colloqui senza query extra
        righe_ctx.append({
            'form': form, 'c': cand, 'colloquio': colloquio,
            'email': [(FASE_BREVE[f], _stato_email(cand, f)) for f in fasi_tab],
            'conferma': any(e.tipo == 'conferma_ricezione' and e.ok for e in cand.email_log.all()),
        })

    email_azioni = []
    for fase in TAB_FASI_EMAIL[tab]:
        pronti, bloccati = emails.da_inviare(candidati, fase)
        email_azioni.append({'fase': fase, 'label': emails.FASI_EMAIL[fase], 'pronti': len(pronti), 'bloccati': bloccati})

    return render(request, f'dashboard/recruitment/tab_{tab}.html', {
        'sessione': sessione,
        'sessioni': RecruitmentSessione.objects.all(),
        'tabs': TABS,
        'tab': tab,
        'funnel': _funnel(candidati),
        'formset': formset,
        'righe': righe_ctx,
        'gruppi': gruppi,
        'email_azioni': email_azioni,
        'q': q,
        'area': area,
        'aree': ch.REC_AREA_VALUES,
        'can_manage': can_manage_recruitment_access(request.user),
    })


@recruitment_access_required
@require_POST
def recruitment_invia_email(request, sessione_id, fase):
    sessione = get_object_or_404(RecruitmentSessione, pk=sessione_id)
    if fase not in emails.FASI_EMAIL:
        raise PermissionDenied
    nxt = request.POST.get('next') or ''
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        nxt = reverse('rec_tab', args=[sessione.pk, TAB_CANDIDATURE])

    pronti, bloccati = emails.da_inviare(list(_candidati(sessione)), fase)
    if not pronti:
        messages.info(request, 'Nessuna email da inviare.')
        return redirect(nxt)
    ok, errori, restanti = emails.invia_in_blocco(pronti, display_name(request.user))
    msg = f'{emails.FASI_EMAIL[fase]}: {ok} email inviate'
    if errori:
        msg += f', {errori} errori (vedi la scheda del candidato)'
    if restanti:
        msg += f'. Ne restano {restanti}: clicca di nuovo "Invia" per continuare'
    (messages.warning if errori else messages.success)(request, msg + '.')
    return redirect(nxt)


# ============================================================
# Sessioni
# ============================================================

@recruitment_access_required
def sessione_create(request):
    if request.method == 'POST':
        form = SessioneForm(request.POST)
        if form.is_valid():
            sessione = form.save(commit=False)
            ultima = RecruitmentSessione.objects.first()
            if ultima:  # riusa i testi email della sessione precedente
                sessione.template_email = dict(ultima.template_email or {})
            sessione.save()
            messages.success(request, f'Sessione "{sessione.nome}" creata.')
            return redirect('rec_tab', sessione.pk, TAB_CANDIDATURE)
    else:
        form = SessioneForm(initial={'aperta': True})
    return render(request, 'dashboard/recruitment/sessione_form.html', {'form': form, 'nuova': True})


@recruitment_access_required
def sessione_update(request, sessione_id):
    sessione = get_object_or_404(RecruitmentSessione, pk=sessione_id)
    form = SessioneForm(instance=sessione)
    template_form = TemplateEmailForm(sessione=sessione)
    if request.method == 'POST':
        if request.POST.get('azione') == 'template':
            template_form = TemplateEmailForm(request.POST, sessione=sessione)
            if template_form.is_valid():
                template_form.save()
                messages.success(request, 'Testi delle email salvati.')
                return redirect('rec_sessione_update', sessione.pk)
        else:
            form = SessioneForm(request.POST, instance=sessione)
            if form.is_valid():
                form.save()
                messages.success(request, 'Impostazioni sessione salvate.')
                return redirect('rec_sessione_update', sessione.pk)
    return render(request, 'dashboard/recruitment/sessione_form.html', {
        'form': form, 'template_form': template_form, 'sessione': sessione, 'nuova': False,
    })


# ============================================================
# Gruppi di colloquio
# ============================================================

@recruitment_access_required
def gruppo_create(request, sessione_id):
    sessione = get_object_or_404(RecruitmentSessione, pk=sessione_id)
    if request.method == 'POST':
        form = GruppoForm(request.POST, sessione=sessione)
        if form.is_valid():
            gruppo = form.save(commit=False)
            gruppo.sessione = sessione
            gruppo.save()
            messages.success(request, f'Gruppo {gruppo.numero} creato.')
            return redirect('rec_tab', sessione.pk, TAB_GRUPPI)
    else:
        prossimo = (sessione.gruppi.order_by('-numero').values_list('numero', flat=True).first() or 0) + 1
        form = GruppoForm(sessione=sessione, initial={'numero': prossimo})
    return render(request, 'dashboard/recruitment/gruppo_form.html', {'form': form, 'sessione': sessione})


@recruitment_access_required
def gruppo_update(request, pk):
    gruppo = get_object_or_404(GruppoColloquio, pk=pk)
    sessione = gruppo.sessione
    if request.method == 'POST':
        if request.POST.get('azione') == 'elimina':
            n = gruppo.numero
            gruppo.delete()
            messages.success(request, f'Gruppo {n} eliminato (i candidati restano, senza gruppo).')
            return redirect('rec_tab', sessione.pk, TAB_GRUPPI)
        form = GruppoForm(request.POST, instance=gruppo, sessione=sessione)
        if form.is_valid():
            form.save()
            messages.success(request, f'Gruppo {gruppo.numero} aggiornato.')
            return redirect('rec_tab', sessione.pk, TAB_GRUPPI)
    else:
        form = GruppoForm(instance=gruppo, sessione=sessione)
    return render(request, 'dashboard/recruitment/gruppo_form.html', {
        'form': form, 'sessione': sessione, 'gruppo': gruppo,
        'candidati': gruppo.candidati.order_by('cognome', 'nome'),
    })


# ============================================================
# Candidato
# ============================================================

@recruitment_access_required
def candidato_create(request, sessione_id):
    sessione = get_object_or_404(RecruitmentSessione, pk=sessione_id)
    if request.method == 'POST':
        form = CandidatoForm(request.POST)
        if form.is_valid():
            candidato = form.save(commit=False)
            candidato.sessione = sessione
            candidato.save()
            messages.success(request, f'Candidato {candidato} aggiunto.')
            return redirect('rec_candidato', candidato.pk)
    else:
        form = CandidatoForm()
    return render(request, 'dashboard/recruitment/candidato_form.html', {'form': form, 'sessione': sessione})


@recruitment_access_required
def candidato_detail(request, pk):
    candidato = get_object_or_404(
        Candidato.objects.select_related('sessione', 'gruppo').prefetch_related('colloqui', 'email_log'), pk=pk,
    )
    if request.method == 'POST':
        azione = request.POST.get('azione')
        if azione == 'invia_email':
            tipo = request.POST.get('tipo', '')
            if tipo not in emails.TIPI:
                messages.error(request, 'Tipo di email non valido.')
            else:
                log = emails.invia(candidato, tipo, display_name(request.user))
                if log.ok:
                    messages.success(request, f'Email "{emails.TIPI[tipo][0]}" inviata a {candidato.email}.')
                else:
                    messages.error(request, f'Invio non riuscito: {log.errore}')
            return redirect('rec_candidato', candidato.pk)
        if azione == 'elimina':
            sessione_id = candidato.sessione_id
            nome = str(candidato)
            candidato.delete()
            messages.success(request, f'Candidato {nome} e tutti i suoi dati eliminati.')
            return redirect('rec_tab', sessione_id, TAB_CANDIDATURE)
        form = CandidatoForm(request.POST, instance=candidato)
        if form.is_valid():
            form.save()
            messages.success(request, 'Dati del candidato aggiornati.')
            return redirect('rec_candidato', candidato.pk)
    else:
        form = CandidatoForm(instance=candidato)

    colloqui = sorted(candidato.colloqui.all(), key=lambda x: x.tipo != ch.REC_TIPO_PRIMA)
    for col in colloqui:  # evita query extra nel template
        col.candidato = candidato
    return render(request, 'dashboard/recruitment/candidato.html', {
        'c': candidato,
        'form': form,
        'colloqui': colloqui,
        'email_log': candidato.email_log.all(),
        'tipi_email': [(k, v[0]) for k, v in emails.TIPI.items()],
        'altre_risposte': sorted((candidato.altre_risposte or {}).items()),
    })


# ============================================================
# Accessi (CdA + Head of)
# ============================================================

@recruitment_manager_required
def accessi(request):
    group, _ = Group.objects.get_or_create(name=RECRUITMENT_GROUP)
    tutti = utenti_con_socio()
    membri = set(group.user_set.values_list('pk', flat=True))
    sempre = [(u, s) for u, s in tutti if is_cda(s) or is_responsabile(s)]
    sempre_ids = {u.pk for u, _ in sempre}
    autorizzati = [(u, s) for u, s in tutti if u.pk in membri and u.pk not in sempre_ids]
    autorizzabili = [
        (u, s) for u, s in tutti
        if u.pk not in membri and u.pk not in sempre_ids and can_authorize_for_recruitment(request.user, s)
    ]
    soci_per_user = {u.pk: s for u, s in tutti}

    if request.method == 'POST':
        if request.POST.get('azione') == 'revoca':
            target = get_object_or_404(get_user_model(), pk=request.POST.get('utente'))
            if not can_authorize_for_recruitment(request.user, soci_per_user.get(target.pk)):
                raise PermissionDenied
            target.groups.remove(group)
            write_log(target, 'update', changes={'accesso_recruitment': {'old': True, 'new': False}})
            messages.success(request, f'Accesso revocato a {soci_per_user[target.pk].nome_e_cognome}.')
            return redirect('rec_accessi')
        form = AccessoForm(request.POST, candidati_utenti=autorizzabili)
        if form.is_valid():
            target = form.cleaned_data['utente']
            target.groups.add(group)
            write_log(target, 'update', changes={'accesso_recruitment': {'old': False, 'new': True}})
            messages.success(request, f'{soci_per_user[target.pk].nome_e_cognome} ora può accedere al Recruitment.')
            return redirect('rec_accessi')
    else:
        form = AccessoForm(candidati_utenti=autorizzabili)

    manager = get_socio(request.user)
    return render(request, 'dashboard/recruitment/accessi.html', {
        'form': form,
        'sempre': sempre,
        'autorizzati': [
            (u, s, can_authorize_for_recruitment(request.user, s)) for u, s in autorizzati
        ],
        'is_cda': is_cda(manager),
        'area_manager': manager.area_di_appartenenza if manager else '',
    })


# ============================================================
# Webhook candidature (Apps Script sul foglio risposte del form)
# ============================================================

@csrf_exempt
@require_POST
def api_candidature(request):
    """
    POST JSON {"risposta": {intestazione: valore, ...}} oppure {"risposte": [...]}
    Header: Authorization: Bearer <RECRUITMENT_WEBHOOK_TOKEN>
    """
    token = getattr(settings, 'RECRUITMENT_WEBHOOK_TOKEN', '')
    if not token:
        return JsonResponse({'error': 'webhook non configurato'}, status=503)
    atteso = f'Bearer {token}'.encode()
    if not hmac.compare_digest(request.headers.get('Authorization', '').encode(), atteso):
        return JsonResponse({'error': 'non autorizzato'}, status=401)
    try:
        payload = json.loads(request.body or b'{}')
    except ValueError:
        return JsonResponse({'error': 'JSON non valido'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'JSON non valido'}, status=400)

    risposte = payload.get('risposte')
    if risposte is None and 'risposta' in payload:
        risposte = [payload['risposta']]
    if not isinstance(risposte, list) or not all(isinstance(r, dict) for r in risposte):
        return JsonResponse({'error': 'attesi "risposta" (oggetto) o "risposte" (lista)'}, status=400)

    sessione = RecruitmentSessione.objects.filter(aperta=True).first()
    if sessione is None:
        return JsonResponse({'error': 'nessuna sessione di recruitment aperta nel CRM'}, status=409)

    risultati = []
    for risposta in risposte:
        try:
            candidato, stato = registra_candidatura(sessione, risposta)
        except RispostaNonValida as exc:
            risultati.append({'stato': 'errore', 'errore': str(exc)})
            continue
        if stato == 'creato' and sessione.conferma_automatica:
            emails.invia(candidato, 'conferma_ricezione', 'automatico')
        risultati.append({'stato': stato, 'id': candidato.pk})

    # 2xx anche con righe invalide: il dettaglio è in `risultati` e lo script non deve ritentarle all'infinito
    creati = sum(1 for r in risultati if r['stato'] in ('creato', 'doppione'))
    status = 201 if creati else 200
    logger.info('Webhook candidature: sessione=%s risultati=%s', sessione.nome, [r['stato'] for r in risultati])
    return JsonResponse({'sessione': sessione.nome, 'risultati': risultati}, status=status)
