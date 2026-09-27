# Contesto sync Sheets ↔ Supabase — per nuova conversazione

## Obiettivo
Sync bidirezionale event-driven tra Google Sheet **"[00] Foglio Soci"** (tab `Soci total`) e tabella Supabase **`SOCI`**. Django (CRM) è un consumer della tabella Supabase ma NON deve essere nel path del sync (può essere off, il sync deve continuare).

## Identificatori chiave
- **Sheet ID**: `1PE8sPI1ZMgWjCYBPEQPs-l795mrDwnu21qoR0IRtR2U`
- **Sheet tab**: `Soci total` (header riga **5**, dati da riga **6**)
- **Supabase project ref**: `qftmtaifcuuhlarponmr`
- **Tabella**: `SOCI` (primary key: colonna `ID`, BigInt)
- **Account Google utente**: `daniele.tegliucci@jesap.it` (Workspace JESAP Consulting)
- **Progetto Django**: `/Users/dannydogthoot/jesap-CRM/` — usa Supabase Postgres via `DATABASE_URL`, modello `Soci` in `dashboard/models.py` (managed=False, tutti TextField tranne ID e PERMANENZA (mesi))

## Architettura scelta
- **Sheet → Supabase**: Apps Script trigger `onEdit`/`onChange` → chiamate PostgREST (PATCH-then-POST, non upsert `on_conflict`)
- **Supabase → Sheet**: Supabase Database Webhook (pg_net) → Apps Script Web App `doPost` → scrive sullo Sheet
- Anti-loop: flag `_sb_writing` in PropertiesService (impedisce che le scritture webhook ri-triggerino upload)

## File creati nel repo
Path: `integrations/sheets_supabase_sync/`
- `Code.gs` — script completo Apps Script (sync bidirezionale + `recordAssociatiEndOfMonth` + `testConnection` + `testUpsertUpdate` + `testDateFormat` + `initialPushSheetToSupabase`)
- `SETUP.md` — guida deployment 7 step
- `CONTEXT.md` — questo file

## Bug fixati durante la sessione
1. `SHEET_TAB` era `"SOCI"`, corretto a `"Soci total"`
2. Header era su riga 1, corretto a riga 5 (`HEADER_ROW=5`, `DATA_START=6`)
3. PM/SENIOR checkbox: conversione bool↔"TRUE"/"FALSE" stringa (DB è TextField)
4. ID/PERMANENZA: coerce int (`parseInt`)
5. **Upsert creava duplicati** invece di update: cambiato da `POST ?on_conflict=ID` con `Prefer: resolution=merge-duplicates` a **PATCH-first, POST-if-empty** (più robusto, indipendente da vincoli UNIQUE)
6. **Date distorte**: Google Sheets auto-converte celle date in oggetti JS Date, `String(d)` produceva `"Mon May 08 2022..."`. Fix: rilevare `Date` e riformattare `DD/MM/YYYY`

## Stato attuale sync

### ✅ Sheet → Supabase (funziona)
Trigger installati, `testConnection` OK, modifiche sul sheet si propagano a Supabase.

### ❌ Supabase → Sheet (BLOCCATO)
Query diagnostica:
```sql
select id, created, status_code, content::text, error_msg
from net._http_response order by created desc limit 20;
```
Risultato: **tutti 401** con HTML di Google → il webhook arriva ad Apps Script ma Google blocca PRIMA che `doPost` venga eseguito.

**Causa radice identificata**: deployment Web App ha impostazioni sbagliate:
- "Esegui come": `Utente che accede all'applicazione web` (va su `Me`)
- "Utenti autorizzati": `Chiunque abbia un Account Google` (Supabase non ha account Google → 401)

**Blocco Workspace**: quando abbiamo tentato di cambiare "Utenti autorizzati" a **"Chiunque"** (Anyone, no account), l'admin Workspace JESAP ha disabilitato questa opzione. Opzioni disponibili sul deploy:
- Solo io
- Chiunque all'interno di JESAP Consulting
- Chiunque abbia un Account Google

Nessuna permette l'accesso anonimo richiesto dal webhook Supabase.

## Prossimo step scelto: OPZIONE 1 (Gmail personale)
User ha scelto la strada più veloce: creare il Web App da un account Gmail personale (non Workspace), che ha l'opzione "Chiunque" disponibile.

### Piano operativo
1. **User**: condivide lo Sheet con il suo gmail personale (ruolo **Editor**)
2. **User**: login Chrome (incognito o nuovo profilo) con account gmail personale
3. **Agent**: crea nuovo progetto Apps Script standalone dall'account personale
4. **Agent**: incolla `Code.gs` (da `integrations/sheets_supabase_sync/Code.gs`)
5. **User**: fornisce valori per le 3 Script Properties:
   - `SUPABASE_URL` = `https://qftmtaifcuuhlarponmr.supabase.co`
   - `SUPABASE_KEY` = (service_role key, da Supabase → Settings → API)
   - `WEBHOOK_SECRET` = (secret random, già generato — fargli aprire il vecchio progetto per copiarlo)
6. **Agent**: Esegue `testConnection` → deve dire `✓ OK`
7. **Agent**: Esegue `setupTriggers` (installerà trigger sullo Sheet condiviso)
8. **Agent**: Deploy → Web App → Esegui come **Me** (gmail personale) + Accesso **Chiunque**
9. **Agent**: Copia nuovo URL Web App
10. **User**: aggiorna URL nel webhook Supabase (`Database → Webhooks → soci_to_sheet → Edit` → URL nuovo + `?secret=<WEBHOOK_SECRET>`)
11. **Verifica**: modifica una cella su Supabase → dopo 5s compare nello Sheet + `net._http_response` mostra `status_code=200`

### Alternativa futura (opzione 3, più pulita)
Quando si vuole togliere la dipendenza da un Gmail personale:
- Creare Service Account su Google Cloud
- Condividere lo Sheet con l'email del Service Account
- Scrivere una **Supabase Edge Function** (Deno) che riceve il webhook e chiama Google Sheets API direttamente
- Riconfigurare webhook Supabase sull'URL della Edge Function

## Info utili per continuare

### Credenziali di servizio
- `SUPABASE_URL`: `https://qftmtaifcuuhlarponmr.supabase.co`
- `SUPABASE_KEY`: chiedi al user (service_role, mai anon)
- `WEBHOOK_SECRET`: salvato nelle Script Properties del progetto "Raccolta dati associati" (account Workspace) — vecchio URL webhook è `https://script.google.com/a/macros/jesap.it/s/AKfycbwcFor08hBLGd9FihaOMuNjhzYvOPsml8t3uk9zgwEYJxZn2h0HNq.../exec?secret=<WEBHOOK_SECRET>`

### Webhook Supabase attuale
- Nome: `soci_to_sheet`
- Eventi: INSERT, UPDATE, DELETE su tabella `SOCI`
- URL attuale: punta al Web App del progetto Workspace (→ 401)
- Da aggiornare post-deploy con nuovo URL del progetto gmail personale

### Modello Django rilevante (dashboard/models.py linee 107-138)
Tabella `SOCI`, managed=False, 26 campi, PK `ID` BigIntegerField, tutti gli altri TextField tranne `PERMANENZA (mesi)` BigInteger.

### Tool environment
- Repo path: `/Users/dannydogthoot/jesap-CRM/.claude/worktrees/adoring-matsumoto-e94a1e/`
- Claude in Chrome MCP disponibile — permette navigazione e click diretto nel browser
- Computer-use MCP disponibile (tier "read" per Chrome, usare Chrome MCP per interazioni)

### Non fare
- Non tentare di riabilitare "Chiunque" su deployment Workspace (admin ha disabilitato)
- Non riscrivere il `Code.gs` — la logica PATCH→POST e la gestione date/bool è corretta
- Non toccare Django per il sync (non deve essere in path)
