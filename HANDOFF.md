# HANDOFF — JESAP CRM (stato al 15/10/2026)

Documento di passaggio consegne. Da leggere insieme a `README.md` (architettura, setup, variabili) e `CLAUDE.md` (regole per l'agente).
Le chat precedenti **non servono**: tutto ciò che contava è riassunto qui o è nella storia git.

---

## 0. Come funziona — spiegato da zero

```
                 ┌──────────── GitHub (codice) ────────────┐
                 │  JesapIt/jesap-CRM  ← PR ←  fork tuo     │
                 └───────────────────┬──────────────────────┘
                                     │ deploy automatico
 utente ──https──► crm.jesap.it ──► RAILWAY (gira Django) ──► RESEND (manda email)
                   (DNS Aruba)               │
                                             ▼
 Google Sheets ◄──── sync doppio ────► SUPABASE (database Postgres)
 (Foglio Soci, DB Partnership)               ▲
 Form "Join Us" del sito ──► Sheet risposte ─┘ (via CRM, ogni 5 min)
```

**Django (il CRM vero e proprio)**
- È il codice del sito: pagine, login, permessi, form. Sta tutto in `dashboard/` (logica in `views.py`, tabelle in `models.py`, HTML in `templates/`).
- Non salva dati in locale: legge e scrive sul database Supabase.
- In locale, senza `.env`, usa un database finto (`db.sqlite3`) e stampa le email nel terminale: puoi rompere tutto senza toccare i dati veri.

**Supabase (il database)**
- È un database PostgreSQL in cloud, con un pannello web (Table Editor, SQL Editor). Progetto: **Gestionale**.
- Due tipi di tabelle:
  - **condivise con i fogli Google** (`SOCI`, `PARTNERSHIP`, `LEADS`, `PROGETTI`, `EVENTI`, `FORMAZIONI`): Django le usa ma non ne cambia mai la struttura (`managed=False`). Si modificano a mano su Supabase con script SQL.
  - **del CRM** (`auth_user` per gli account, `TASKS`, `CREDENZIALI`, `REC_*` per il recruitment, `django_*`): le crea e aggiorna Django con le migrations, lanciate in automatico a ogni deploy.
- Django si collega con `DATABASE_URL` (connessione Postgres diretta). Gli script Google si collegano con la REST API di Supabase e la chiave `service_role`, che bypassa ogni permesso: non deve mai finire in chiaro da nessuna parte.

**Railway (il server)**
- È dove il sito gira 24/7. Prende il codice da GitHub e, a ogni push sul branch collegato, ricostruisce e riavvia (`railway.json`: `collectstatic` → `migrate` → `gunicorn`). Controlla in Railway → *Settings → Source* quale repo e branch sono collegati.
- Le **Variables** di Railway sono i segreti di produzione (chiavi, URL del DB, mittente email). Il codice le legge in `setup/settings.py`.
- I **Deploy Logs** sono il primo posto dove guardare quando qualcosa non va: all'avvio stampano quale DB e quale backend email sono in uso.
- `crm.jesap.it` punta a Railway grazie a un record CNAME nel DNS di Aruba.

**Sync doppio Google Sheets ↔ Supabase**
- Perché esiste: l'associazione lavora ancora sui fogli Google, il CRM lavora su Supabase. Il sync tiene le due copie uguali, così ognuno usa lo strumento che preferisce.
- **Foglio → Supabase**: un Apps Script attaccato al foglio parte a ogni modifica (trigger `onEdit`/`onChange`) e aggiorna la riga su Supabase via REST (prova un update, se la riga non esiste la crea).
- **Supabase → Foglio**: un *Database Webhook* di Supabase, a ogni insert, update o delete, chiama l'URL della Web App dello script (`doPost?secret=…`), che riscrive la riga sul foglio.
- **Anti-loop**: quando la scrittura arriva da Supabase, lo script alza un flag (`_sb_writing`) per non rimandarla indietro all'infinito.
- Tabelle coperte: **SOCI** (`integrations/sheets_supabase_sync/Code.gs`, tab "Soci total", intestazioni in riga 5) e **PARTNERSHIP** (`PartnershipCode.gs`, guida passo-passo in `PARTNERSHIP_SETUP.md`). **LEADS**: lo schema è pronto (`LEADS_SCHEMA.sql`), lo script di sync non è nel repo.
- ⚠️ La direzione Supabase → Foglio per SOCI era bloccata: Google rispondeva 401 perché il Workspace JESAP non permette Web App aperte a "Chiunque". La soluzione scelta era pubblicare la Web App da un Gmail personale (dettagli in `CONTEXT.md`). Lo stato attuale **va verificato**: in SQL Editor `select status_code, created from net._http_response order by created desc limit 20;` → deve dare 200.
- `sync/soci_apps_script.js` e `sync/soci_sync.py` sono la versione vecchia (tab sbagliato `SOCI`). Quella buona è `integrations/sheets_supabase_sync/Code.gs`.

**Recruitment (candidature dal sito)**
- Il form "Join Us" del sito scrive su un Google Sheet. Uno script su quel foglio, ogni 5 minuti, manda le righe nuove a `crm.jesap.it/recruitment/api/candidature/`, protetto dal token `RECRUITMENT_WEBHOOK_TOKEN`.
- Il CRM salva il candidato nella sessione di recruitment aperta e, se attivo, gli manda l'email di conferma via Resend. Guida: `integrations/recruitment_form_sync/SETUP.md`.

**Email, dominio e posta**
- `jesap.it` è registrato su **Aruba**, che gestisce il DNS: decide dove punta `crm.jesap.it` e chi è autorizzato a mandare email a nome del dominio.
- Le caselle `@jesap.it` stanno su **Google Workspace** (ricevono la posta).
- Il CRM **manda** le email tramite **Resend**, con una chiamata HTTP invece dell'SMTP, che Railway blocca. Per farlo a nome di `@jesap.it`, Resend deve vedere i suoi record nel DNS di Aruba: è proprio il bug della sezione 2.

**Come si lavora sul codice**
- Si lavora sul fork, su un branch dedicato, e si apre una PR verso `JesapIt/jesap-CRM`. Railway pubblica solo quello che finisce sul branch collegato.
- In locale: `python manage.py runserver` per avviare il sito, `pytest` per i test (408 test; usano un database in memoria e non toccano mai Supabase).

---

## 1. Contesto rapido

| Cosa | Dove |
|---|---|
| Codice | Django 4.2 (Python 3.12 su Railway), app unica `dashboard/` |
| DB | Supabase Postgres, progetto **Gestionale** (`qftmtaifcuuhlarponmr`, eu-central-1). Tabelle legacy `managed=False` (`SOCI`, `LEADS`, `PARTNERSHIP`, …) — **non creare tabelle nuove** |
| Hosting | Railway → `https://crm.jesap.it` (CNAME `bnmrcbm9.up.railway.app`) |
| Email | Resend via `django-anymail` (HTTP API) — config in `setup/settings.py:247-262` |
| DNS `jesap.it` | Aruba (nameserver `dns*.arubadns.*` / `technorail.com`). Posta in arrivo su Google Workspace (`MX smtp.google.com`) |
| Repo | `upstream` = `JesapIt/jesap-CRM` (ufficiale), `origin` = fork `daniteg71/jesap-CRM` |
| Test | `pytest` → 408 passati, nessun fallimento |
| Branch aperto | `feat/candidature-sito-supabase`: 1 commit (`cc8be91`) avanti rispetto a `upstream/main`, manca la PR |

---

## 2. BUG PRINCIPALE — le email di accesso non arrivano

Riguarda: registrazione (`/register/`), reset password (`/password-reset/`), email di benvenuto, email recruitment ai candidati.

### 2.1 Causa (verificata)

**Il dominio `jesap.it` non è verificato su Resend.** Resend invia solo da domini con record DNS (DKIM + SPF) pubblicati. Senza:

- mittente `noreply@jesap.it` → Resend risponde **403 "domain is not verified"** (già visto: commit `7b23568`);
- mittente di ripiego `onboarding@resend.dev` (default del codice quando `DEFAULT_FROM_EMAIL` è vuota) → Resend consegna **solo all'indirizzo del proprietario dell'account Resend**: qualunque `nome.cognome@jesap.it` riceve un 403 "You can only send testing emails to your own email address".

Quindi, comunque sia impostato oggi il mittente su Railway, nessun socio riceve le email.

Prova DNS (controllata il 15/10/2026 con `dig`):

```
resend._domainkey.jesap.it  TXT  → (vuoto)      ← manca DKIM Resend
send.jesap.it               MX   → (vuoto)      ← manca return-path Resend
send.jesap.it               TXT  → (vuoto)      ← manca SPF Resend
jesap.it                    TXT  → "v=spf1 include:_spf.aruba.it ~all"
_dmarc.jesap.it             TXT  → "v=DMARC1; p=none; adkim=r; aspf=r;"
jesap.it                    MX   → smtp.google.com
```

### 2.2 Perché la "mail proxy" `noreply@jesap.it` non basta

Cronologia ricostruita dalle chat:
1. Inizio: SMTP Gmail con la casella Workspace `noreply@jesap.it` + app password (`EMAIL_HOST`, `EMAIL_HOST_USER`, …).
2. Railway blocca l'SMTP in uscita sui piani non-Pro → migrazione a Resend (commit `5999c0b`).
3. Resend 403 perché `jesap.it` non verificato → mittente cambiato in `onboarding@resend.dev` (commit `7b23568`), che però consegna solo al proprietario dell'account.

Per Resend **non conta che la casella `noreply@jesap.it` esista**: conta solo che il **dominio** sia verificato via DNS. Inoltre il codice attuale **non legge più** `EMAIL_HOST*`: se quelle variabili sono ancora su Railway sono ignorate.

### 2.3 Come si presenta all'utente (riprodotto con un test che simula il 403)

| Flusso | Cosa vede l'utente | Cosa succede davvero |
|---|---|---|
| Reset password | Pagina "email inviata" ✅ | Errore inghiottito da Django: nei log solo `ERROR django.contrib.auth: Failed to send password reset email to <id>` |
| Registrazione | "Errore tecnico con il server di posta" | Eccezione loggata (`Invio email di registrazione fallito`) |
| Benvenuto | Niente | `fail_silently=True`: nessuna traccia |
| `RESEND_API_KEY` assente su Railway | Messaggi di successo ovunque | Backend `console`: le email finiscono nei log di Railway, non partono |

Nota: in Django 4.2 `PasswordResetForm.send_mail` cattura già le eccezioni e le logga. Il `try/except` in `CustomPasswordResetView.form_valid` (`dashboard/views.py:299`) quindi **non scatta mai**.

---

## 3. COSA FARE

### Fix A — infrastruttura (OBBLIGATORIO, zero codice)

Serve accesso a: account **Resend**, pannello DNS **Aruba** di `jesap.it`, progetto **Railway**.

1. **Resend → Domains → Add Domain** → `jesap.it`, region EU (va bene anche un sottodominio dedicato tipo `mail.jesap.it`: in quel caso il mittente diventa `noreply@mail.jesap.it`).
2. **Aruba → Gestione DNS di jesap.it** → aggiungi i record che mostra Resend, **copiando i valori esatti dalla dashboard** (dipendono dalla region). Tipicamente:
   - `TXT  resend._domainkey` → chiave DKIM lunga (`p=MIGf…`)
   - `MX   send` → `feedback-smtp.<region>.amazonses.com`, priorità 10
   - `TXT  send` → `v=spf1 include:amazonses.com ~all`
   
   Non toccare l'MX di `jesap.it` (Google) né l'SPF della root: i record Resend stanno sul sottodominio `send`, non creano conflitti.
3. Resend → **Verify** → attendi stato *Verified* (minuti / qualche ora di propagazione). Verifica: `dig +short TXT resend._domainkey.jesap.it`.
4. **Railway → Variables**:
   - `RESEND_API_KEY` = chiave Resend con permesso *Sending access*
   - `DEFAULT_FROM_EMAIL` = `JESAP CRM <noreply@jesap.it>`
   - `SITE_URL` = `https://crm.jesap.it`
   - opzionali: `RECRUITMENT_FROM_EMAIL`, `RECRUITMENT_REPLY_TO`
   - **elimina** `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_BACKEND` (morte; l'app password Gmail va revocata in Google Workspace)
5. Redeploy. Nei Deploy Logs deve comparire:
   ```
   [settings:email] backend=anymail.backends.resend.EmailBackend resend_key=<SET> from=JESAP CRM <noreply@jesap.it>
   ```
6. Test reale (shell Railway o `railway run`):
   ```bash
   python manage.py send_test_email nome.cognome@jesap.it
   ```
   Poi prova `/password-reset/` con un account esistente e controlla Resend → **Logs** (stato *Delivered*).

Limiti piano gratuito Resend: 100 email/giorno, 3.000/mese. L'invio in blocco del recruitment (40 per click) può saturare la quota giornaliera.

### Fix B — codice (CONSIGLIATO: rendere visibili i fallimenti)

1. **Reset password — errore inghiottito.** In `CaseInsensitivePasswordResetForm` (`dashboard/forms.py:908`) sovrascrivere `send_mail` per loggare con dettaglio (tipo errore, risposta Resend) invece del log generico di Django. Lato utente mantenere il messaggio generico (anti-enumerazione: un errore visibile rivelerebbe che l'account esiste). Rimuovere o correggere il `try/except` morto in `CustomPasswordResetView`.
2. **Email di benvenuto** (`dashboard/signals.py:36`): sostituire `fail_silently=True` con `try/except` + `logger.exception(...)`.
3. **Guardia in produzione** (`setup/settings.py:252-258`): se `ON_RAILWAY` e `RESEND_API_KEY` vuota → warning forte (o `ImproperlyConfigured`), invece di passare in silenzio al backend console. Stesso warning se `DEFAULT_FROM_EMAIL` termina con `@resend.dev`.
4. **Allineare il default**: `.env.example` e README dicono `noreply@jesap.it`, `settings.py` usa `onboarding@resend.dev`. Una volta verificato il dominio, default = `JESAP CRM <noreply@jesap.it>`.
5. Test: aggiungere in `dashboard/tests/test_login.py` un caso che simula il fallimento di `EmailMultiAlternatives.send` su reset/registrazione e verifica log + messaggio.

### Fix C — controlli dati (motivi "silenziosi" per cui una mail non parte anche dopo il Fix A)

Per design anti-enumerazione questi casi mostrano un messaggio generico e **non inviano nulla**:

- **Registrazione**: l'email inserita deve coincidere (case-insensitive) con `SOCI."EMAIL @jesap"`. Quel campo è calcolato come `nome_1.cognome@jesap.it` (slug) da `Soci.save()`, ma le righe sincronizzate dal Google Sheet possono averlo vuoto o diverso dall'indirizzo Workspace reale (secondo nome, doppio cognome, apostrofi).
- **Registrazione**: se esiste già un `User` con quell'email → niente mail, va usato "Password dimenticata".
- **Reset password**: serve un `User` con quell'email, `is_active=True` e password utilizzabile.

Query di controllo da lanciare su Supabase (SQL editor):

```sql
select
 (select count(*) from "SOCI") as soci_tot,
 (select count(*) from "SOCI" where coalesce(trim("EMAIL @jesap"),'')='') as soci_senza_email_jesap,
 (select count(*) from auth_user) as users_tot,
 (select count(*) from auth_user where coalesce(email,'')='') as users_senza_email,
 (select count(*) from auth_user where password like '!%') as users_password_inutilizzabile,
 (select count(*) from auth_user where not is_active) as users_inattivi;
```

Infine: se le mail arrivano ma finiscono in spam su Gmail, controllare in Resend che DKIM sia *Verified* (con `adkim=r` del DMARC attuale l'allineamento è ok).

---

## 4. Checklist di chiusura

- [ ] `jesap.it` *Verified* su Resend
- [ ] Variabili Railway aggiornate, `EMAIL_HOST*` rimosse, app password Gmail revocata
- [ ] Log di avvio con `backend=anymail…resend` e `from=…@jesap.it`
- [ ] `send_test_email` consegnata a un indirizzo `@jesap.it` diverso dal proprietario Resend
- [ ] Reset password e registrazione provati end-to-end su `crm.jesap.it`
- [ ] Fix B in PR verso `JesapIt/jesap-CRM` con test
- [ ] PR per `feat/candidature-sito-supabase` (commit `cc8be91`)

## 5. Accessi da passare (fuori da chat e repo)

Account Resend, pannello DNS Aruba di `jesap.it`, progetto Railway, progetto Supabase *Gestionale*, permesso di scrittura su `JesapIt/jesap-CRM`. Le chiavi (`RESEND_API_KEY`, `CREDENTIALS_ENCRYPTION_KEY`, `RECRUITMENT_WEBHOOK_TOKEN`, `DATABASE_URL`) vanno condivise con un password manager, mai incollate in chat o nel repo.
