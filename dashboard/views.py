from django.shortcuts import render

def home(request):
    return render(request, 'dashboard/pages/home.html')


def progetti(request):
    return render(request, 'dashboard/pages/progetti.html')


def leads(request):
    return render(request, 'dashboard/pages/leads.html')


def partnerships(request):
    return render(request, 'dashboard/pages/partnerships.html')
