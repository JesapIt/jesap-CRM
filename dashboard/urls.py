from django.urls import path
from dashboard import views


urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('home', views.home, name='home'),
    path('progetti/', views.progetti, name='progetti'),
    path('leads/', views.leads, name='leads'),
    path('partnerships/', views.partnerships, name='partnerships'),
]