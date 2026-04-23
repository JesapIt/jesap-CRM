import re
from datetime import date, datetime

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Max


def _parse_iso_date(value):
    if value in (None, ''):
        return None
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _slug_for_email(value):
    return re.sub(r'\s+', '', (value or '')).lower()

class Eventi(models.Model):
    id = models.TextField(db_column='ID', primary_key=True)
    nome_evento = models.TextField(blank=True, null=True)
    data_inizio_evento = models.TextField(blank=True, null=True)
    anno = models.BigIntegerField(blank=True, null=True)
    durata_evento_giorni = models.TextField(blank=True, null=True)
    tipologia_evento = models.TextField(blank=True, null=True)
    tema_evento = models.TextField(blank=True, null=True)
    modalita = models.TextField(blank=True, null=True)
    organizzato_da = models.TextField(blank=True, null=True)
    dettaglio_organizzatore = models.TextField(blank=True, null=True)
    organizzato_dalla_je = models.TextField(blank=True, null=True)
    totale_je_coinvolte = models.TextField(blank=True, null=True)
    num_partecipanti_jesap = models.BigIntegerField(blank=True, null=True)
    num_partecipanti_evento = models.TextField(blank=True, null=True)
    num_staff_jesap_organizzatori = models.TextField(blank=True, null=True)
    target_partecipanti = models.TextField(blank=True, null=True)
    aperto_al_network = models.TextField(blank=True, null=True)
    percentuale_gradimento = models.TextField(blank=True, null=True)
    num_patrocini = models.TextField(blank=True, null=True)
    collab_enti_territorio = models.TextField(blank=True, null=True)
    ricavi_sponsor_partner = models.TextField(blank=True, null=True)
    costi = models.TextField(blank=True, null=True)
    ricavi_fee_senza_iva = models.TextField(blank=True, null=True)
    link_foto = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'EVENTI'


class Formazioni(models.Model):
    id = models.TextField(db_column='ID', primary_key=True)
    nome = models.TextField(db_column='NOME', blank=True, null=True)
    area = models.TextField(db_column='AREA', blank=True, null=True)
    numero_partecipanti = models.BigIntegerField(db_column='Numero partecipanti', blank=True, null=True)
    data = models.TextField(db_column='Data', blank=True, null=True)
    durata_formazione_ore_field = models.TextField(db_column='Durata formazione (ore)', blank=True, null=True)
    durata_formazione_ore_2 = models.TextField(db_column='Durata formazione (ore) 2', blank=True, null=True)
    ente_erogante = models.TextField(db_column='Ente erogante', blank=True, null=True)
    anno = models.BigIntegerField(db_column='ANNO', blank=True, null=True)
    modalitα_di_erogazione = models.TextField(db_column='Modalità di erogazione', blank=True, null=True)
    luogo_della_formazione = models.TextField(db_column='Luogo della formazione', blank=True, null=True)
    erogata_in_un_evento_je = models.TextField(db_column='Erogata in un evento JE', blank=True, null=True)
    processo_di_handover_onboarding = models.BooleanField(db_column='Processo di Handover/Onboarding', blank=True, null=True)
    spese_della_formazione_senza_iva_field = models.TextField(db_column='Spese della Formazione (senza IVA)', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'FORMAZIONI'


class Progetti(models.Model):
    codice_progetto = models.TextField(db_column='CODICE PROGETTO', primary_key=True, blank=True)
    nome_progetto = models.TextField(db_column='NOME PROGETTO', blank=True, null=True)
    cliente = models.TextField(db_column='CLIENTE', blank=True, null=True)
    tipologia_cliente = models.TextField(db_column='TIPOLOGIA CLIENTE', blank=True, null=True)
    tipologia_di_progetto = models.TextField(db_column='TIPOLOGIA DI PROGETTO', blank=True, null=True)
    stato = models.TextField(db_column='STATO', blank=True, null=True)
    area_di_pertinenza = models.TextField(db_column='AREA DI PERTINENZA', blank=True, null=True)
    pm = models.TextField(db_column='PM', blank=True, null=True)
    provenienza = models.TextField(db_column='PROVENIENZA', blank=True, null=True)
    data_primo_contatto = models.TextField(db_column='DATA PRIMO CONTATTO', blank=True, null=True)
    data_firma_contratto = models.TextField(db_column='DATA FIRMA CONTRATTO', blank=True, null=True)
    data_inizio = models.TextField(db_column='DATA INIZIO', blank=True, null=True)
    mese_inizio = models.BigIntegerField(db_column='MESE INIZIO', blank=True, null=True)
    data_fine_contratto = models.TextField(db_column='DATA FINE CONTRATTO', blank=True, null=True)
    anno = models.BigIntegerField(db_column='ANNO', blank=True, null=True)
    n_risorse_coinvolte = models.BigIntegerField(db_column='N° RISORSE COINVOLTE', blank=True, null=True)
    fatturato_senza_iva_field = models.TextField(db_column='Fatturato (senza IVA)', blank=True, null=True)
    iva = models.TextField(db_column='IVA', blank=True, null=True)
    costi = models.TextField(db_column='COSTI', blank=True, null=True)
    profitti = models.TextField(db_column='PROFITTI', blank=True, null=True)
    descrizione_servizio_offerto = models.TextField(db_column='DESCRIZIONE SERVIZIO OFFERTO', blank=True, null=True)
    coinvolgimento_della_pubblica_amministrazione = models.BooleanField(db_column='COINVOLGIMENTO DELLA Pubblica Amministrazione', blank=True, null=True)
    soddisfazione_team_in_field = models.TextField(db_column='SODDISFAZIONE TEAM (in %%)', blank=True, null=True)
    soddisfazione_cliente_in_field = models.TextField(db_column='SODDISFAZIONE CLIENTE (in %%)', blank=True, null=True)
    risorsa_1 = models.TextField(db_column='RISORSA 1', blank=True, null=True)
    risorsa_2 = models.TextField(db_column='RISORSA 2', blank=True, null=True)
    risorsa_3 = models.TextField(db_column='RISORSA 3', blank=True, null=True)
    risorsa_4 = models.TextField(db_column='RISORSA 4', blank=True, null=True)
    risorsa_5 = models.TextField(db_column='RISORSA 5', blank=True, null=True)
    risorsa_6 = models.TextField(db_column='RISORSA 6', blank=True, null=True)
    risorsa_7 = models.TextField(db_column='RISORSA 7', blank=True, null=True)
    risorsa_8 = models.TextField(db_column='RISORSA 8', blank=True, null=True)
    risorsa_9 = models.TextField(db_column='RISORSA 9', blank=True, null=True)
    risorsa_10 = models.TextField(db_column='RISORSA 10', blank=True, null=True)
    risorsa_11 = models.TextField(db_column='RISORSA 11', blank=True, null=True)
    risorsa_12 = models.TextField(db_column='RISORSA 12', blank=True, null=True)
    risorsa_13 = models.TextField(db_column='RISORSA 13', blank=True, null=True)
    risorsa_14 = models.TextField(db_column='RISORSA 14', blank=True, null=True)
    risorsa_15 = models.TextField(db_column='RISORSA 15', blank=True, null=True)
    risorsa_16 = models.TextField(db_column='RISORSA 16', blank=True, null=True)
    risorsa_17 = models.TextField(db_column='RISORSA 17', blank=True, null=True)
    risorsa_18 = models.TextField(db_column='RISORSA 18', blank=True, null=True)
    risorsa_19 = models.TextField(db_column='RISORSA 19', blank=True, null=True)
    risorsa_20 = models.TextField(db_column='RISORSA 20', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'PROGETTI'


class Soci(models.Model):
    class Sesso(models.TextChoices):
        M = 'M', 'M'
        F = 'F', 'F'
        NB = 'N.B.', 'N.B.'

    class Facolta(models.TextChoices):
        MEDICINA_PSICOLOGIA = 'Medicina e Psicologia', 'Medicina e Psicologia'
        ECONOMIA = 'Economia', 'Economia'
        INGEGNERIA_INFORMAZIONE = (
            "Ingegneria dell'informazione informatica e statistica",
            "Ingegneria dell'informazione informatica e statistica",
        )
        GIURISPRUDENZA = 'Giurisprudenza', 'Giurisprudenza'
        SCIENZE_POLITICHE = (
            'Scienze politiche sociologia e comunicazione',
            'Scienze politiche sociologia e comunicazione',
        )
        LETTERE = 'Lettere e Filosofia', 'Lettere e Filosofia'
        ARCHITETTURA = 'Architettura', 'Architettura'
        FARMACIA_MEDICINA = 'Farmacia e Medicina', 'Farmacia e Medicina'
        SCIENZE_MFN = (
            'Scienze Matematiche fisiche e naturali',
            'Scienze Matematiche fisiche e naturali',
        )
        INGEGNERIA_CIVILE = (
            'Ingegneria Civile e Industriale',
            'Ingegneria Civile e Industriale',
        )
        MATEMATICA = 'Matematica', 'Matematica'
        INGEGNERIA_ASTRONAUTICA = (
            'Ingegneria Astronautica, Elettrica ed Energetica',
            'Ingegneria Astronautica, Elettrica ed Energetica',
        )

    class Status(models.TextChoices):
        ASSOCIATO = 'Associato', 'Associato'
        IN_PROVA = 'Socio in prova', 'Socio in prova'
        ALUMNUS = 'Alumnus', 'Alumnus'
        USCITO = 'Uscito', 'Uscito'
        PROVA_NON_PASSATA = 'Periodo di prova non passato', 'Periodo di prova non passato'
        PROVA_TERMINATA = (
            'Periodo di prova terminato anticipatamente',
            'Periodo di prova terminato anticipatamente',
        )
        ALUMNUS_VALUTAZIONE = (
            'Alumnus in stato di valutazione',
            'Alumnus in stato di valutazione',
        )

    class Area(models.TextChoices):
        HR = 'HR', 'HR'
        BD = 'BD', 'BD'
        MC = 'M&C', 'M&C'
        LEGAL = 'Legal', 'Legal'
        AUDIT = 'Audit', 'Audit'
        DA = 'D&A', 'D&A'
        BOARD = 'Board', 'Board'

    class AnnoStudi(models.TextChoices):
        PRIMO_TRIENNALE = 'Primo Triennale', 'Primo Triennale'
        SECONDO_TRIENNALE = 'Secondo Triennale', 'Secondo Triennale'
        TERZO_TRIENNALE = 'Terzo Triennale', 'Terzo Triennale'
        PRIMO_MAGISTRALE = 'Primo Magistrale', 'Primo Magistrale'
        SECONDO_MAGISTRALE = 'Secondo Magistrale', 'Secondo Magistrale'
        LAUREATO = 'Laureato', 'Laureato'
        FUORI_CORSO = 'Fuori Corso', 'Fuori Corso'

    class Ruolo(models.TextChoices):
        SENIOR = 'Senior Consultant', 'Senior Consultant'
        JUNIOR = 'Junior Consultant', 'Junior Consultant'
        CONSULTANT = 'Consultant', 'Consultant'
        HEAD_OF = 'Head of', 'Head of'
        PRESIDENT = 'President', 'President'
        VICE_PRESIDENT = 'Vice President', 'Vice President'
        TREASURER = 'Treasurer', 'Treasurer'
        SECRETARY_GENERAL = 'Secretary General', 'Secretary General'
        INTERNATIONAL_MANAGER = 'International Manager', 'International Manager'

    _ACADEMIC_STATUS_MAP = {
        'Primo Triennale': 'Studente Triennale',
        'Secondo Triennale': 'Studente Triennale',
        'Terzo Triennale': 'Studente Triennale',
        'Primo Magistrale': 'Studente Magistrale',
        'Secondo Magistrale': 'Studente Magistrale',
        'Laureato': 'Laureato',
        'Fuori Corso': 'Fuori Corso',
    }

    _BOARD_STANDALONE_RUOLI = {
        'President', 'Vice President', 'Treasurer',
        'Secretary General', 'International Manager',
    }

    nome_e_cognome = models.TextField(db_column='NOME E COGNOME', blank=True, null=True)
    nome_1 = models.TextField(db_column='NOME 1', blank=True, null=True)
    nome_2 = models.TextField(db_column='NOME 2', blank=True, null=True)
    cognome = models.TextField(db_column='COGNOME', blank=True, null=True)
    sesso = models.TextField(db_column='SESSO', blank=True, null=True)
    data_di_nascita = models.TextField(db_column='DATA DI NASCITA', blank=True, null=True)
    email_jesap = models.TextField(db_column='EMAIL @jesap', blank=True, null=True)
    email_personale = models.TextField(db_column='EMAIL personale', blank=True, null=True)
    cellulare = models.TextField(db_column='CELLULARE', blank=True, null=True)
    ruolo_esteso = models.TextField(db_column='RUOLO ESTESO', blank=True, null=True)
    ruolo = models.TextField(db_column='RUOLO', blank=True, null=True)
    area_di_appartenenza = models.TextField(db_column='AREA DI APPARTENENZA', blank=True, null=True)
    status = models.TextField(db_column='STATUS', blank=True, null=True)
    data_inizio_prova = models.TextField(db_column='DATA INIZIO PROVA', blank=True, null=True)
    data_entrata = models.TextField(db_column='DATA ENTRATA', blank=True, null=True)
    data_uscita = models.TextField(db_column='DATA USCITA', blank=True, null=True)
    permanenza_mesi_field = models.BigIntegerField(db_column='PERMANENZA (mesi)', blank=True, null=True)
    facolta_field = models.TextField(db_column="FACOLTA'", blank=True, null=True)
    corso_di_studi = models.TextField(db_column='CORSO DI STUDI', blank=True, null=True)
    anno_di_studi = models.TextField(db_column='ANNO DI STUDI', blank=True, null=True)
    anno_di_studi_1 = models.TextField(db_column='ANNO DI STUDI_1', blank=True, null=True)
    pm = models.TextField(db_column='PM', blank=True, null=True)
    senior = models.TextField(db_column='SENIOR', blank=True, null=True)
    etα = models.TextField(db_column='ETÀ', blank=True, null=True)
    note = models.TextField(db_column='NOTE', blank=True, null=True)
    id = models.BigIntegerField(db_column='ID', primary_key=True)

    class Meta:
        managed = False
        db_table = 'SOCI'

    def _compute_nome_e_cognome(self):
        parts = [p.strip() for p in (self.nome_1, self.nome_2, self.cognome) if p and p.strip()]
        return ' '.join(parts) if parts else None

    def _compute_email_jesap(self):
        n1 = _slug_for_email(self.nome_1)
        cg = _slug_for_email(self.cognome)
        if not n1 or not cg:
            return None
        return f'{n1}.{cg}@jesap.it'

    def _compute_eta(self):
        bd = _parse_iso_date(self.data_di_nascita)
        if not bd:
            return None
        today = date.today()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))

    def _compute_permanenza_mesi(self):
        start = _parse_iso_date(self.data_entrata)
        if not start:
            return None
        end = _parse_iso_date(self.data_uscita) or date.today()
        months = (end.year - start.year) * 12 + (end.month - start.month)
        if end.day < start.day:
            months -= 1
        return max(months, 0)

    def _compute_academic_status(self):
        if not self.anno_di_studi:
            return None
        return self._ACADEMIC_STATUS_MAP.get(self.anno_di_studi, self.anno_di_studi)

    def _compute_ruolo_esteso(self):
        ruolo = (self.ruolo or '').strip()
        area = (self.area_di_appartenenza or '').strip()
        if not ruolo:
            return None
        if ruolo in self._BOARD_STANDALONE_RUOLI:
            return ruolo
        if ruolo == 'Head of' and area:
            return f'Head of {area}'
        if area:
            return f'{ruolo} {area}'
        return ruolo

    def save(self, *args, **kwargs):
        self.nome_e_cognome = self._compute_nome_e_cognome()
        self.email_jesap = self._compute_email_jesap()

        eta_val = self._compute_eta()
        self.etα = str(eta_val) if eta_val is not None else None

        self.permanenza_mesi_field = self._compute_permanenza_mesi()
        self.anno_di_studi_1 = self._compute_academic_status()
        self.ruolo_esteso = self._compute_ruolo_esteso()

        if self.id is None:
            last = Soci.objects.aggregate(m=Max('id'))['m']
            self.id = (last or 0) + 1

        super().save(*args, **kwargs)


class Socio(Soci):
    """Compat alias for code that imports `Socio`."""
    class Meta:
        proxy = True


class Partnership(models.Model):
    id = models.TextField(db_column='ID', primary_key=True)
    partnership = models.TextField(db_column='Partnership', blank=True, null=True)
    tipologia = models.TextField(db_column='Tipologia', blank=True, null=True)
    oggetto_primario = models.TextField(db_column='Oggetto primario della partnership', blank=True, null=True)
    status_partnership = models.TextField(db_column='Status partnership', blank=True, null=True)
    data_firma = models.TextField(db_column='Data firma', blank=True, null=True)
    anno = models.FloatField(db_column='ANNO', blank=True, null=True)
    durata = models.TextField(db_column='Durata', blank=True, null=True)
    rinnovo = models.TextField(db_column='Rinnovo', blank=True, null=True)
    data_ultimo_rinnovo = models.TextField(db_column='Data ultimo rinnovo', blank=True, null=True)
    data_fine_prevista = models.TextField(db_column='Data fine prevista', blank=True, null=True)
    numero_progetti = models.TextField(db_column='Numero di progetti prodotti dalle Partnership', blank=True, null=True)
    numero_partecipanti = models.TextField(db_column='Numero di partecipanti', blank=True, null=True)
    contatti = models.TextField(db_column='Contatti', blank=True, null=True)
    cartella_sul_drive = models.TextField(db_column='Cartella sul drive', blank=True, null=True)
    vantaggi_partner = models.TextField(db_column='Vantaggi partner', blank=True, null=True)
    compenso_economico = models.TextField(db_column='Compenso economico', blank=True, null=True)
    url_cartella_drive = models.TextField(db_column='Url cartella drive', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'PARTNERSHIP'  # Ho messo tutto minuscolo assumendo che su Supabase si chiami così


class PartnershipNonFin(models.Model):
    realta = models.TextField(db_column='Realtà', primary_key=True)
    contatti = models.TextField(db_column='Contatti', blank=True, null=True)
    periodo = models.TextField(db_column='Periodo', blank=True, null=True)
    anno = models.BigIntegerField(db_column='Anno', blank=True, null=True)
    cartella = models.TextField(db_column='Cartella', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'PARTNERSHIP_NON_FIN'


class AuditLog(models.Model):
    ACTION_CREATE = 'create'
    ACTION_UPDATE = 'update'
    ACTION_DELETE = 'delete'
    ACTION_CHOICES = [
        (ACTION_CREATE, 'Create'),
        (ACTION_UPDATE, 'Update'),
        (ACTION_DELETE, 'Delete'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='audit_logs',
    )
    user_repr = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=16, choices=ACTION_CHOICES)

    content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    object_pk = models.CharField(max_length=255, db_index=True)
    object_repr = models.CharField(max_length=255, blank=True)
    content_object = GenericForeignKey('content_type', 'object_pk')

    changes = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['content_type', 'object_pk']),
        ]

    def __str__(self):
        who = self.user_repr or 'anonymous'
        return f'[{self.timestamp:%Y-%m-%d %H:%M}] {who} {self.action} {self.object_repr}'
