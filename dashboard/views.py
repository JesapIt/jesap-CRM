from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from urllib.parse import urlencode
from .models import Partnership
from .forms import PartnershipForm

# These are for generating secure email links
from django.core.mail import send_mail
from django.core import signing
from .models import Eventi, Formazioni, Progetti, Soci, Socio, Partnership, PartnershipNonFin
from django.conf import settings# Adicione este import lá no topo junto com os outros
from django.contrib.auth.decorators import user_passes_test

# Função que checa se o usuário é um Editor ou um Superusuário
def is_editor(user):
    return user.groups.filter(name='Editori').exists() or user.is_superuser

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
    # Captura a tab atual (padrão: partnership)
    tab = request.GET.get("tab", "partnership")
    
    # Captura os parâmetros de busca e filtro
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    
    context = {
        "current_tab": tab,
        "search_query": search_query,
        "status_filter": status_filter,
        "is_editor": is_editor(request.user),
    }
    
    if tab == "partnership":
        # 1. Busca inicial
        queryset = Partnership.objects.all().order_by('partnership')
        
        # 2. Pega todos os status únicos para popular o dropdown no HTML
        stati_partnership = Partnership.objects.exclude(
            status_partnership__isnull=True
        ).exclude(
            status_partnership__exact=''
        ).values_list('status_partnership', flat=True).distinct()
        
        context["stati_partnership"] = stati_partnership
        
        # 3. Aplica o filtro de busca por texto (Nome ou Contatos, por exemplo)
        if search_query:
            queryset = queryset.filter(
                Q(partnership__icontains=search_query) | 
                Q(contatti__icontains=search_query)
            )
            
        # 4. Aplica o filtro de status do dropdown
        if status_filter:
            queryset = queryset.filter(status_partnership=status_filter)
            
        context["partnerships"] = queryset
        context["dati_tabella"] = queryset

    elif tab == "non_finalizzate":
        queryset = PartnershipNonFin.objects.all().order_by('realta')
        
        # Filtro de busca na aba "non_finalizzate"
        if search_query:
            queryset = queryset.filter(
                Q(realta__icontains=search_query) | 
                Q(contatti__icontains=search_query)
            )
            
        context["dati_tabella"] = queryset

    elif tab == "lead":
        # Lógica futura para lead partnership
        context["dati_tabella"] = []

    else:
        context["dati_tabella"] = []

    return render(request, "dashboard/partnerships.html", context)

@login_required(login_url="login")
def progetti(request):
    progetti_list = Progetti.objects.all()
    return render(request, "dashboard/progetti.html", {"progetti": progetti_list})

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

@user_passes_test(is_editor)
def partnership_create(request):
    if request.method == 'POST':
        form = PartnershipForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Partnership criada com sucesso!")
            return redirect('partnerships') # Redireciona para a aba principal
    else:
        form = PartnershipForm()
    
    context = {'form': form, 'azione': 'Nuova'}
    return render(request, 'dashboard/partnership_form.html', context)

@user_passes_test(is_editor)
def partnership_update(request, pk):
    # Tenta achar a partnership pelo ID, se não achar, dá erro 404
    partnership = get_object_or_404(Partnership, id=pk)
    
    if request.method == 'POST':
        form = PartnershipForm(request.POST, instance=partnership)
        if form.is_valid():
            form.save()
            messages.success(request, "Partnership atualizada com sucesso!")
            return redirect('partnerships') # Redireciona para a aba principal
    else:
        form = PartnershipForm(instance=partnership)
    
    context = {'form': form, 'azione': 'Modifica'}
    return render(request, 'dashboard/partnership_form.html', context)

@user_passes_test(is_editor)
def partnership_delete(request, pk):
    partnership = get_object_or_404(Partnership, id=pk)
    
    if request.method == 'POST':
        partnership.delete()
        messages.success(request, "Partnership eliminada com sucesso!")
        return redirect('partnerships') # Redireciona para a aba principal
        
    return render(request, 'dashboard/partnership_confirm_delete.html', {'partnership': partnership})
