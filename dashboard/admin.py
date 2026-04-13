from django.contrib import admin
from .models import Eventi, Formazioni, Progetti, Soci, Socio, Partnership, PartnershipNonFin

@admin.register(Eventi)
class EventiAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome_evento', 'data_inizio_evento', 'anno', 'tipologia_evento')

@admin.register(Formazioni)
class FormazioniAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'area', 'data', 'anno')

@admin.register(Progetti)
class ProgettiAdmin(admin.ModelAdmin):
    list_display = ('codice_progetto', 'nome_progetto', 'cliente', 'stato', 'pm')

@admin.register(Soci)
class SociAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome_e_cognome', 'email_jesap', 'cellulare', 'status')

@admin.register(Socio)
class SocioAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome_e_cognome', 'email_jesap', 'cellulare', 'status')

@admin.register(Partnership)
class PartnershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'partnership', 'status_partnership', 'contatti', 'cartella_sul_drive')

@admin.register(PartnershipNonFin)
class PartnershipNonFinAdmin(admin.ModelAdmin):
    list_display = ('realta', 'contatti', 'periodo', 'anno', 'cartella')
