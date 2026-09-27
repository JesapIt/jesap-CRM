"""Compatibilità con il form del NUOVO sito (nuo/google-apps-script/Codice.gs).

Il foglio "Candidature" del sito ha intestazioni diverse dal vecchio Google Form
(es. "Data invio", "Prima Area di preferenza", colonna "CV" col link Drive e
"Curriculum" come testo libero). RecruitmentSync.gs manda le date come ISO UTC.
"""
from dashboard.recruitment.intake import mappa_risposta

# Una riga del foglio "Candidature" come la invia RecruitmentSync.gs
SITO_ROW = {
    'Data invio': '2026-10-06T08:15:00.000Z',
    'Email': 'Giulia.Neri@Example.com',
    'Nome': 'Giulia',
    'Cognome': 'Neri',
    'Data di nascita': '2004-05-12',
    'N. Telefono': '+39 333 1234567',
    'Residenza': 'Via Roma 1, Roma',
    'Domicilio': 'Via Milano 2, Roma',
    'Ateneo': 'Sapienza',
    'Facoltà': 'Economia',
    'Corso di laurea': 'Management',
    'Curriculum': 'Finanza',
    'Anno di frequenza': '2º anno',
    'Prima Area di preferenza': 'Data & Automation',
    'Seconda Area di preferenza': 'Human Resources',
    'Motivazione aree': 'Mi piacciono i dati',
    'Come hai conosciuto JESAP': 'Online',
    'Fonte': 'Social Media',
    'Perché vuoi entrare in JESAP': 'Per crescere',
    'Conosci associati JESAP': 'No',
    'Conosci network JE Italy': 'Sì',
    'CV': 'https://drive.google.com/file/d/abc/view',
}


def test_sito_data_invio_diventa_data_candidatura():
    campi, _ = mappa_risposta(SITO_ROW)
    # 08:15 UTC = 10:15 ora di Roma (ora legale)
    assert campi['data_candidatura'].isoformat().startswith('2026-10-06T08:15')


def test_sito_aree_di_preferenza():
    campi, _ = mappa_risposta(SITO_ROW)
    assert (campi['area_1'], campi['area_2']) == ('D&A', 'HR')


def test_sito_cv_viene_dal_link_drive_non_dal_testo_curriculum():
    campi, altre = mappa_risposta(SITO_ROW)
    assert campi['cv_url'] == 'https://drive.google.com/file/d/abc/view'
    assert altre['Curriculum'] == 'Finanza'


def test_sito_motivazione_e_je_italy():
    campi, altre = mappa_risposta(SITO_ROW)
    assert campi['motivazione'] == 'Per crescere'
    assert campi['conosce_je_italy'] == 'Sì'
    assert altre['Motivazione aree'] == 'Mi piacciono i dati'


def test_sito_fonte_unisce_canale_e_dettaglio():
    campi, _ = mappa_risposta(SITO_ROW)
    assert campi['fonte'] == 'Online – Social Media'


def test_vecchio_form_curriculum_link_resta_cv():
    campi, _ = mappa_risposta({'Indirizzo di mail': 'a@b.it', 'Nome': 'A', 'Curriculum': 'https://drive.google.com/x'})
    assert campi['cv_url'] == 'https://drive.google.com/x'
