"""Ruoli JESAP ricavati da SOCI.

Utente Django ↔ socio: `User.email` == `SOCI."EMAIL @jesap"` (stesso legame
usato in registrazione). Solo soci con STATUS 'Associato'.

- CdA: RUOLO contiene uno dei ruoli board. Match per sottostringa perché in
  SOCI esistono ruoli combinati (es. "Vice President and Secretary General").
- Responsabile: RUOLO == 'Head of'.
"""
from .models import Soci

CDA_RUOLI = tuple(sorted(Soci._BOARD_STANDALONE_RUOLI))
RESPONSABILE_RUOLO = 'Head of'

_CACHE_ATTR = '_jesap_socio_cache'


def get_socio(user):
    """Socio associato all'utente (cache per request sull'oggetto user)."""
    if not getattr(user, 'is_authenticated', False):
        return None
    if hasattr(user, _CACHE_ATTR):
        return getattr(user, _CACHE_ATTR)
    email = (user.email or '').strip()
    socio = None
    if email:
        socio = (
            Soci.objects.filter(email_jesap__iexact=email, status__iexact='Associato')
            .order_by('id')
            .first()
        )
    setattr(user, _CACHE_ATTR, socio)
    return socio


def is_cda(socio):
    ruolo = (getattr(socio, 'ruolo', '') or '').lower()
    return bool(ruolo) and any(r.lower() in ruolo for r in CDA_RUOLI)


def is_responsabile(socio):
    ruolo = (getattr(socio, 'ruolo', '') or '').strip().lower()
    return ruolo == RESPONSABILE_RUOLO.lower()


def can_access_credenziali(user):
    socio = get_socio(user)
    return socio is not None and (is_cda(socio) or is_responsabile(socio))


def display_name(user):
    """Nome da salvare in creato_da / modificato_da."""
    socio = get_socio(user)
    if socio and socio.nome_e_cognome:
        return socio.nome_e_cognome
    return user.get_full_name() or user.get_username()


# ============================================================
# RECRUITMENT
# Accesso: CdA + Head of sempre; altri soci solo se autorizzati (gruppo Django
# RECRUITMENT_GROUP). Head of autorizza i soci della propria area, CdA chiunque.
# ============================================================

RECRUITMENT_GROUP = 'Recruitment'


def _is_cda_or_head(socio):
    return socio is not None and (is_cda(socio) or is_responsabile(socio))


def can_access_recruitment(user):
    socio = get_socio(user)
    if socio is None:
        return False
    if _is_cda_or_head(socio):
        return True
    return user.groups.filter(name=RECRUITMENT_GROUP).exists()


def can_manage_recruitment_access(user):
    return _is_cda_or_head(get_socio(user))


def can_authorize_for_recruitment(manager, target_socio):
    """CdA: chiunque. Head of: solo soci della propria area."""
    socio = get_socio(manager)
    if socio is None or target_socio is None:
        return False
    if is_cda(socio):
        return True
    if is_responsabile(socio):
        area = (socio.area_di_appartenenza or '').strip().lower()
        return bool(area) and area == (target_socio.area_di_appartenenza or '').strip().lower()
    return False
