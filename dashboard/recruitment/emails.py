"""Email ai candidati (sostituisce gli scenari Make.com).

- Testi per sessione in `RecruitmentSessione.template_email`, con fallback ai
  default qui sotto. Segnaposto `{nome}`, `{data_colloquio}`, ...
- Invio via EMAIL_BACKEND (Resend in produzione), ogni tentativo registrato in
  `EmailCandidato` (ok/errore): è la fonte di "email già inviata".
"""
import re
import time

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import linebreaks, urlize

from dashboard import choices as ch
from dashboard.models import EmailCandidato

# tipo → (etichetta, segnaposto specifici oltre a {nome} {cognome} {sessione})
TIPI = {
    'conferma_ricezione': ('Conferma ricezione candidatura', []),
    'screening_passato': ('Screening CV: passato', []),
    'screening_scartato': ('Screening CV: scartato', []),
    'convocazione_gruppo': ('Convocazione colloquio di gruppo', ['numero_gruppo', 'data_gruppo', 'ora_gruppo', 'luogo_gruppo']),
    'gruppo_ammesso': ('Colloquio di gruppo: ammesso + convocazione individuale', ['data_colloquio', 'ora_colloquio', 'link_colloquio']),
    'gruppo_non_ammesso': ('Colloquio di gruppo: non ammesso', []),
    'individuale_ammesso': ('Colloquio individuale: ammesso al periodo di prova', ['area', 'link_welcome_day']),
    'individuale_non_ammesso': ('Colloquio individuale: non ammesso', []),
    'seconda_scelta': ('Seconda scelta: convocazione nuovo colloquio', ['area', 'data_colloquio', 'ora_colloquio', 'link_colloquio']),
    'finale_ammesso': ('Esito finale: ammesso in associazione', ['area']),
    'finale_non_ammesso': ('Esito finale: non ammesso', []),
    'finale_prolungato': ('Esito finale: periodo di prova prolungato', ['settimane']),
}

_FIRMA = '\n\nUn saluto,\nTeam HR — JESAP Junior Enterprise'

# Testi di esempio: vanno sostituiti con quelli attuali (Make) da "Impostazioni sessione".
DEFAULT_TEMPLATES = {
    'conferma_ricezione': (
        'Abbiamo ricevuto la tua candidatura — JESAP',
        'Ciao {nome},\n\ngrazie per esserti candidato/a a JESAP! Abbiamo ricevuto la tua candidatura '
        'e ti aggiorneremo al più presto sui prossimi passi.' + _FIRMA,
    ),
    'screening_passato': (
        'La tua candidatura a JESAP — esito screening',
        'Ciao {nome},\n\nabbiamo il piacere di comunicarti che la tua candidatura ha superato lo screening CV. '
        'A breve riceverai le informazioni per il colloquio di gruppo.' + _FIRMA,
    ),
    'screening_scartato': (
        'La tua candidatura a JESAP — esito screening',
        'Ciao {nome},\n\nti ringraziamo per l\'interesse verso JESAP. Purtroppo la tua candidatura non è stata '
        'selezionata per le fasi successive.' + _FIRMA,
    ),
    'convocazione_gruppo': (
        'JESAP — Convocazione colloquio di gruppo',
        'Ciao {nome},\n\nti aspettiamo al colloquio di gruppo:\n\n'
        'Data: {data_gruppo}\nOra: {ora_gruppo}\nLuogo: {luogo_gruppo}' + _FIRMA,
    ),
    'gruppo_ammesso': (
        'JESAP — Esito colloquio di gruppo',
        'Ciao {nome},\n\ncomplimenti, hai superato il colloquio di gruppo! Ti aspettiamo al colloquio individuale:\n\n'
        'Data: {data_colloquio}\nOra: {ora_colloquio}\nLink: {link_colloquio}' + _FIRMA,
    ),
    'gruppo_non_ammesso': (
        'JESAP — Esito colloquio di gruppo',
        'Ciao {nome},\n\nti ringraziamo per aver partecipato al colloquio di gruppo. Purtroppo non sei stato/a '
        'ammesso/a alla fase successiva.' + _FIRMA,
    ),
    'individuale_ammesso': (
        'JESAP — Esito colloquio individuale',
        'Ciao {nome},\n\ncomplimenti! Sei stato/a ammesso/a al periodo di prova nell\'area {area}.\n\n'
        'Ti aspettiamo al Welcome Day: {link_welcome_day}' + _FIRMA,
    ),
    'individuale_non_ammesso': (
        'JESAP — Esito colloquio individuale',
        'Ciao {nome},\n\nti ringraziamo per il tempo dedicato ai colloqui. Purtroppo non sei stato/a ammesso/a '
        'al periodo di prova.' + _FIRMA,
    ),
    'seconda_scelta': (
        'JESAP — Colloquio per la tua seconda area',
        'Ciao {nome},\n\nvorremmo conoscerti meglio anche per l\'area {area}. Ti aspettiamo al colloquio:\n\n'
        'Data: {data_colloquio}\nOra: {ora_colloquio}\nLink: {link_colloquio}' + _FIRMA,
    ),
    'finale_ammesso': (
        'Benvenuto/a in JESAP!',
        'Ciao {nome},\n\nhai concluso con successo il periodo di prova: sei ufficialmente associato/a di JESAP '
        'nell\'area {area}!' + _FIRMA,
    ),
    'finale_non_ammesso': (
        'JESAP — Esito periodo di prova',
        'Ciao {nome},\n\nti ringraziamo per il percorso fatto insieme. Purtroppo il periodo di prova non si è '
        'concluso con l\'ammissione in associazione.' + _FIRMA,
    ),
    'finale_prolungato': (
        'JESAP — Esito periodo di prova',
        'Ciao {nome},\n\nabbiamo deciso di prolungare il tuo periodo di prova di {settimane} settimane, '
        'per darti modo di dimostrare al meglio le tue capacità.' + _FIRMA,
    ),
}

_PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')


class EmailNonInviabile(Exception):
    pass


def template(sessione, tipo):
    """(oggetto, corpo) personalizzati per la sessione, altrimenti default."""
    custom = (sessione.template_email or {}).get(tipo) or {}
    default_oggetto, default_corpo = DEFAULT_TEMPLATES[tipo]
    return (custom.get('oggetto') or default_oggetto, custom.get('corpo') or default_corpo)


def is_personalizzato(sessione, tipo):
    custom = (sessione.template_email or {}).get(tipo) or {}
    return bool(custom.get('oggetto') or custom.get('corpo'))


def _fmt_data(d):
    return d.strftime('%d/%m/%Y') if d else ''


def _fmt_ora(t):
    return t.strftime('%H:%M') if t else ''


def contesto(candidato):
    sessione = candidato.sessione
    ctx = {
        'nome': candidato.nome,
        'cognome': candidato.cognome,
        'sessione': sessione.nome,
        'link_welcome_day': sessione.link_welcome_day,
        'settimane': str(candidato.settimane_prolungamento or ''),
    }
    g = candidato.gruppo
    if g:
        ctx.update(numero_gruppo=str(g.numero), data_gruppo=_fmt_data(g.data), ora_gruppo=_fmt_ora(g.ora), luogo_gruppo=g.luogo)
    prima = candidato.colloquio(ch.REC_TIPO_PRIMA)
    seconda = candidato.colloquio(ch.REC_TIPO_SECONDA)
    # Il colloquio "corrente" per le convocazioni: la seconda scelta se esiste
    corrente = seconda or prima
    if corrente:
        ctx.update(
            data_colloquio=_fmt_data(corrente.data), ora_colloquio=_fmt_ora(corrente.ora),
            link_colloquio=corrente.link_meet,
        )
    area = candidato.area_prova or (seconda and (seconda.area_probabile or seconda.area)) \
        or (prima and (prima.area_probabile or prima.area)) or candidato.area_1
    ctx['area'] = area or ''
    return ctx


def render(testo, ctx):
    return _PLACEHOLDER_RE.sub(lambda m: str(ctx.get(m.group(1), m.group(0))), testo or '')


def invia(candidato, tipo, inviata_da=''):
    """Invia (o tenta di inviare) e registra. Ritorna l'EmailCandidato creato."""
    if tipo not in TIPI:
        raise EmailNonInviabile(f'Tipo email sconosciuto: {tipo}')
    ctx = contesto(candidato)
    oggetto_tpl, corpo_tpl = template(candidato.sessione, tipo)
    oggetto = render(oggetto_tpl, ctx).replace('\n', ' ')[:255]
    corpo = render(corpo_tpl, ctx)

    msg = EmailMultiAlternatives(
        subject=oggetto,
        body=corpo,
        from_email=getattr(settings, 'RECRUITMENT_FROM_EMAIL', '') or None,
        to=[candidato.email],
        reply_to=[settings.RECRUITMENT_REPLY_TO] if getattr(settings, 'RECRUITMENT_REPLY_TO', '') else None,
    )
    msg.attach_alternative(linebreaks(urlize(corpo, autoescape=True)), 'text/html')
    ok, errore = True, ''
    try:
        msg.send(fail_silently=False)
    except Exception as exc:  # errore del provider: registrato, non blocca gli altri invii
        ok, errore = False, f'{type(exc).__name__}: {exc}'[:1000]

    return EmailCandidato.objects.create(
        candidato=candidato, tipo=tipo, destinatario=candidato.email,
        oggetto=oggetto, corpo=corpo, inviata_da=inviata_da, ok=ok, errore=errore,
    )


def tipi_inviati(candidato):
    """Tipi email già inviati con successo (usa email_log prefetchato)."""
    return {e.tipo for e in candidato.email_log.all() if e.ok}


# ------------------------------------------------------------
# Quale email spetta al candidato in una fase: (tipo | None, motivo_blocco)
# ------------------------------------------------------------

FASE_SCREENING = 'screening'
FASE_CONVOCAZIONE_GRUPPO = 'convocazione_gruppo'
FASE_ESITO_GRUPPO = 'esito_gruppo'
FASE_ESITO_INDIVIDUALE = 'esito_individuale'
FASE_ESITO_FINALE = 'esito_finale'

FASI_EMAIL = {
    FASE_SCREENING: 'Esiti screening CV',
    FASE_CONVOCAZIONE_GRUPPO: 'Convocazioni colloquio di gruppo',
    FASE_ESITO_GRUPPO: 'Esiti colloquio di gruppo',
    FASE_ESITO_INDIVIDUALE: 'Esiti colloquio individuale',
    FASE_ESITO_FINALE: 'Esiti finali periodo di prova',
}

def email_dovuta(candidato, fase):
    if fase == FASE_SCREENING:
        return {'Passato': ('screening_passato', ''), 'Scartato': ('screening_scartato', '')}.get(
            candidato.esito_screening, (None, ''))

    if fase == FASE_CONVOCAZIONE_GRUPPO:
        g = candidato.gruppo
        if candidato.esito_screening != 'Passato' or g is None:
            return None, ''
        if not (g.data and g.ora and g.luogo):
            return None, 'gruppo senza data/ora/luogo'
        return 'convocazione_gruppo', ''

    if fase == FASE_ESITO_GRUPPO:
        if candidato.esito_gruppo == 'Non ammesso':
            return 'gruppo_non_ammesso', ''
        if candidato.esito_gruppo == 'Ammesso':
            prima = candidato.colloquio(ch.REC_TIPO_PRIMA)
            if not (prima and prima.pianificato):
                return None, 'colloquio individuale non ancora pianificato'
            return 'gruppo_ammesso', ''
        return None, ''

    if fase == FASE_ESITO_INDIVIDUALE:
        prima = candidato.colloquio(ch.REC_TIPO_PRIMA)
        seconda = candidato.colloquio(ch.REC_TIPO_SECONDA)
        decisivo = seconda if seconda and seconda.esito in ('Ammesso', 'Non ammesso') else prima
        if decisivo and decisivo.esito == 'Ammesso':
            return 'individuale_ammesso', ''
        if decisivo and decisivo.esito == 'Non ammesso':
            return 'individuale_non_ammesso', ''
        if prima and prima.esito == 'Seconda scelta':
            if not (seconda and seconda.pianificato):
                return None, 'colloquio di seconda scelta non ancora pianificato'
            return 'seconda_scelta', ''
        return None, ''

    if fase == FASE_ESITO_FINALE:
        return {
            'Ammesso': ('finale_ammesso', ''),
            'Non ammesso': ('finale_non_ammesso', ''),
            'Prolungato': ('finale_prolungato', ''),
        }.get(candidato.esito_finale, (None, ''))

    raise ValueError(fase)


def da_inviare(candidati, fase):
    """[(candidato, tipo)] ancora da inviare + {motivo: n} dei bloccati."""
    pronti, bloccati = [], {}
    for c in candidati:
        tipo, motivo = email_dovuta(c, fase)
        if tipo is None:
            if motivo:
                bloccati[motivo] = bloccati.get(motivo, 0) + 1
            continue
        if tipo in tipi_inviati(c):
            continue
        pronti.append((c, tipo))
    return pronti, bloccati


def invia_in_blocco(coppie, inviata_da, limite=None):
    """Invia rispettando il rate limit del provider. Ritorna (ok, errori, restanti)."""
    limite = limite or getattr(settings, 'RECRUITMENT_EMAIL_BATCH', 40)
    pausa = getattr(settings, 'RECRUITMENT_EMAIL_PAUSE', 0.5)
    ok = errori = 0
    for i, (candidato, tipo) in enumerate(coppie[:limite]):
        if i and pausa:
            time.sleep(pausa)
        if invia(candidato, tipo, inviata_da).ok:
            ok += 1
        else:
            errori += 1
    return ok, errori, max(len(coppie) - limite, 0)
