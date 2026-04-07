from django.db import models


class Eventi(models.Model):
    id = models.TextField(db_column='ID', primary_key=True)  # Field name made lowercase.
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
    id = models.TextField(db_column='ID', primary_key=True)  # Field name made lowercase.
    nome = models.TextField(db_column='NOME', blank=True, null=True)  # Field name made lowercase.
    area = models.TextField(db_column='AREA', blank=True, null=True)  # Field name made lowercase.
    numero_partecipanti = models.BigIntegerField(db_column='Numero partecipanti', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    data = models.TextField(db_column='Data', blank=True, null=True)  # Field name made lowercase.
    durata_formazione_ore_field = models.TextField(db_column='Durata formazione (ore)', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    durata_formazione_ore_2 = models.TextField(db_column='Durata formazione (ore) 2', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    ente_erogante = models.TextField(db_column='Ente erogante', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    anno = models.BigIntegerField(db_column='ANNO', blank=True, null=True)  # Field name made lowercase.
    modalitα_di_erogazione = models.TextField(db_column='Modalità di erogazione', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    luogo_della_formazione = models.TextField(db_column='Luogo della formazione', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    erogata_in_un_evento_je = models.TextField(db_column='Erogata in un evento JE', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    processo_di_handover_onboarding = models.BooleanField(db_column='Processo di Handover/Onboarding', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    spese_della_formazione_senza_iva_field = models.TextField(db_column='Spese della Formazione (senza IVA)', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.

    class Meta:
        managed = False
        db_table = 'FORMAZIONI'


class Progetti(models.Model):
    codice_progetto = models.TextField(db_column='CODICE PROGETTO', primary_key=True, blank=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    nome_progetto = models.TextField(db_column='NOME PROGETTO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    cliente = models.TextField(db_column='CLIENTE', blank=True, null=True)  # Field name made lowercase.
    tipologia_cliente = models.TextField(db_column='TIPOLOGIA CLIENTE', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    tipologia_di_progetto = models.TextField(db_column='TIPOLOGIA DI PROGETTO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    stato = models.TextField(db_column='STATO', blank=True, null=True)  # Field name made lowercase.
    area_di_pertinenza = models.TextField(db_column='AREA DI PERTINENZA', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    pm = models.TextField(db_column='PM', blank=True, null=True)  # Field name made lowercase.
    provenienza = models.TextField(db_column='PROVENIENZA', blank=True, null=True)  # Field name made lowercase.
    data_primo_contatto = models.TextField(db_column='DATA PRIMO CONTATTO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    data_firma_contratto = models.TextField(db_column='DATA FIRMA CONTRATTO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    data_inizio = models.TextField(db_column='DATA INIZIO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    mese_inizio = models.BigIntegerField(db_column='MESE INIZIO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    data_fine_contratto = models.TextField(db_column='DATA FINE CONTRATTO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    anno = models.BigIntegerField(db_column='ANNO', blank=True, null=True)  # Field name made lowercase.
    n_risorse_coinvolte = models.BigIntegerField(db_column='N° RISORSE COINVOLTE', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    fatturato_senza_iva_field = models.TextField(db_column='Fatturato (senza IVA)', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    iva = models.TextField(db_column='IVA', blank=True, null=True)  # Field name made lowercase.
    costi = models.TextField(db_column='COSTI', blank=True, null=True)  # Field name made lowercase.
    profitti = models.TextField(db_column='PROFITTI', blank=True, null=True)  # Field name made lowercase.
    descrizione_servizio_offerto = models.TextField(db_column='DESCRIZIONE SERVIZIO OFFERTO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    coinvolgimento_della_pubblica_amministrazione = models.BooleanField(db_column='COINVOLGIMENTO DELLA Pubblica Amministrazione', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    soddisfazione_team_in_field = models.TextField(db_column='SODDISFAZIONE TEAM (in %%)', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    soddisfazione_cliente_in_field = models.TextField(db_column='SODDISFAZIONE CLIENTE (in %%)', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    risorsa_1 = models.TextField(db_column='RISORSA 1', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_2 = models.TextField(db_column='RISORSA 2', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_3 = models.TextField(db_column='RISORSA 3', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_4 = models.TextField(db_column='RISORSA 4', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_5 = models.TextField(db_column='RISORSA 5', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_6 = models.TextField(db_column='RISORSA 6', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_7 = models.TextField(db_column='RISORSA 7', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_8 = models.TextField(db_column='RISORSA 8', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_9 = models.TextField(db_column='RISORSA 9', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_10 = models.TextField(db_column='RISORSA 10', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_11 = models.TextField(db_column='RISORSA 11', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_12 = models.TextField(db_column='RISORSA 12', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_13 = models.TextField(db_column='RISORSA 13', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_14 = models.TextField(db_column='RISORSA 14', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_15 = models.TextField(db_column='RISORSA 15', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_16 = models.TextField(db_column='RISORSA 16', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_17 = models.TextField(db_column='RISORSA 17', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_18 = models.TextField(db_column='RISORSA 18', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_19 = models.TextField(db_column='RISORSA 19', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    risorsa_20 = models.TextField(db_column='RISORSA 20', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.

    class Meta:
        managed = False
        db_table = 'PROGETTI'


class Soci(models.Model):
    nome_e_cognome = models.TextField(db_column='NOME E COGNOME', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    nome_1 = models.TextField(db_column='NOME 1', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    nome_2 = models.TextField(db_column='NOME 2', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    cognome = models.TextField(db_column='COGNOME', blank=True, null=True)  # Field name made lowercase.
    sesso = models.TextField(db_column='SESSO', blank=True, null=True)  # Field name made lowercase.
    data_di_nascita = models.TextField(db_column='DATA DI NASCITA', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    email_jesap = models.TextField(db_column='EMAIL @jesap', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    email_personale = models.TextField(db_column='EMAIL personale', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    cellulare = models.TextField(db_column='CELLULARE', blank=True, null=True)  # Field name made lowercase.
    ruolo_esteso = models.TextField(db_column='RUOLO ESTESO', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    ruolo = models.TextField(db_column='RUOLO', blank=True, null=True)  # Field name made lowercase.
    area_di_appartenenza = models.TextField(db_column='AREA DI APPARTENENZA', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    status = models.TextField(db_column='STATUS', blank=True, null=True)  # Field name made lowercase.
    data_inizio_prova = models.TextField(db_column='DATA INIZIO PROVA', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    data_entrata = models.TextField(db_column='DATA ENTRATA', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    data_uscita = models.TextField(db_column='DATA USCITA', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    permanenza_mesi_field = models.BigIntegerField(db_column='PERMANENZA (mesi)', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    facolta_field = models.TextField(db_column="FACOLTA'", blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters. Field renamed because it ended with '_'.
    corso_di_studi = models.TextField(db_column='CORSO DI STUDI', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    anno_di_studi = models.TextField(db_column='ANNO DI STUDI', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    anno_di_studi_1 = models.TextField(db_column='ANNO DI STUDI_1', blank=True, null=True)  # Field name made lowercase. Field renamed to remove unsuitable characters.
    pm = models.TextField(db_column='PM', blank=True, null=True)  # Field name made lowercase.
    senior = models.TextField(db_column='SENIOR', blank=True, null=True)  # Field name made lowercase.
    etα = models.TextField(db_column='ETÀ', blank=True, null=True)  # Field name made lowercase.
    note = models.TextField(db_column='NOTE', blank=True, null=True)  # Field name made lowercase.
    id = models.BigIntegerField(db_column='ID', primary_key=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'SOCI'


class Socio(Soci):
    """Compat alias for code that imports `Socio`."""

    class Meta:
        proxy = True
