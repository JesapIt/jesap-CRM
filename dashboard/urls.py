from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import CaseInsensitivePasswordResetForm
from . import views
from .recruitment import views as rec

urlpatterns = [
    # Healthcheck (Railway)
    path('healthz', views.healthz, name='healthz'),

    # Dashboard Pages
    path('', views.home, name='home'),
    path('leads/', views.leads, name='leads'),
    path('leads/nuova/', views.lead_create, name='lead_create'),
    path('leads/<str:pk>/modifica/', views.lead_update, name='lead_update'),
    path('leads/<str:pk>/elimina/', views.lead_delete, name='lead_delete'),
    path('progetti/', views.progetti, name='progetti'),
    path('partnerships/', views.partnerships, name='partnerships'),

    # --- CRUD de Progetti ---
    path('progetti/nuova/', views.progetto_create, name='progetto_create'),
    path('progetti/<str:pk>/modifica/', views.progetto_update, name='progetto_update'),
    path('progetti/<str:pk>/elimina/', views.progetto_delete, name='progetto_delete'),
    
    # --- CRUD de Partnerships ---
    # PK = nome della partnership: può contenere "/" → converter `path`.
    path('partnerships/nuova/', views.partnership_create, name='partnership_create'),
    path('partnerships/nuova/<str:kind>/', views.partnership_create, name='partnership_create_kind'),
    path('partnerships/<path:pk>/modifica/', views.partnership_update, name='partnership_update'),
    path('partnerships/<path:pk>/elimina/', views.partnership_delete, name='partnership_delete'),
    path('partnerships/<path:pk>/sposta/', views.partnership_change_status, name='partnership_change_status'),

    # --- Task (tutti i soci loggati) ---
    path('task/', views.tasks, name='tasks'),
    path('task/nuova/', views.task_create, name='task_create'),
    path('task/<int:pk>/modifica/', views.task_update, name='task_update'),
    path('task/<int:pk>/elimina/', views.task_delete, name='task_delete'),
    path('task/<int:pk>/stato/', views.task_set_stato, name='task_set_stato'),

    # --- Credenziali (solo CdA + responsabili) ---
    path('credenziali/', views.credenziali, name='credenziali'),
    path('credenziali/nuova/', views.credenziale_create, name='credenziale_create'),
    path('credenziali/<int:pk>/modifica/', views.credenziale_update, name='credenziale_update'),
    path('credenziali/<int:pk>/elimina/', views.credenziale_delete, name='credenziale_delete'),
    path('credenziali/<int:pk>/rivela/', views.credenziale_reveal, name='credenziale_reveal'),

    # --- Recruitment (CdA + Head of + autorizzati) ---
    path('recruitment/', rec.recruitment_home, name='rec_home'),
    path('recruitment/sessioni/nuova/', rec.sessione_create, name='rec_sessione_create'),
    path('recruitment/accessi/', rec.accessi, name='rec_accessi'),
    path('recruitment/api/candidature/', rec.api_candidature, name='rec_api_candidature'),
    path('recruitment/candidato/<int:pk>/', rec.candidato_detail, name='rec_candidato'),
    path('recruitment/gruppi/<int:pk>/', rec.gruppo_update, name='rec_gruppo_update'),
    path('recruitment/<int:sessione_id>/impostazioni/', rec.sessione_update, name='rec_sessione_update'),
    path('recruitment/<int:sessione_id>/gruppi/nuovo/', rec.gruppo_create, name='rec_gruppo_create'),
    path('recruitment/<int:sessione_id>/candidati/nuovo/', rec.candidato_create, name='rec_candidato_create'),
    path('recruitment/<int:sessione_id>/email/<str:fase>/', rec.recruitment_invia_email, name='rec_invia_email'),
    path('recruitment/<int:sessione_id>/<str:tab>/', rec.recruitment_tab, name='rec_tab'),

    # Soci (read-only: write avviene via sync Sheets -> Supabase)
    path('soci/', views.soci, name='soci'),
    path('soci/admin-promote/', views.admin_promote, name='admin_promote'),
    path('soci/admin-demote/', views.admin_demote, name='admin_demote'),

    # Authentication & Registration
    path('login/', views.login_view, name='login'),
    path('register/', views.register_step1, name='register_step1'), # Step 1: Email check
    path('register/step2/<str:token>/', views.register_step2, name='register_step2'), # Step 2: Password setup

    # Logout
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Password reset (custom views with email error handling)
    # from_email=None → usa DEFAULT_FROM_EMAIL (Resend onboarding@resend.dev)
    path(
        'password-reset/',
        views.CustomPasswordResetView.as_view(
            form_class=CaseInsensitivePasswordResetForm,
            template_name='dashboard/password_reset_form.html',
            email_template_name='registration/password_reset_email.txt',
            html_email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
            from_email=None,
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
        views.CustomPasswordResetConfirmView.as_view(
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