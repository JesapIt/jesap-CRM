import logging
import re as _re
from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.views import PasswordResetConfirmView as DjangoPasswordResetConfirmView
from django.contrib.auth.views import PasswordResetView as DjangoPasswordResetView
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator
from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from . import choices as ch
from .forms import (
    LeadForm,
    LeadPartnershipForm,
    NonFinalizzataForm,
    PartnershipFullForm,
    ProgettoForm,
    CredenzialeForm,
    TaskForm,
)
from . import crypto
from .audit import write_log
from .models import AuditLog, Credenziale, Lead, Partnership, Progetti, Soci, Socio, Task
from .permissions import can_access_credenziali, display_name, get_socio
from .utils.parsing import parse_date_text, parse_money

logger = logging.getLogger(__name__)

# Valori "vuoti" letterali arrivati dal sync Sheets → Supabase
_EMPTY_TEXT_VALUES = ('', 'None', 'null')


# RBAC: Editor = gruppo 'Editori' | staff admin | superuser
def is_editor(user):
    return (
        user.is_authenticated
        and (user.is_superuser or user.is_staff or user.groups.filter(name='Editori').exists())
    )


def _is_admin_user(u):
    return u.is_authenticated and (u.is_staff or u.is_superuser)


def _role_required(check):
    """Anonimo → login; loggato senza permesso → 403 (non un redirect silenzioso)."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return login_required(_wrapped, login_url='login')
    return decorator


editor_required = _role_required(is_editor)
admin_required = _role_required(_is_admin_user)


def _named(field):
    """Esclude righe senza nome (NULL / '' / 'None' letterale dal sync)."""
    return Q(**{f'{field}__isnull': False}) & ~Q(**{f'{field}__in': _EMPTY_TEXT_VALUES})


# ============================================================
# SORTING HELPERS — sort server-side cross-page
# Le date in DB sono salvate come stringhe (DD/MM/YYYY o YYYY-MM-DD).
# `order_by` di Django sui TextField ordina alfabeticamente — sbagliato.
# Soluzione: load full queryset → sort in Python con parser type-aware → paginate.
# ============================================================

SORT_TEXT = 'text'   # ordinamento alfabetico puro (nomi, stati, ...)
SORT_AUTO = 'auto'   # data → numero/importo → testo

_DATE_LIKE = _re.compile(r'^\d{1,4}[/-]\d{1,2}[/-]\d{1,4}$')


def _make_sort_key(value, kind=SORT_AUTO):
    """
    Converte un valore in una chiave sortabile `(rank, valore)`.
    Il rank separa date / numeri / testo → ordine totale anche su colonne miste.
    Ritorna `None` per valori vuoti (sinkati in fondo).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s or s in ("-", "None", "null", "N/A"):
        return None
    if kind == SORT_TEXT:
        return (2, s.lower())

    if _DATE_LIKE.match(s):
        parsed = parse_date_text(s)
        if parsed:
            return (0, parsed.isoformat())

    if _re.search(r'\d', s):
        try:
            amount = parse_money(s)
        except ValueError:
            amount = None
        if amount is not None:
            return (1, amount)

    return (2, s.lower())


def _sort_records(records, sort_key, sort_dir, sort_map, default_sort):
    """
    Ordina lista records in Python.
    sort_map: {sort_key: attrname | callable | (attrname|callable, SORT_TEXT|SORT_AUTO)}
    default_sort: tuple (key, dir) usato se sort_key non valido
    Empty values sinkano sempre in fondo (asc + desc).
    Ritorna (records_sorted, sort_key_effettivo, sort_dir_effettivo).
    """
    if sort_key not in sort_map:
        sort_key, sort_dir = default_sort
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"

    accessor = sort_map[sort_key]
    kind = SORT_AUTO
    if isinstance(accessor, tuple):
        accessor, kind = accessor

    def get_key(obj):
        try:
            val = accessor(obj) if callable(accessor) else getattr(obj, accessor, None)
        except Exception:
            val = None
        return _make_sort_key(val, kind)

    # Chiave calcolata una sola volta per record (non a ogni confronto).
    keyed = [(get_key(r), r) for r in records]
    present = [kr for kr in keyed if kr[0] is not None]
    missing = [r for k, r in keyed if k is None]
    present.sort(key=lambda kr: kr[0], reverse=(sort_dir == "desc"))
    return [r for _, r in present] + missing, sort_key, sort_dir


def _read_sort_params(request, allowed_keys, default_sort):
    """Legge ?sort= e ?dir= dalla query string, valida contro allowed_keys."""
    sort_key = request.GET.get("sort", "").strip()
    sort_dir = request.GET.get("dir", "asc").strip().lower()
    if sort_key not in allowed_keys:
        sort_key = default_sort[0]
        sort_dir = default_sort[1]
    if sort_dir not in ("asc", "desc"):
        sort_dir = "asc"
    return sort_key, sort_dir


def _sorted_page(request, queryset, sort_map, default_sort, per_page=25):
    """Sort server-side cross-page + paginazione. Ritorna (page_obj, all_records, key, dir)."""
    sort_key, sort_dir = _read_sort_params(request, sort_map, default_sort)
    all_records, sort_key, sort_dir = _sort_records(
        list(queryset), sort_key, sort_dir, sort_map, default_sort
    )
    page_obj = Paginator(all_records, per_page).get_page(request.GET.get("page"))
    return page_obj, all_records, sort_key, sort_dir


# --- 1. LOGIN (username o email + password) ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect(reverse("home"))
    if request.method == "POST":
        # Sanitizzazione: trim + lowercase su identificativo
        u = (request.POST.get("username") or "").strip().lower()
        p = request.POST.get("password") or ""

        user = authenticate(request, username=u, password=p) if u and p else None
        # is_active controllato dal backend (user_can_authenticate)
        if user is not None and user.is_active:
            login(request, user)
            return redirect(reverse("home"))

        # Messaggio generico: non rivelare se l'utente esiste o la password è sbagliata
        messages.error(request, "Credenziali non valide.")

    return render(request, "dashboard/login.html")


# --- 2. SUBSCRIBE STEP 1 (Check Database & Send Email) ---
def register_step1(request):
    if request.method == "POST":
        # Sanitizzazione: trim + lowercase
        email = (request.POST.get("email") or "").strip().lower()
        generic_ok = "Se l'email è valida, riceverai un link per completare la registrazione."

        if not email or not Socio.objects.filter(email_jesap__iexact=email).exists():
            # Messaggio generico anti-enumerazione
            messages.success(request, generic_ok)
            return redirect("register_step1")

        if User.objects.filter(email__iexact=email).exists():
            # Messaggio generico per non rivelare se l'account esiste già
            messages.success(request, generic_ok)
            return redirect("register_step1")

        signed_token = signing.TimestampSigner().sign(email)
        verification_link = request.build_absolute_uri(
            reverse("register_step2", args=[signed_token])
        )

        try:
            ctx = {'verification_link': verification_link}
            msg = EmailMultiAlternatives(
                subject="Completa la tua registrazione al Gestionale JESAP",
                body=render_to_string('registration/registration_verify_email.txt', ctx),
                from_email=None,
                to=[email],
            )
            msg.attach_alternative(
                render_to_string('registration/registration_verify_email.html', ctx), 'text/html',
            )
            msg.send(fail_silently=False)
        except Exception:
            logger.exception("Invio email di registrazione fallito")
            messages.error(
                request,
                "Errore tecnico con il server di posta. Riprova più tardi o contatta l'amministratore.",
            )
            return redirect("register_step1")

        messages.success(
            request,
            "Ti abbiamo inviato un'email! Controlla la casella di posta per impostare la password.",
        )
        return redirect("register_step1")

    return render(request, "dashboard/register_step1.html")


# --- 3. SUBSCRIBE STEP 2 (Double Password & Create Account) ---
def register_step2(request, token):
    try:
        email = signing.TimestampSigner().unsign(token, max_age=86400)  # Scade dopo 24h
    except (signing.SignatureExpired, signing.BadSignature):
        messages.error(request, "Link non valido o scaduto.")
        return redirect("register_step1")

    email_clean = email.strip().lower()
    # Email già validata in step1 (formato nome.cognome@jesap.it firmato).
    short_username = email_clean.split("@", 1)[0]
    ctx = {"email": email}

    if request.method == "POST":
        password = request.POST.get("password") or ""
        password_confirm = request.POST.get("password_confirm") or ""

        if not password or password != password_confirm:
            messages.error(request, "Le password non coincidono.")
            return render(request, "dashboard/register_step2.html", ctx)

        if (User.objects.filter(username__iexact=short_username).exists()
                or User.objects.filter(email__iexact=email_clean).exists()):
            messages.error(
                request,
                "Esiste già un account per questa email. Accedi o usa «Password dimenticata».",
            )
            return render(request, "dashboard/register_step2.html", ctx)

        try:
            # Stessi validatori di AUTH_PASSWORD_VALIDATORS (lunghezza, comuni, numeriche, ...)
            validate_password(password, user=User(username=short_username, email=email_clean))
        except ValidationError as exc:
            for err in exc.messages:
                messages.error(request, err)
            return render(request, "dashboard/register_step2.html", ctx)

        User.objects.create_user(username=short_username, email=email_clean, password=password)
        messages.success(request, f"Account creato! Il tuo username è: {short_username}")
        return redirect("login")

    return render(request, "dashboard/register_step2.html", ctx)


# --- PASSWORD RESET (Custom with email error handling) ---
class CustomPasswordResetView(DjangoPasswordResetView):
    """Password reset con error handling. Email via Resend HTTP API (no SMTP)."""

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Email sending failed in password reset: {type(e).__name__}: {e}")
            messages.error(
                self.request,
                "Errore durante l'invio della email. Riprova più tardi o contatta l'amministratore.",
            )
            return self.form_invalid(form)


class CustomPasswordResetConfirmView(DjangoPasswordResetConfirmView):
    """Password reset confirm with graceful error handling."""

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except Exception as e:
            logger.error(f"Password reset error: {type(e).__name__}: {e}")
            messages.error(
                self.request,
                "Errore durante il reset della password. Riprova più tardi.",
            )
            return self.form_invalid(form)


# --- DASHBOARD VIEWS ---
@login_required(login_url="login")
def home(request):
    return render(request, "dashboard/home.html")


# Sort map per Leads
LEADS_SORT_MAP = {
    "lead_id": "lead_id",
    "azienda": ("azienda", SORT_TEXT),
    "referente": ("referente", SORT_TEXT),
    "owner": ("owner", SORT_TEXT),
    "fase": ("fase_attuale", SORT_TEXT),
    "stato": ("stato_lead", SORT_TEXT),
    "contratto": ("stato_contratto", SORT_TEXT),
    "priorita": ("priorita", SORT_TEXT),
    "valore_stimato": "valore_stimato",
    "valore_ponderato": "valore_ponderato",
    "probabilita": "probabilita",
    "data_creazione": "data_creazione",
    "data_primo_contatto": "data_primo_contatto",
    "data_prossima_azione": "data_prossima_azione",
}
LEADS_SORT_DEFAULT = ("data_creazione", "desc")


@login_required(login_url="login")
def leads(request):
    """
    BD Lead Control — lista pipeline con filtri e sort server-side cross-page.

    Query params supportati:
      ?q=...                 ricerca su azienda / referente / email
      ?fase=Nuovo            filtro fase pipeline
      ?stato=Attiva          filtro stato lead
      ?owner=...             filtro PM assegnato
      ?alert=1               solo lead con follow-up scaduto
      ?sort=key&dir=asc|desc ordinamento server-side
      ?page=N                paginazione
    """
    search_query = request.GET.get("q", "").strip()
    fase_filter = request.GET.get("fase", "").strip()
    stato_filter = request.GET.get("stato", "").strip()
    owner_filter = request.GET.get("owner", "").strip()
    alert_only = request.GET.get("alert", "") == "1"

    queryset = Lead.objects.all()

    if search_query:
        queryset = queryset.filter(
            Q(azienda__icontains=search_query)
            | Q(referente__icontains=search_query)
            | Q(nome_referente__icontains=search_query)
            | Q(cognome_referente__icontains=search_query)
            | Q(email_referente__icontains=search_query)
            | Q(lead_id__icontains=search_query)
        )

    if fase_filter:
        queryset = queryset.filter(fase_attuale__iexact=fase_filter)
    if stato_filter:
        queryset = queryset.filter(stato_lead__iexact=stato_filter)
    if owner_filter:
        queryset = queryset.filter(owner__icontains=owner_filter)
    if alert_only:
        queryset = queryset.filter(alert_follow_up=True)

    page_obj, all_records, sort_key, sort_dir = _sorted_page(
        request, queryset, LEADS_SORT_MAP, LEADS_SORT_DEFAULT
    )

    # KPI rapidi sopra la tabella (sull'intero dataset filtrato, non sulla pagina)
    kpi = {
        "total": len(all_records),
        "attive": sum(1 for l in all_records if (l.stato_lead or "").lower() == "attiva"),
        "vinte": sum(1 for l in all_records if (l.stato_lead or "").lower() == "vinta"),
        "alert": sum(1 for l in all_records if l.alert_follow_up),
        "valore_ponderato_tot": sum(
            (l.valore_ponderato or 0) for l in all_records
        ),
    }

    return render(request, "dashboard/leads.html", {
        "leads": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "fase_filter": fase_filter,
        "stato_filter": stato_filter,
        "owner_filter": owner_filter,
        "alert_only": alert_only,
        "current_sort": sort_key,
        "current_dir": sort_dir,
        "kpi": kpi,
        "fasi": ch.LEAD_FASE_VALUES,
        "stati": ch.LEAD_STATO_VALUES,
        "is_editor": is_editor(request.user),
    })


# ============================================================
# LEAD CRUD (Editor-only)
# ============================================================
@editor_required
def lead_create(request):
    if request.method == 'POST':
        form = LeadForm(request.POST)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                logger.exception("Creazione lead fallita")
                form.add_error(None, "Impossibile salvare la lead. Riprova tra qualche secondo.")
            else:
                messages.success(request, "Lead creata con successo!")
                return redirect('leads')
    else:
        form = LeadForm()
    return render(request, 'dashboard/lead_form.html', {
        'form': form, 'azione': 'Nuova',
    })


@editor_required
def lead_update(request, pk):
    lead = get_object_or_404(Lead, lead_id=pk)
    if request.method == 'POST':
        form = LeadForm(request.POST, instance=lead)
        if form.is_valid():
            form.save()
            messages.success(request, "Lead aggiornata con successo!")
            return redirect('leads')
    else:
        form = LeadForm(instance=lead)
    return render(request, 'dashboard/lead_form.html', {
        'form': form, 'azione': 'Modifica', 'lead': lead,
    })


@editor_required
def lead_delete(request, pk):
    lead = get_object_or_404(Lead, lead_id=pk)
    if request.method == 'POST':
        lead.delete()
        messages.success(request, "Lead eliminata con successo!")
        return redirect('leads')
    return render(request, 'dashboard/lead_confirm_delete.html', {'lead': lead})


# Sort map per Partnership (tab "partnership")
PARTNERSHIP_SORT_MAP = {
    "id": "id_codice",
    "nome": ("partnership", SORT_TEXT),
    "status": ("status_partnership", SORT_TEXT),
    "data_firma": "data_firma",
    "anno": "anno",
}
PARTNERSHIP_SORT_DEFAULT = ("nome", "asc")

# Sort map per Partnership tab "non_finalizzate" e "lead"
PARTNERSHIP_NF_SORT_MAP = {
    "nome": ("partnership", SORT_TEXT),
    "realta": ("partnership", SORT_TEXT),
    "contatti": ("contatti", SORT_TEXT),
    "data_firma": "data_firma",
    "anno": "anno",
}
PARTNERSHIP_NF_SORT_DEFAULT = ("nome", "asc")


@login_required(login_url="login")
def partnerships(request):
    tab = request.GET.get("tab", "partnership")
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    context = {
        "current_tab": tab,
        "search_query": search_query,
        "status_filter": status_filter,
        "is_editor": is_editor(request.user),
    }

    if tab == "partnership":
        queryset = Partnership.objects.filter(
            status_partnership__in=Partnership.STATUS_PARTNERSHIP_TAB
        )
        context["stati_partnership"] = list(Partnership.STATUS_PARTNERSHIP_TAB)

        if search_query:
            queryset = queryset.filter(
                Q(partnership__icontains=search_query) |
                Q(contatti__icontains=search_query) |
                Q(id_codice__icontains=search_query)
            )
        if status_filter:
            queryset = queryset.filter(status_partnership=status_filter)
        sort_map, sort_default, context_key = PARTNERSHIP_SORT_MAP, PARTNERSHIP_SORT_DEFAULT, "partnerships"

    elif tab == "non_finalizzate":
        queryset = Partnership.objects.filter(
            status_partnership__iexact=Partnership.STATUS_NON_FINALIZZATA
        )
        if search_query:
            queryset = queryset.filter(
                Q(partnership__icontains=search_query) |
                Q(contatti__icontains=search_query)
            )
        sort_map, sort_default, context_key = PARTNERSHIP_NF_SORT_MAP, PARTNERSHIP_NF_SORT_DEFAULT, "non_finalizzate"

    elif tab == "lead":
        queryset = Partnership.objects.filter(
            status_partnership__iexact=Partnership.STATUS_TRATTATIVA
        )
        if search_query:
            queryset = queryset.filter(partnership__icontains=search_query)
        sort_map, sort_default, context_key = PARTNERSHIP_NF_SORT_MAP, PARTNERSHIP_NF_SORT_DEFAULT, "leads"

    else:
        context["dati_tabella"] = []
        return render(request, "dashboard/partnerships.html", context)

    page_obj, _, sort_key, sort_dir = _sorted_page(request, queryset, sort_map, sort_default)
    context.update({
        context_key: page_obj,
        "dati_tabella": page_obj,
        "page_obj": page_obj,
        "current_sort": sort_key,
        "current_dir": sort_dir,
    })
    return render(request, "dashboard/partnerships.html", context)


# Sort map per Progetti: chiave URL → attrname o lambda
PROGETTI_SORT_MAP = {
    "progetto": ("nome_progetto", SORT_TEXT),
    "stato": ("stato", SORT_TEXT),
    "pm": ("pm", SORT_TEXT),
    "provenienza": ("provenienza", SORT_TEXT),
    "data_inizio": "data_inizio",
    "data_fine": "data_fine_contratto",
    "fatturato": "fatturato_senza_iva_field",
}
PROGETTI_SORT_DEFAULT = ("progetto", "asc")


@login_required(login_url="login")
def progetti(request):
    search_query = request.GET.get("q", "").strip()
    stato_filter = request.GET.get("stato", "").strip()

    # Righe senza nome = residui del foglio: escluse qui, non nel template,
    # così paginazione e stato vuoto restano coerenti.
    queryset = Progetti.objects.filter(_named("nome_progetto"))

    if search_query:
        queryset = queryset.filter(
            Q(nome_progetto__icontains=search_query)
            | Q(pm__icontains=search_query)
            | Q(cliente__icontains=search_query)
        )

    if stato_filter:
        queryset = queryset.filter(stato=stato_filter)

    page_obj, _, sort_key, sort_dir = _sorted_page(
        request, queryset, PROGETTI_SORT_MAP, PROGETTI_SORT_DEFAULT
    )

    return render(request, "dashboard/progetti.html", {
        "progetti": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "stato_filter": stato_filter,
        "stati": ch.STATO_PROGETTO_VALUES,
        "is_editor": is_editor(request.user),
        "current_sort": sort_key,
        "current_dir": sort_dir,
    })


@editor_required
def progetto_create(request):
    if request.method == 'POST':
        form = ProgettoForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
            except IntegrityError:
                # Codice generato già preso (creazione concorrente): nessuna sovrascrittura.
                logger.warning("Collisione CODICE PROGETTO in creazione", exc_info=True)
                form.add_error(None, "Codice progetto già esistente. Riprova a salvare.")
            else:
                messages.success(request, "Progetto creato con successo!")
                return redirect('progetti')
    else:
        form = ProgettoForm()

    return render(request, 'dashboard/progetto_form.html', {'form': form, 'azione': 'Nuovo'})


@editor_required
def progetto_update(request, pk):
    progetto = get_object_or_404(Progetti, codice_progetto=pk)

    if request.method == 'POST':
        form = ProgettoForm(request.POST, instance=progetto)
        if form.is_valid():
            form.save()
            messages.success(request, "Progetto aggiornato con successo!")
            return redirect('progetti')
    else:
        form = ProgettoForm(instance=progetto)

    return render(request, 'dashboard/progetto_form.html', {'form': form, 'azione': 'Modifica'})


@editor_required
def progetto_delete(request, pk):
    progetto = get_object_or_404(Progetti, codice_progetto=pk)

    if request.method == 'POST':
        progetto.delete()
        messages.success(request, "Progetto eliminato con successo!")
        return redirect('progetti')

    return render(request, 'dashboard/progetto_confirm_delete.html', {'progetto': progetto})


# Sort map per Soci
SOCI_SORT_MAP = {
    "nome": ("nome_e_cognome", SORT_TEXT),
    "ruolo": ("ruolo", SORT_TEXT),
    "area": ("area_di_appartenenza", SORT_TEXT),
}
SOCI_SORT_DEFAULT = ("nome", "asc")

SOCI_AREA_TABS = {
    "da": "D&A",
    "bd": "BD",
    "hr": "HR",
    "mc": "M&C",
}

# Ruoli Board: valori ufficiali (EN, vedi Soci.Ruolo) + legacy IT dal foglio.
_BOARD_ROLE_FRAGMENTS = (
    "board", "president", "segretari", "secretary", "tesorier", "treasurer",
    "international manager",
)


def _board_filter():
    q = Q(area_di_appartenenza__iexact="Board") | Q(ruolo_esteso__icontains="board")
    for fragment in _BOARD_ROLE_FRAGMENTS:
        q |= Q(ruolo__icontains=fragment)
    return q


@login_required(login_url="login")
def soci(request):
    tab = request.GET.get("tab", "da")
    search_query = request.GET.get("q", "").strip()
    user_is_admin = _is_admin_user(request.user)

    # Tab sconosciute (o admin per non-admin) → default
    valid_tabs = set(SOCI_AREA_TABS) | {"board"}
    if user_is_admin:
        valid_tabs.add("admin")
    if tab not in valid_tabs:
        tab = "da"

    context = {
        "current_tab": tab,
        "search_query": search_query,
        "is_admin_tab": tab == "admin",
        "is_editor": is_editor(request.user),
    }

    if tab == "admin":
        admin_users = User.objects.filter(Q(is_staff=True) | Q(is_superuser=True))
        if search_query:
            admin_users = admin_users.filter(
                Q(username__icontains=search_query)
                | Q(email__icontains=search_query)
                | Q(first_name__icontains=search_query)
                | Q(last_name__icontains=search_query)
            )
        context["admin_users"] = admin_users.order_by("username")
        context["non_admin_users"] = User.objects.filter(
            is_staff=False, is_superuser=False,
        ).order_by("username")
        context["can_manage_admins"] = True
        context["soci_list"] = []
        return render(request, "dashboard/soci.html", context)

    # Base filter: only active members
    queryset = Soci.objects.filter(status__iexact="Associato").filter(_named("nome_e_cognome"))

    if tab == "board":
        queryset = queryset.filter(_board_filter())
    else:
        queryset = queryset.filter(area_di_appartenenza__iexact=SOCI_AREA_TABS[tab])

    if search_query:
        queryset = queryset.filter(
            Q(nome_e_cognome__icontains=search_query)
            | Q(ruolo__icontains=search_query)
            | Q(email_jesap__icontains=search_query)
        )

    page_obj, _, sort_key, sort_dir = _sorted_page(
        request, queryset, SOCI_SORT_MAP, SOCI_SORT_DEFAULT
    )
    context.update({
        "soci_list": page_obj,
        "page_obj": page_obj,
        "current_sort": sort_key,
        "current_dir": sort_dir,
    })
    return render(request, "dashboard/soci.html", context)


def _target_user(request):
    """Utente da POST user_id; None se id mancante/non numerico/inesistente."""
    user_id = (request.POST.get("user_id") or "").strip()
    if not user_id.isdigit():
        return None
    return User.objects.filter(pk=int(user_id)).first()


@require_POST
@admin_required
def admin_promote(request):
    target = _target_user(request)
    if target is None:
        messages.error(request, "Utente non trovato.")
    else:
        target.is_staff = True
        target.save(update_fields=["is_staff"])
        messages.success(request, f"{target.username} promosso ad admin.")
    return redirect(reverse("soci") + "?tab=admin")


@require_POST
@admin_required
def admin_demote(request):
    target = _target_user(request)
    if target is None:
        messages.error(request, "Utente non trovato.")
    elif target == request.user:
        messages.error(request, "Non puoi rimuovere te stesso.")
    elif target.is_superuser and not request.user.is_superuser:
        # Solo un superuser può rimuovere un altro superuser.
        messages.error(request, "Non puoi rimuovere un superuser.")
    else:
        target.is_staff = False
        if request.user.is_superuser:
            target.is_superuser = False
            target.save(update_fields=["is_staff", "is_superuser"])
        else:
            target.save(update_fields=["is_staff"])
        messages.success(request, f"{target.username} rimosso dagli admin.")
    return redirect(reverse("soci") + "?tab=admin")


_KIND_TO_FORM = {
    Partnership.KIND_FULL:    PartnershipFullForm,
    Partnership.KIND_LEAD:    LeadPartnershipForm,
    Partnership.KIND_NON_FIN: NonFinalizzataForm,
}

# Layout del form partnership: ogni kind mostra solo i campi che possiede.
PARTNERSHIP_FORM_SECTIONS = (
    ('Identificazione', ('partnership', 'id_codice', 'tipologia', 'oggetto_primario', 'status_partnership')),
    ('Date e durata', ('data_firma', 'anno', 'durata', 'rinnovo', 'data_ultimo_rinnovo', 'data_fine_prevista')),
    ('Numeri', ('numero_progetti', 'numero_partecipanti')),
    ('Contatti & Drive', ('contatti', 'cartella_sul_drive', 'url_cartella')),
    ('Vantaggi & Compenso', ('vantaggi_partner', 'compenso_economico')),
)


def _form_sections(form, layout):
    sections = []
    for title, names in layout:
        fields = [form[name] for name in names if name in form.fields]
        if fields:
            sections.append((title, fields))
    return sections


def _kind_for_status(status):
    status = (status or '').strip()
    if status == Partnership.STATUS_TRATTATIVA:
        return Partnership.KIND_LEAD
    if status == Partnership.STATUS_NON_FINALIZZATA:
        return Partnership.KIND_NON_FIN
    return Partnership.KIND_FULL


def _redirect_to_tab(kind):
    tab = Partnership.KIND_TO_TAB.get(kind, 'partnership')
    return redirect(reverse('partnerships') + f'?tab={tab}')


def _render_partnership_form(request, form, azione, kind):
    return render(request, 'dashboard/partnership_form.html', {
        'form': form,
        'azione': azione,
        'kind': kind,
        'sections': _form_sections(form, PARTNERSHIP_FORM_SECTIONS),
    })


@editor_required
def partnership_create(request, kind=Partnership.KIND_FULL):
    if kind not in _KIND_TO_FORM:
        kind = Partnership.KIND_FULL
    FormClass = _KIND_TO_FORM[kind]

    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Partnership creata con successo!")
            # Per le full la tab dipende dallo status scelto
            return _redirect_to_tab(_kind_for_status(obj.status_partnership))
    else:
        form = FormClass()

    azione_map = {
        Partnership.KIND_FULL:    'Nuova Partnership',
        Partnership.KIND_LEAD:    'Nuovo Lead',
        Partnership.KIND_NON_FIN: 'Nuova Non Finalizzata',
    }
    return _render_partnership_form(request, form, azione_map[kind], kind)


@editor_required
def partnership_update(request, pk):
    partnership = get_object_or_404(Partnership, partnership=pk)

    # Scegli il form in base allo status corrente
    kind = _kind_for_status(partnership.status_partnership)
    FormClass = _KIND_TO_FORM[kind]

    if request.method == 'POST':
        form = FormClass(request.POST, instance=partnership)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Partnership aggiornata con successo!")
            return _redirect_to_tab(_kind_for_status(obj.status_partnership))
    else:
        form = FormClass(instance=partnership)

    return _render_partnership_form(request, form, 'Modifica', kind)


@editor_required
def partnership_delete(request, pk):
    partnership = get_object_or_404(Partnership, partnership=pk)

    if request.method == 'POST':
        kind = _kind_for_status(partnership.status_partnership)
        partnership.delete()
        messages.success(request, "Partnership eliminata con successo!")
        return _redirect_to_tab(kind)

    return render(request, 'dashboard/partnership_confirm_delete.html', {'partnership': partnership})


@require_POST
@editor_required
def partnership_change_status(request, pk):
    """POST-only: sposta una Partnership in un altro tab cambiando lo status."""
    partnership = get_object_or_404(Partnership, partnership=pk)
    new_status = (request.POST.get('status') or '').strip()

    if new_status not in dict(Partnership.STATUS_CHOICES):
        messages.error(request, "Status non valido.")
        return redirect('partnerships')

    partnership.status_partnership = new_status
    partnership.save(update_fields=['status_partnership'])
    messages.success(request, f"Spostata in '{new_status}'.")
    return _redirect_to_tab(_kind_for_status(new_status))


# ============================================================
# TASK — tutti i soci loggati vedono e modificano tutto
# ============================================================

TASK_AREA_TABS = {
    "da": "D&A",
    "bd": "BD",
    "hr": "HR",
    "mc": "M&C",
}
TASK_AREA_TO_TAB = {v: k for k, v in TASK_AREA_TABS.items()}
TASK_TAB_MIE = "mie"
TASK_STATO_APERTE = "aperte"

_TASK_PRIORITA_RANK = {v: i for i, v in enumerate(ch.TASK_PRIORITA_VALUES)}
_TASK_STATO_RANK = {v: i for i, v in enumerate(ch.TASK_STATO_VALUES)}

TASKS_SORT_MAP = {
    "scadenza": "scadenza",
    "titolo": "titolo",
    "priorita": lambda t: _TASK_PRIORITA_RANK.get(t.priorita),
    "stato": lambda t: _TASK_STATO_RANK.get(t.stato),
    "creato_il": "creato_il",
    "modificato_il": "modificato_il",
}
TASKS_SORT_DEFAULT = ("scadenza", "asc")


def _tasks_url(area=None):
    tab = TASK_AREA_TO_TAB.get(area, "")
    return reverse("tasks") + (f"?tab={tab}" if tab else "")


def _safe_next(request, fallback):
    nxt = request.POST.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


@login_required(login_url="login")
def tasks(request):
    """
    Task per area. Query params:
      ?tab=mie|da|bd|hr|mc   (default: mie se l'utente è collegato a un socio)
      ?q=...                 ricerca titolo / descrizione / competenza / assegnatari
      ?stato=aperte|<stato>  default 'aperte' (esclude le completate); vuoto = tutte
      ?scadute=1             solo scadute
      ?sort=key&dir=asc|desc
    """
    socio = get_socio(request.user)
    default_tab = TASK_TAB_MIE if socio else "da"
    tab = request.GET.get("tab") or default_tab
    if tab != TASK_TAB_MIE and tab not in TASK_AREA_TABS:
        tab = default_tab

    search_query = request.GET.get("q", "").strip()
    stato_filter = request.GET.get("stato", TASK_STATO_APERTE).strip()
    scadute_only = request.GET.get("scadute", "") == "1"

    queryset = Task.objects.prefetch_related("assegnatari")
    if tab == TASK_TAB_MIE:
        queryset = queryset.filter(assegnatari=socio) if socio else queryset.none()
    else:
        queryset = queryset.filter(area=TASK_AREA_TABS[tab])

    if search_query:
        queryset = queryset.filter(
            Q(titolo__icontains=search_query)
            | Q(descrizione__icontains=search_query)
            | Q(competenza__icontains=search_query)
            | Q(altri_assegnatari__icontains=search_query)
            | Q(assegnatari__nome_e_cognome__icontains=search_query)
        ).distinct()

    all_records = list(queryset)

    # KPI sul tab corrente (prima dei filtri stato/scadute)
    kpi = {
        "da_iniziare": sum(1 for t in all_records if t.stato == ch.TASK_STATO_DA_INIZIARE),
        "in_corso": sum(1 for t in all_records if t.stato == ch.TASK_STATO_IN_CORSO),
        "scadute": sum(1 for t in all_records if t.scaduta),
        "completate": sum(1 for t in all_records if t.is_completata),
    }

    if stato_filter == TASK_STATO_APERTE:
        all_records = [t for t in all_records if not t.is_completata]
    elif stato_filter in ch.TASK_STATO_VALUES:
        all_records = [t for t in all_records if t.stato == stato_filter]
    else:
        stato_filter = ""
    if scadute_only:
        all_records = [t for t in all_records if t.scaduta]

    sort_key, sort_dir = _read_sort_params(request, TASKS_SORT_MAP, TASKS_SORT_DEFAULT)
    all_records, sort_key, sort_dir = _sort_records(
        all_records, sort_key, sort_dir, TASKS_SORT_MAP, TASKS_SORT_DEFAULT
    )

    paginator = Paginator(all_records, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "dashboard/tasks.html", {
        "tasks": page_obj,
        "page_obj": page_obj,
        "current_tab": tab,
        "area_tabs": TASK_AREA_TABS,
        "current_area": TASK_AREA_TABS.get(tab, ""),
        "has_socio": socio is not None,
        "search_query": search_query,
        "stato_filter": stato_filter,
        "scadute_only": scadute_only,
        "stati": ch.TASK_STATO_VALUES,
        "current_sort": sort_key,
        "current_dir": sort_dir,
        "kpi": kpi,
    })


def _competenze_suggerite():
    valori = set()
    for raw in Task.objects.exclude(competenza="").values_list("competenza", flat=True):
        valori.update(c.strip() for c in raw.split(",") if c.strip())
    return sorted(valori, key=str.lower)


@login_required(login_url="login")
def task_create(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.creato_da = task.modificato_da = display_name(request.user)
            task.save()
            form.save_m2m()
            messages.success(request, "Task creata con successo!")
            return redirect(_tasks_url(task.area))
    else:
        area = TASK_AREA_TABS.get(request.GET.get("tab", ""))
        socio = get_socio(request.user)
        form = TaskForm(initial={
            "area": area or (socio.area_di_appartenenza if socio else ""),
            "stato": ch.TASK_STATO_DA_INIZIARE,
        })

    return render(request, "dashboard/task_form.html", {
        "form": form,
        "azione": "Nuova",
        "competenze_suggerite": _competenze_suggerite(),
    })


@login_required(login_url="login")
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            task = form.save(commit=False)
            task.modificato_da = display_name(request.user)
            task.save()
            form.save_m2m()
            messages.success(request, "Task aggiornata con successo!")
            return redirect(_tasks_url(task.area))
    else:
        form = TaskForm(instance=task)

    return render(request, "dashboard/task_form.html", {
        "form": form,
        "azione": "Modifica",
        "task": task,
        "competenze_suggerite": _competenze_suggerite(),
    })


@login_required(login_url="login")
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        area = task.area
        task.delete()
        messages.success(request, "Task eliminata con successo!")
        return redirect(_tasks_url(area))

    return render(request, "dashboard/task_confirm_delete.html", {"task": task})


@login_required(login_url="login")
@require_POST
def task_set_stato(request, pk):
    """Cambio stato rapido dalla lista."""
    task = get_object_or_404(Task, pk=pk)
    nuovo = (request.POST.get("stato") or "").strip()
    if nuovo not in ch.TASK_STATO_VALUES:
        messages.error(request, "Stato non valido.")
    elif nuovo != task.stato:
        task.stato = nuovo
        task.modificato_da = display_name(request.user)
        task.save(update_fields=["stato", "modificato_da", "modificato_il"])
        messages.success(request, f"'{task.titolo}' → {nuovo}.")
    return redirect(_safe_next(request, _tasks_url(task.area)))


# ============================================================
# CREDENZIALI — solo CdA + responsabili (dashboard/permissions.py)
# ============================================================

CREDENZIALI_AREA_TABS = {
    "generale": "Generale",
    "da": "D&A",
    "bd": "BD",
    "hr": "HR",
    "mc": "M&C",
}
CREDENZIALI_TAB_TUTTE = "tutte"


def credenziali_access_required(view):
    """Login + ruolo CdA/responsabile. 403 per gli altri. Mai in cache."""
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not can_access_credenziali(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return never_cache(login_required(_wrapped, login_url="login"))


def _credenziali_url(area=None):
    tab = next((k for k, v in CREDENZIALI_AREA_TABS.items() if v == area), "")
    return reverse("credenziali") + (f"?tab={tab}" if tab else "")


@credenziali_access_required
def credenziali(request):
    tab = request.GET.get("tab", CREDENZIALI_TAB_TUTTE)
    if tab != CREDENZIALI_TAB_TUTTE and tab not in CREDENZIALI_AREA_TABS:
        tab = CREDENZIALI_TAB_TUTTE
    search_query = request.GET.get("q", "").strip()

    queryset = Credenziale.objects.all()
    if tab in CREDENZIALI_AREA_TABS:
        queryset = queryset.filter(area=CREDENZIALI_AREA_TABS[tab])
    if search_query:
        queryset = queryset.filter(
            Q(servizio__icontains=search_query)
            | Q(username__icontains=search_query)
            | Q(url__icontains=search_query)
        )
    queryset = queryset.order_by("area", "servizio", "id")

    paginator = Paginator(queryset, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "dashboard/credenziali.html", {
        "credenziali": page_obj,
        "page_obj": page_obj,
        "current_tab": tab,
        "area_tabs": CREDENZIALI_AREA_TABS,
        "search_query": search_query,
        "crypto_ok": crypto.is_configured(),
    })


def _crypto_guard(request):
    if crypto.is_configured():
        return None
    messages.error(request, "Chiave di cifratura non configurata (CREDENTIALS_ENCRYPTION_KEY). Contatta l'admin.")
    return redirect("credenziali")


@credenziali_access_required
def credenziale_create(request):
    blocked = _crypto_guard(request)
    if blocked:
        return blocked

    if request.method == "POST":
        form = CredenzialeForm(request.POST)
        if form.is_valid():
            cred = form.save(commit=False)
            cred.modificato_da = display_name(request.user)
            cred.save()
            messages.success(request, "Credenziale salvata.")
            return redirect(_credenziali_url(cred.area))
    else:
        tab_area = CREDENZIALI_AREA_TABS.get(request.GET.get("tab", ""))
        form = CredenzialeForm(initial={"area": tab_area or ""})

    return render(request, "dashboard/credenziale_form.html", {"form": form, "azione": "Nuova"})


@credenziali_access_required
def credenziale_update(request, pk):
    blocked = _crypto_guard(request)
    if blocked:
        return blocked
    cred = get_object_or_404(Credenziale, pk=pk)

    if request.method == "POST":
        form = CredenzialeForm(request.POST, instance=cred)
        if form.is_valid():
            cred = form.save(commit=False)
            cred.modificato_da = display_name(request.user)
            cred.save()
            messages.success(request, "Credenziale aggiornata.")
            return redirect(_credenziali_url(cred.area))
    else:
        form = CredenzialeForm(instance=cred)

    return render(request, "dashboard/credenziale_form.html", {"form": form, "azione": "Modifica", "cred": cred})


@credenziali_access_required
def credenziale_delete(request, pk):
    cred = get_object_or_404(Credenziale, pk=pk)

    if request.method == "POST":
        area = cred.area
        cred.delete()
        messages.success(request, "Credenziale eliminata.")
        return redirect(_credenziali_url(area))

    return render(request, "dashboard/credenziale_confirm_delete.html", {"cred": cred})


@credenziali_access_required
@require_POST
def credenziale_reveal(request, pk):
    """Restituisce password + note in chiaro (JSON) e traccia chi le ha viste."""
    cred = get_object_or_404(Credenziale, pk=pk)
    try:
        payload = {"password": cred.password, "note": cred.note}
    except crypto.CryptoNotConfigured:
        return JsonResponse({"error": "Chiave di cifratura non configurata."}, status=503)
    except crypto.InvalidToken:
        logger.error("Credenziale %s: token non decifrabile con la chiave attuale", cred.pk)
        return JsonResponse({"error": "Impossibile decifrare: chiave errata."}, status=500)
    write_log(cred, AuditLog.ACTION_VIEW)
    return JsonResponse(payload)


@require_GET
def healthz(request):
    """Healthcheck per Railway. Verifica DB raggiungibile."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:
        # Dettagli (host DB, credenziali nei messaggi driver) solo nei log, mai in risposta pubblica.
        logger.exception("Healthcheck DB fallito")
        return JsonResponse({"status": "error"}, status=503)
