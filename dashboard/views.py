from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from urllib.parse import urlencode

# These are for generating secure email links
from django.core.mail import send_mail
from django.core import signing
from .models import Eventi, Formazioni, Progetti, Soci, Socio, Partnership
from django.conf import settings

# --- 1. LOGIN (username o email + password) ---
def login_view(request):
    if request.method == "POST":
        u = (request.POST.get("username") or "").strip()
        p = request.POST.get("password")

        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect(reverse("home"))

        messages.error(request, "Username o password errati.")

    return render(request, "dashboard/login.html")


# --- 2. SUBSCRIBE STEP 1 (Check Database & Send Email) ---
def register_step1(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()

        if Socio.objects.filter(email_jesap__iexact=email).exists():
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "Questo account è già stato registrato. Vai al Login.")
                return redirect("login")

            # Creazione Token Sicuro
            signer = signing.TimestampSigner()
            signed_token = signer.sign(email) 
            verification_link = request.build_absolute_uri(f"/register/step2/{signed_token}/")

            try:
                send_mail(
                    subject="Completa la tua registrazione al CRM JESAP",
                    message=f"Ciao! Clicca su questo link per impostare la tua password:\n\n{verification_link}",
                    from_email=None,  # Django userà in automatico settings.DEFAULT_FROM_EMAIL
                    recipient_list=[email],
                    fail_silently=False,
                )
                
                messages.success(
                    request,
                    "Ti abbiamo inviato un'email! Controlla la casella di posta (o il terminale) per impostare la password.",
                )
                return redirect("register_step1")

            except Exception as e:
                # Se la mail fallisce, logga l'errore nel terminale senza far crashare la pagina
                print(f"❌ ERRORE INVIO EMAIL: {e}")
                messages.error(
                    request,
                    "Errore tecnico con il server di posta. Riprova più tardi o contatta l'amministratore.",
                )
                return redirect("register_step1")

        messages.error(request, "Accesso negato. Questa email non è presente nel database dell'associazione.")
        return redirect("register_step1")

    return render(request, "dashboard/register_step1.html")


# --- 3. SUBSCRIBE STEP 2 (Double Password & Create Account) ---
def register_step2(request, token):
    signer = signing.TimestampSigner()
    
    try:
        email = signer.unsign(token, max_age=86400) # Scade dopo 24h
    except (signing.SignatureExpired, signing.BadSignature):
        messages.error(request, "Link non valido o scaduto.")
        return redirect("register_step1")

    if request.method == "POST":
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")

        if password != password_confirm:
            messages.error(request, "Le password non coincidono.")
        elif len(password) < 8:
            messages.error(request, "La password deve essere di almeno 8 caratteri.")
        else:
            email_clean = email.strip().lower()
            if email_clean.count("@") != 1:
                messages.error(request, "Indirizzo email non valido.")
                return render(request, "dashboard/register_step2.html", {"email": email})

            local_part, domain = email_clean.split("@", 1)
            local_part = local_part.strip()
            domain = domain.strip()
            
            if not local_part or not domain:
                messages.error(request, "Indirizzo email non valido.")
                return render(request, "dashboard/register_step2.html", {"email": email})

            # Username = solo la parte locale (es. mario.rossi), mai l'intera email
            short_username = local_part.lower()

            if User.objects.filter(username__iexact=short_username).exists():
                messages.error(
                    request,
                    "Questo username è già in uso. Contatta l'amministratore se hai bisogno di assistenza.",
                )
                return render(request, "dashboard/register_step2.html", {"email": email})

            user = User.objects.create_user(
                username=short_username,
                email=email_clean,
                password=password,
            )
            user.save()

            messages.success(request, f"Account creato! Il tuo username è: {short_username}")
            return redirect("login")

    return render(request, "dashboard/register_step2.html", {"email": email})


# --- DASHBOARD VIEWS ---
@login_required(login_url="login")
def home(request):
    return render(request, "dashboard/home.html")

@login_required(login_url="login")
def leads(request):
    return render(request, "dashboard/leads.html")

@login_required(login_url="login")
def partnerships(request):
    return render(request, "dashboard/partnerships.html")

@login_required(login_url="login")
def progetti(request):
    qs = Progetti.objects.all()

    q = (request.GET.get("q") or "").strip()
    stato = (request.GET.get("stato") or "").strip()

    if q:
        qs = qs.filter(
            Q(nome_progetto__icontains=q)
            | Q(stato__icontains=q)
            | Q(pm__icontains=q)
            | Q(provenienza__icontains=q)
        )

    if stato:
        qs = qs.filter(stato__iexact=stato)

    qs = qs.order_by("nome_progetto")

    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    stati = (
        Progetti.objects.exclude(stato__isnull=True)
        .exclude(stato__exact="")
        .values_list("stato", flat=True)
        .distinct()
        .order_by("stato")
    )

    preserved = request.GET.copy()
    preserved.pop("page", None)
    preserved_qs = preserved.urlencode()
    if preserved_qs:
        preserved_qs = preserved_qs + "&"

    context = {
        "page_obj": page_obj,
        "progetti": page_obj.object_list,
        "search_query": q,
        "stato_filter": stato,
        "stati": stati,
        "querystring": preserved_qs,
    }
    return render(request, "dashboard/progetti.html", context)

@login_required(login_url="login")
def eventi(request):
    eventi_list = Eventi.objects.all()
    return render(request, "dashboard/pages/eventi.html", {"eventi": eventi_list})

@login_required(login_url="login")
def formazioni(request):
    formazioni_list = Formazioni.objects.all()
    return render(request, "dashboard/pages/formazioni.html", {"formazioni": formazioni_list})

@login_required(login_url="login")
def soci(request):
    soci_list = Soci.objects.all()
    return render(request, "dashboard/pages/soci.html", {"soci": soci_list})
@login_required(login_url="login")
def partnerships(request):
    # Gestione delle 3 schede (Tabs) tramite l'URL (es: ?tab=partnership)
    # Se non c'è il parametro tab, di default apre "partnership"
    tab = request.GET.get("tab", "partnership")
    
    # Prepariamo la lista dati in base al tab selezionato
    if tab == "partnership":
        # Per ora peschiamo tutte le righe dalla tabella PARTNERSHIP
        dati_tabella = Partnership.objects.all().order_by('partnership')
    elif tab == "non_finalizzate":
        # Qui in futuro potrai filtrare, ad es: Partnership.objects.filter(status_partnership="Non finalizzata")
        dati_tabella = [] 
    elif tab == "lead":
        # Qui andranno i lead partnership
        dati_tabella = []
    else:
        dati_tabella = []

    context = {
        "current_tab": tab,
        "dati_tabella": dati_tabella
    }
    return render(request, "dashboard/partnerships.html", context)