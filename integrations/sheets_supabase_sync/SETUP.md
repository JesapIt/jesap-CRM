# Sync bidirezionale Sheet "Soci total" ↔ Supabase SOCI

L'automazione **non dipende da Django**: Supabase Database Webhook scatta su qualunque modifica della tabella SOCI (sito Django, SQL editor, API, psql, …) e chiama il Web App Apps Script. Analogamente Sheets→Supabase passa diretto via PostgREST. Django può essere off.

## 1. Incolla il codice
Sheet → **Estensioni → Apps Script** → incolla l'intero `Code.gs` di questa cartella, salva.

## 2. Script properties
⚙️ **Project Settings → Script properties**:
| key | value |
|---|---|
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_KEY` | **service_role** key (Supabase → Settings → API) — NON anon |
| `WEBHOOK_SECRET` | stringa random (es. `openssl rand -hex 24`) |

## 3. Verifica credenziali
Esegui `testConnection`. Deve stampare `✓ OK — trovate N righe in Supabase SOCI`.

## 4. Installa i trigger
Esegui `setupTriggers` una volta. Installa:
- `onSheetEdit` (On edit) — Sheet→Supabase upsert
- `onSheetChange` (On change) — Sheet→Supabase delete
- `recordAssociatiEndOfMonth` — daily 23:00

Alla prima esecuzione Google chiede permessi Sheets + external request → autorizza.

## 5. Deploy Web App (Supabase→Sheet)
**Distribuisci → Nuova distribuzione → Tipo: App Web**
- Esegui come: **Me**
- Chi ha accesso: **Chiunque**
- Copia l'URL `https://script.google.com/macros/s/.../exec`

## 6. Supabase Database Webhook
Supabase → **Database → Webhooks → Create a new hook**:
- Table: `SOCI`
- Events: ☑ Insert ☑ Update ☑ Delete
- Type: HTTP Request · Method `POST`
- URL: `<URL-web-app>?secret=<WEBHOOK_SECRET>`

## 7. Push iniziale (una tantum)
Esegui `initialPushSheetToSupabase` per caricare lo stato attuale dello Sheet.

## Note tecniche
- **Tab**: `Soci total` · **Header**: riga 5 · **Dati**: da riga 6 · **PK**: colonna `ID` (Z)
- **Anti-loop**: flag `_sb_writing` in Script Properties — la scrittura innescata dal webhook non ri-triggera l'upload.
- **Checkbox `PM`/`SENIOR`**: convertite bool ↔ "TRUE"/"FALSE" (DB è TEXT).
- **Interi `ID`/`PERMANENZA (mesi)`**: parse/coerce automatico.
- **Eliminazioni da Sheet**: `onSheetChange` confronta ID Sheet vs DB → DELETE dei mancanti. Devi *eliminare la riga* (non svuotarla).
- **Django off**: Supabase Webhook continua a funzionare — qualunque fonte modifichi la tabella, il webhook scatta.
- **Django on**: le modifiche ORM Django arrivano a Postgres, Postgres invoca il webhook, lo Sheet si aggiorna. Nessuna integrazione Django necessaria.
- Log: Apps Script → **Executions** · Supabase → **Webhooks → Logs**.
