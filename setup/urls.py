from django.contrib import admin
from django.urls import path
from dashboard import views # Importiamo le logiche dalla dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
]
