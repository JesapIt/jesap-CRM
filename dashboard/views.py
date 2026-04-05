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

from .models import Socio
from django.conf import settings

# --- 1. LOGIN (Standard username + password) ---
def login_view(request):
    if request.method == 'POST':
        u = request.POST.get('username')
        p = request.POST.get('password')
        
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect('home') # Redirect to dashboard
        else:
            messages.error(request, "Username o password errati.")
            
    return render(request, 'dashboard/login.html')

# --- 2. SUBSCRIBE STEP 1 (Check Database & Send Email) ---
def register_step1(request):
    if request.method == 'POST':
        # .strip() removes any accidental spaces before or after the email
        email = request.POST.get('email').strip() 
        
        # ADD __iexact HERE: This tells the database to ignore uppercase/lowercase
        if Socio.objects.filter(email_jesap__iexact=email).exists():
            
            # Check if this person has ALREADY registered a Django account
            # We use __iexact here too, just to be safe!
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, "Questo account è già stato registrato. Vai al Login.")
                return redirect('login')

            # --- The rest of your email sending code stays exactly the same ---
            user_data = force_bytes(email)
            uid = urlsafe_base64_encode(user_data)
            token = default_token_generator.make_token(User(email=email)) 
            
            verification_link = request.build_absolute_uri(f"/register/step2/{uid}/{token}/")

            send_mail(
                subject="Completa la tua registrazione al CRM JESAP",
                message=f"Ciao! Clicca su questo link per impostare la tua password: {verification_link}",
                from_email="noreply@jesap.it",
                recipient_list=[email],
                fail_silently=False,
            )
            
            messages.success(request, "Ti abbiamo inviato un'email! Controlla la casella di posta per impostare la password.")
            return redirect('register_step1')
            
        else:
            messages.error(request, "Accesso negato. Questa email non è presente nel database dell'associazione.")
            return redirect('register_step1')
            
    return render(request, 'dashboard/register_step1.html')
# --- 3. SUBSCRIBE STEP 2 (Double Password & Create Account) ---
def register_step2(request, uidb64, token):
    try:
        # Decode the email from the URL link
        email = force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError):
        email = None

    # Validate that the link is real and hasn't been tampered with
    if email is not None and default_token_generator.check_token(User(email=email), token):
        
        if request.method == 'POST':
            password = request.POST.get('password')
            password_confirm = request.POST.get('password_confirm')
            
            # Double verification check
            if password != password_confirm:
                messages.error(request, "Le password non coincidono. Riprova.")
            elif len(password) < 8:
                messages.error(request, "La password deve essere di almeno 8 caratteri.")
            else:
                # Generate the username from the email prefix (e.g., mario.rossi)
                username = email.split('@')[0]
                
                # Create the actual Django user
                user = User.objects.create_user(username=username, email=email, password=password)
                user.save()
                
                messages.success(request, f"Account creato con successo! Il tuo username è: {username}. Ora puoi accedere.")
                return redirect('login')
                
        # Pass the email to the template so the user knows which account they are activating
        return render(request, 'dashboard/register_step2.html', {'email': email})
        
    else:
        messages.error(request, "Il link di registrazione non è valido o è scaduto.")
        return redirect('register_step1')
@login_required(login_url='login')
def home(request):
    return render(request, 'dashboard/home.html')

# (If you have views for leads, progetti, and partnerships, add them back here too!)
@login_required(login_url='login')
def leads(request):
    return render(request, 'dashboard/leads.html')

@login_required(login_url='login')
def progetti(request):
    return render(request, 'dashboard/progetti.html')

@login_required(login_url='login')
def partnerships(request):
    return render(request, 'dashboard/partnerships.html')