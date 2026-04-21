from django.contrib import admin
from .models import AuditLog, Eventi, Formazioni, Progetti, Soci, Socio, Partnership, PartnershipNonFin

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


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user_repr', 'action', 'content_type', 'object_repr')
    list_filter = ('action', 'content_type', 'timestamp')
    search_fields = ('user_repr', 'object_repr', 'object_pk')
    readonly_fields = (
        'timestamp', 'user', 'user_repr', 'action',
        'content_type', 'object_pk', 'object_repr', 'changes',
    )
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
