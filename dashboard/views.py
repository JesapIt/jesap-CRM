from django.shortcuts import render
from .models import Eventi, Formazioni, Progetti, Soci

# Home view: Renders the main dashboard dashboard page
def home(request):
    return render(request, 'dashboard/pages/home.html')


# Progetti view: Fetches all projects from the PROGETTI table
def progetti(request):
    progetti_list = Progetti.objects.all()
    q = (request.GET.get("q") or "").strip()
    if q:
        progetti_list = progetti_list.filter(nome_progetto__icontains=q)

    context = {
        "progetti": progetti_list,
        "search_query": q,
    }
    return render(request, "dashboard/pages/progetti.html", context)


# Eventi view: Fetches all events from the EVENTI table
def eventi(request):
    # Retrieve all records from the Eventi model
    eventi_list = Eventi.objects.all()
    
    # Pack the data into a context dictionary
    context = {
        'eventi': eventi_list
    }
    # Note: Make sure you have an 'eventi.html' template created
    return render(request, 'dashboard/pages/eventi.html', context)


# Formazioni view: Fetches all training sessions from the FORMAZIONI table
def formazioni(request):
    # Retrieve all records from the Formazioni model
    formazioni_list = Formazioni.objects.all()
    
    # Pack the data into a context dictionary
    context = {
        'formazioni': formazioni_list
    }
    # Note: Make sure you have a 'formazioni.html' template created
    return render(request, 'dashboard/pages/formazioni.html', context)


# Soci view: Fetches all members from the SOCI table
def soci(request):
    # Retrieve all records from the Soci model
    soci_list = Soci.objects.all()
    
    # Pack the data into a context dictionary
    context = {
        'soci': soci_list
    }
    # Note: Make sure you have a 'soci.html' template created
    return render(request, 'dashboard/pages/soci.html', context)


# Leads view: Currently static as there is no Leads model provided yet
def leads(request):
    return render(request, 'dashboard/pages/leads.html')


# Partnerships view: Currently static as there is no Partnerships model provided yet
def partnerships(request):
    return render(request, 'dashboard/pages/partnerships.html')