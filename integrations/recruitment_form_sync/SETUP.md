# Sync candidature: form del sito → Google Sheet → CRM

> **Nuovo sito (form Join Us su jesap.it):** l'invio al CRM è già integrato nello script
> del sito (`Codice.gs`, funzioni `sincronizzaCrm` / `installaCollegamentoCrm`, colonna
> "CRM" nel foglio). `RecruitmentSync.gs` qui sotto serve solo per un foglio risposte di
> **Google Form** classico: non installarli entrambi sullo stesso foglio.

Il form sul sito continua a scrivere sul Google Sheet delle risposte (nessuna modifica al sito).
Uno script sul foglio invia ogni 5 minuti le righe nuove al CRM, che le salva nella **sessione aperta**
e (se attivo) manda al candidato l'email di conferma ricezione.

## 1. Railway
Aggiungi la variabile `RECRUITMENT_WEBHOOK_TOKEN` (stringa casuale lunga):
```
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Opzionali: `RECRUITMENT_FROM_EMAIL` (mittente) e `RECRUITMENT_REPLY_TO` (dove arrivano le risposte dei candidati).

## 2. CRM
Recruitment → **+ Nuova sessione** (es. *Spring REC 26*) con "Sessione aperta" attivo.
In **Impostazioni ed email** sostituisci i testi *di esempio* con quelli usati oggi in Make.

## 3. Google Sheet delle risposte
Apri il foglio dove il form scrive le risposte → **Estensioni → Apps Script** → incolla `RecruitmentSync.gs`.

⚙️ **Impostazioni progetto → Proprietà script**:

| Chiave | Valore |
|---|---|
| `CRM_URL` | `https://crm.jesap.it/recruitment/api/candidature/` |
| `CRM_TOKEN` | stesso valore di `RECRUITMENT_WEBHOOK_TOKEN` |
| `SHEET_NAME` | nome del tab con le risposte |
| `HEADER_ROW` | riga delle intestazioni (di solito `1`) |

Esegui una volta, nell'ordine:
1. `testConnessione` → deve stampare `✓ OK`
2. `syncTutto` → invia le risposte già presenti (solo se vuoi importarle nella sessione aperta)
3. `installaTrigger` → da qui in poi è automatico

## Note
- **Intestazioni**: il CRM riconosce le colonne per nome (es. "Indirizzo di mail", "Nome", "Area 1", "Curriculum"…)
  ignorando maiuscole e accenti. Colonne sconosciute finiscono in "Altre risposte" nella scheda del candidato.
- **Doppioni**: stessa email già candidata nella sessione → nuova riga con esito screening "Doppione".
- **Nessuna sessione aperta**: il CRM risponde 409 e lo script riprova al giro successivo (nessuna riga persa).
- **Log**: Apps Script → *Esecuzioni*. Nel CRM ogni email inviata è nella scheda del candidato.
- **Import manuale** (alternativa allo script): esporta il tab in CSV e lancia
  `python manage.py import_candidature risposte.csv --sessione "Spring REC 26"`.
