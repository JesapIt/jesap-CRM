from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('progetti/', views.progetti, name='progetti'),
    path('leads/', views.leads, name='leads'),
    path('partnerships/', views.partnerships, name='partnerships'),
]