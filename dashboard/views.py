from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# These are for generating secure email links
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator

from .models import Eventi, Formazioni, Progetti, Soci, Socio
from django.conf import settings


# --- 1. LOGIN (Standard username + password) ---
def login_view(request):
    if request.method == "POST":
        u = request.POST.get("username")
        p = request.POST.get("password")

        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect("home")

        messages.error(request, "Username o password errati.")

    return render(request, "dashboard/login.html")


# --- 2. SUBSCRIBE STEP 1 (Check Database & Send Email) ---
def register_step1(request):
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()

        # Allow registration only if email exists in SOCI table
        if Socio.objects.filter(email_jesap__iexact=email).exists():
            # Prevent duplicate Django accounts for same email
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "Questo account è già stato registrato. Vai al Login.")
                return redirect("login")

            uid = urlsafe_base64_encode(force_bytes(email))
            token = default_token_generator.make_token(User(email=email))
            verification_link = request.build_absolute_uri(f"/register/step2/{uid}/{token}/")

            send_mail(
                subject="Completa la tua registrazione al CRM JESAP",
                message=f"Ciao! Clicca su questo link per impostare la tua password: {verification_link}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@jesap.it"),
                recipient_list=[email],
                fail_silently=False,
            )

            messages.success(
                request,
                "Ti abbiamo inviato un'email! Controlla la casella di posta per impostare la password.",
            )
            return redirect("register_step1")

        messages.error(request, "Accesso negato. Questa email non è presente nel database dell'associazione.")
        return redirect("register_step1")

    return render(request, "dashboard/register_step1.html")


# --- 3. SUBSCRIBE STEP 2 (Double Password & Create Account) ---
def register_step2(request, uidb64, token):
    try:
        email = force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError):
        email = None

    if email is None or not default_token_generator.check_token(User(email=email), token):
        messages.error(request, "Il link di registrazione non è valido o è scaduto.")
        return redirect("register_step1")

    if request.method == "POST":
        password = request.POST.get("password")
        password_confirm = request.POST.get("password_confirm")

        if password != password_confirm:
            messages.error(request, "Le password non coincidono. Riprova.")
        elif not password or len(password) < 8:
            messages.error(request, "La password deve essere di almeno 8 caratteri.")
        else:
            username = email.split("@")[0]
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()

            messages.success(
                request,
                f"Account creato con successo! Il tuo username è: {username}. Ora puoi accedere.",
            )
            return redirect("login")

    return render(request, "dashboard/register_step2.html", {"email": email})


@login_required(login_url="login")
def home(request):
    # Using base_figma layout pages
    return render(request, "dashboard/pages/home.html")


@login_required(login_url="login")
def leads(request):
    return render(request, "dashboard/leads.html")


@login_required(login_url="login")
def partnerships(request):
    return render(request, "dashboard/partnerships.html")


@login_required(login_url="login")
def progetti(request):
    progetti_list = Progetti.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        progetti_list = progetti_list.filter(nome_progetto__icontains=q)

    context = {
        "progetti": progetti_list,
        "search_query": q,
    }
    return render(request, "dashboard/progetti.html", context)


# Optional endpoints (kept for future pages)
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
