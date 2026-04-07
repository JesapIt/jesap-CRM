from django.contrib import admin
from django.urls import path, include  # <-- Make sure 'include' is imported here!

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # This tells Django: "Send all other web traffic to the dashboard app's URLs"
    path('', include('dashboard.urls')), 
]