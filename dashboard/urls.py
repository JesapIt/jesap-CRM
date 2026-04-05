from django.urls import path
from . import views

urlpatterns = [
    # Dashboard Pages
    path('', views.home, name='home'),
    path('leads/', views.leads, name='leads'),
    path('progetti/', views.progetti, name='progetti'),
    path('partnerships/', views.partnerships, name='partnerships'),

    # Authentication & Registration
    path('login/', views.login_view, name='login'),
    path('register/', views.register_step1, name='register_step1'), # Step 1: Email check
    path('register/step2/<uidb64>/<token>/', views.register_step2, name='register_step2'), # Step 2: Password setup
]