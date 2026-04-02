from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import Socio  # Importiamo il modello Socio che ora è in models.py

# --- 1. HOME (Protetta da login) ---
@login_required(login_url='login')
def home(request):
    return render(request, 'home.html', {'username': request.user.username})

# --- 2. LOGIN VIEW ---
def login_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        user = authenticate(request, username=u, password=p)
        if user is not None:
            auth_login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Username o Password errati.")
            
    return render(request, 'login.html')

# --- 3. LOGOUT VIEW (Opzionale ma utile) ---
def logout_view(request):
    auth_logout(request)
    return redirect('login')

# --- 4. REGISTRAZIONE (Logica Jesap: 2 Step) ---
def register_view(request):
    # Step 2: Se la mail è già stata validata ed è in sessione
    if 'temp_email' in request.session:
        email = request.session['temp_email']
        username = email.split('@')[0] # Genera username dalla parte prima della @

        if request.method == 'POST':
            password = request.POST.get('password')
            password_confirm = request.POST.get('password_confirm')

            if password == password_confirm:
                # Creazione utente Django
                if not User.objects.filter(username=username).exists():
                    user = User.objects.create_user(username=username, email=email, password=password)
                    user.save()
                    del request.session['temp_email'] # Puliamo la sessione
                    messages.success(request, f"Registrazione completata! Username: {username}")
                    return redirect('login')
                else:
                    messages.error(request, "Questo utente è già registrato.")
                    return redirect('login')
            else:
                messages.error(request, "Le password non coincidono.")

        return render(request, 'register_step2.html', {'username': username, 'email': email})

    # Step 1: Controllo iniziale della mail
    if request.method == 'POST':
        email = request.POST.get('email')
        
        # Controllo se la mail esiste nella tabella 'soci' (Supabase)
        if Socio.objects.filter(email=email).exists():
            # Controlliamo se ha già un account Django
            if User.objects.filter(email=email).exists():
                messages.info(request, "Sei già registrato. Accedi.")
                return redirect('login')
            
            # Se è un socio e non è registrato, salviamo la mail in sessione
            request.session['temp_email'] = email
            return redirect('register')
        else:
            messages.error(request, "Accesso negato: non sei presente nel database soci Jesap.")
    
    return render(request, 'register_step1.html')