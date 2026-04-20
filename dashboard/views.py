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
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
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
                ctx = {'verification_link': verification_link}
                text_body = render_to_string('registration/registration_verify_email.txt', ctx)
                html_body = render_to_string('registration/registration_verify_email.html', ctx)

                msg = EmailMultiAlternatives(
                    subject="Completa la tua registrazione all'ERP JESAP",
                    body=text_body,
                    from_email=None,
                    to=[email],
                )
                msg.attach_alternative(html_body, 'text/html')
                msg.send(fail_silently=False)
                
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
            
        paginator = Paginator(queryset, 25)
        page_obj = paginator.get_page(request.GET.get("page"))
        context["partnerships"] = page_obj
        context["dati_tabella"] = page_obj
        context["page_obj"] = page_obj

    elif tab == "non_finalizzate":
        queryset = PartnershipNonFin.objects.all().order_by('realta')

        if search_query:
            queryset = queryset.filter(
                Q(realta__icontains=search_query) |
                Q(contatti__icontains=search_query)
            )

        paginator = Paginator(queryset, 25)
        page_obj = paginator.get_page(request.GET.get("page"))
        context["dati_tabella"] = page_obj
        context["page_obj"] = page_obj

    elif tab == "lead":
        # Lógica futura para lead partnership
        context["dati_tabella"] = []

    else:
        context["dati_tabella"] = []

    return render(request, "dashboard/partnerships.html", context)

@login_required(login_url="login")
def progetti(request):
    search_query = request.GET.get("q", "").strip()
    stato_filter = request.GET.get("stato", "").strip()

    queryset = Progetti.objects.all().order_by('nome_progetto')

    stati = (
        Progetti.objects.exclude(stato__isnull=True)
        .exclude(stato__exact='')
        .exclude(stato='None')
        .values_list('stato', flat=True)
        .distinct()
    )

    if search_query:
        queryset = queryset.filter(
            Q(nome_progetto__icontains=search_query)
            | Q(pm__icontains=search_query)
            | Q(cliente__icontains=search_query)
        )

    if stato_filter:
        queryset = queryset.filter(stato=stato_filter)

    paginator = Paginator(queryset, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "dashboard/progetti.html", {
        "progetti": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "stato_filter": stato_filter,
        "stati": stati,
    })

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
    tab = request.GET.get("tab", "da")
    search_query = request.GET.get("q", "").strip()

    AREA_TABS = {
        "da":  "D&A",
        "bd":  "BD",
        "hr":  "HR",
        "mc":  "M&C",
    }

    # Redirect unknown tabs to default
    valid_tabs = set(AREA_TABS) | {"board", "admin"}
    if tab not in valid_tabs:
        tab = "da"

    context = {
        "current_tab": tab,
        "search_query": search_query,
        "is_admin_tab": tab == "admin",
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

        if request.user.is_superuser:
            all_non_admin = User.objects.filter(is_staff=False, is_superuser=False).order_by("username")
            context["non_admin_users"] = all_non_admin

        context["soci_list"] = []
    else:
        # Base filter: only active members
        queryset = Soci.objects.filter(status__iexact="Associato").order_by("nome_e_cognome")

        if tab == "board":
            queryset = queryset.filter(
                Q(ruolo__icontains="board")
                | Q(ruolo__icontains="presidente")
                | Q(ruolo__icontains="vicepresidente")
                | Q(ruolo__icontains="segretario")
                | Q(ruolo__icontains="tesoriere")
                | Q(ruolo_esteso__icontains="board")
            )
        elif tab in AREA_TABS:
            queryset = queryset.filter(area_di_appartenenza__iexact=AREA_TABS[tab])

        if search_query:
            queryset = queryset.filter(
                Q(nome_e_cognome__icontains=search_query)
                | Q(ruolo__icontains=search_query)
                | Q(email_jesap__icontains=search_query)
            )

        paginator = Paginator(queryset, 25)
        page_obj = paginator.get_page(request.GET.get("page"))
        context["soci_list"] = page_obj
        context["page_obj"] = page_obj

    return render(request, "dashboard/soci.html", context)


@login_required(login_url="login")
@user_passes_test(lambda u: u.is_superuser)
def admin_promote(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        try:
            target = User.objects.get(pk=user_id)
            target.is_staff = True
            target.save(update_fields=["is_staff"])
            messages.success(request, f"{target.username} promosso ad admin.")
        except User.DoesNotExist:
            messages.error(request, "Utente non trovato.")
    return redirect(reverse("soci") + "?tab=admin")


@login_required(login_url="login")
@user_passes_test(lambda u: u.is_superuser)
def admin_demote(request):
    if request.method == "POST":
        user_id = request.POST.get("user_id")
        try:
            target = User.objects.get(pk=user_id)
            if target == request.user:
                messages.error(request, "Non puoi rimuovere te stesso.")
            else:
                target.is_staff = False
                target.is_superuser = False
                target.save(update_fields=["is_staff", "is_superuser"])
                messages.success(request, f"{target.username} rimosso dagli admin.")
        except User.DoesNotExist:
            messages.error(request, "Utente non trovato.")
    return redirect(reverse("soci") + "?tab=admin")

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
