from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import CaseInsensitivePasswordResetForm
from . import views

urlpatterns = [
    # Dashboard Pages
    path('', views.home, name='home'),
    path('leads/', views.leads, name='leads'),
    path('progetti/', views.progetti, name='progetti'),
    path('partnerships/', views.partnerships, name='partnerships'),

    # --- CRUD de Progetti ---
    path('progetti/nuova/', views.progetto_create, name='progetto_create'),
    path('progetti/<str:pk>/modifica/', views.progetto_update, name='progetto_update'),
    path('progetti/<str:pk>/elimina/', views.progetto_delete, name='progetto_delete'),
    
    # --- CRUD de Partnerships ---
    path('partnerships/nuova/', views.partnership_create, name='partnership_create'),
    path('partnerships/<str:pk>/modifica/', views.partnership_update, name='partnership_update'),
    path('partnerships/<str:pk>/elimina/', views.partnership_delete, name='partnership_delete'),

    # --- CRUD de Partnerships Finalizzate ---
    path('partnerships/non-finalizzate/nuova/', views.partnership_nonfin_create, name='partnership_nonfin_create'),
    path('partnerships/non-finalizzate/<str:pk>/modifica/', views.partnership_nonfin_update, name='partnership_nonfin_update'),

    # Soci
    path('soci/', views.soci, name='soci'),
    path('soci/nuovo/', views.socio_create, name='socio_create'),
    path('soci/<int:pk>/modifica/', views.socio_update, name='socio_update'),
    path('soci/admin-promote/', views.admin_promote, name='admin_promote'),
    path('soci/admin-demote/', views.admin_demote, name='admin_demote'),

    # Authentication & Registration
    path('login/', views.login_view, name='login'),
    path('register/', views.register_step1, name='register_step1'), # Step 1: Email check
    path('register/step2/<str:token>/', views.register_step2, name='register_step2'), # Step 2: Password setup

    # Logout
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Password reset (Django built-in views + custom templates)
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            form_class=CaseInsensitivePasswordResetForm,
            template_name='dashboard/password_reset_form.html',
            email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='dashboard/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='dashboard/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='dashboard/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
]