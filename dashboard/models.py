from django.db import models

class Socio(models.Model):
    
    #Add db_column='EMAIL @jesap' 
    
    email_jesap = models.EmailField(db_column='EMAIL @jesap',unique=True, max_length=254) 
    nome = models.CharField(max_length=100, blank=True, null=True)
    cognome = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        managed = False # Because Supabase manages the table
        db_table = 'SOCI' # The exact name of your table in Supabase