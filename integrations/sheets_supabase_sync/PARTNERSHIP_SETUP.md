# 🚀 GUIDA NOOB — Sync Partnership Sheets ↔ Supabase ↔ Django

Tempo totale: **~25 minuti**. Segui i 5 passaggi nell'ordine. Non saltare niente.

---

## 📍 Mappa di cosa farai

```
PASSO 1 → Supabase: crea/aggiorna la tabella PARTNERSHIP             [5 min]
PASSO 2 → Apps Script: incolla il codice + setta 3 segreti           [5 min]
PASSO 3 → Apps Script: esegui 4 funzioni di setup                    [5 min]
PASSO 4 → Apps Script: pubblica la Web App                           [3 min]
PASSO 5 → Supabase: crea il Webhook                                  [5 min]
```

Stato attuale: i Sheets sono già pronti (tab Partnership con 75 righe + 4 tab filtro QUERY).

---

## PASSO 1 — Supabase: tabella PARTNERSHIP

### 1.1 Apri il SQL Editor

1. Vai su https://supabase.com → entra nel tuo progetto JESAP
2. Menu sinistro → icona "SQL Editor" (terminal con `>_`)
3. Click **"+ New query"** in alto a sinistra

### 1.2 Esegui la migrazione

1. Apri sul tuo Mac il file
   `/Users/dannydogthoot/Stuff/UNI2/jesap-CRM/integrations/sheets_supabase_sync/PARTNERSHIP_MIGRATION.sql`
2. Copia **TUTTO** il contenuto
3. Incolla nel SQL Editor di Supabase
4. Click **"Run"** (o `Cmd+Enter`)

✅ Aspetto: in basso vedi una tabella con i conteggi per status, tipo:
```
Attiva                 | 22
Conclusa               | 24
In trattativa          |  6
Non finalizzata        | 18
NULL                   |  4   (P048-P051: status da impostare manualmente)
─────────────────────────
Totale: 74 righe
```

❌ Se errore "relation does not exist": riesegui semplicemente il file `PARTNERSHIP_MIGRATION.sql` (è auto-contenuto, fa sia CREATE che INSERT).
❌ Se errore "duplicate key value": la tabella esiste già. Il file ha `DROP TABLE` in cima quindi non dovrebbe succedere — verifica di aver copiato TUTTO il file dall'inizio.

### 1.3 Recupera URL e KEY (servono al PASSO 2)

1. Settings (ingranaggio in basso a sinistra) → **API**
2. Copia:
   - **Project URL** = `https://xyz123.supabase.co` ← lo userai come `SUPABASE_URL`
   - **service_role** key (la lunga, NON anon!) ← lo userai come `SUPABASE_KEY`
3. Mettili da parte (Note app o file txt)

⚠️ La service_role key è **segreta**, non condividerla pubblicamente.

---

## PASSO 2 — Apps Script: incolla il codice + 3 segreti

### 2.1 Apri l'editor Apps Script

Sei già lì (tab Chrome **"PARTNERSHIPS SYNC - Editor progetto"**). Se chiuso:
- Apri il foglio "DB Partnership"
- Menu **Estensioni → Apps Script**

### 2.2 Incolla il codice

1. Apri sul tuo Mac il file
   `/Users/dannydogthoot/Stuff/UNI2/jesap-CRM/integrations/sheets_supabase_sync/PartnershipCode.gs`
2. Copia **TUTTO** il contenuto
3. Nell'editor Apps Script: file `Code.gs` (già aperto) → seleziona tutto (`Cmd+A`) → Cancella → Incolla (`Cmd+V`)
4. Salva: `Cmd+S`

L'ID del foglio è già hard-coded nel codice (riga 38), non devi cambiarlo.

### 2.3 Setta i 3 segreti (Properties)

1. In Apps Script, sidebar sinistra → **Impostazioni progetto** (icona ingranaggio ⚙)
2. Scorri giù fino a "**Proprietà script**"
3. Click **"Aggiungi proprietà script"** e inserisci queste **3 righe** (una per volta, click "Aggiungi" dopo ognuna):

| Proprietà | Valore |
|-----------|--------|
| `SUPABASE_URL` | `https://xxxx.supabase.co` (quello che hai copiato al passo 1.3) |
| `SUPABASE_KEY` | `eyJhbGc...` (la service_role key lunga) |
| `WEBHOOK_SECRET` | una stringa random a tua scelta, es. `jesap-partnership-2026` |

4. Click **"Salva proprietà script"**

⚠️ Non confondere `SUPABASE_KEY` con la chiave **anon** (la service_role è la più potente).

---

## PASSO 3 — Apps Script: esegui 4 funzioni di setup

Torna alla vista **Editor** (icona `<>`).

In alto c'è una toolbar con:
- una **dropdown** con i nomi delle funzioni (es. "Seleziona funzione")
- un bottone **▶ Esegui**

Esegui le seguenti 4 funzioni **in ordine**, una per volta. Per ognuna: seleziona dalla dropdown → click ▶ Esegui → attendi messaggio "Esecuzione completata" → guarda la sezione "Log esecuzione" in basso.

### 3.1 `diagnostics`
**Scopo**: verifica che tutto sia configurato.

✅ Atteso nei log:
```
Master:    OK ('Partnership')
✓ Lead Partnership
✓ Non finalizzate
✓ Partnership Attive
✓ Partnership Concluse
SUPABASE_URL:   OK
SUPABASE_KEY:   OK
WEBHOOK_SECRET: OK
```

Se vedi "MANCA!" su una properties: torna al passo 2.3.

### 3.2 `testPartnershipConnection`
**Scopo**: verifica che le credenziali Supabase funzionino.

⚠️ Alla **prima esecuzione** Google chiederà permessi: click "Rivedi autorizzazioni" → scegli il tuo account Google → "Avanzate" → "Vai a PARTNERSHIPS SYNC (non sicuro)" → "Consenti".

✅ Atteso:
```
Status: 200
✓ Connessione OK — N righe campione lette
```

❌ Se 401/403: chiave sbagliata, ricontrolla service_role.
❌ Se 404: la tabella PARTNERSHIP non esiste, torna al PASSO 1.

### 3.3 `applyStatusValidation`
**Scopo**: applica la convalida dati con i 5 status sulla colonna E del master (in caso non sia ancora a posto).

✅ Atteso:
```
✓ Convalida status applicata a E2:E2000
```

### 3.4 `styleFilterTabs`
**Scopo**: applica lo stile (sfondo magenta + testo bianco bold) ai 4 tab filtro, identico al master.

✅ Atteso:
```
✓ Stile applicato a 'Lead Partnership' (2 colonne)
✓ Stile applicato a 'Non finalizzate' (5 colonne)
✓ Stile applicato a 'Partnership Attive' (9 colonne)
✓ Stile applicato a 'Partnership Concluse' (8 colonne)
```

Apri il foglio: i 4 tab filtro ora hanno l'header magenta come il master 🎉

### 3.5 `setupPartnershipTriggers`
**Scopo**: installa i trigger che fanno scattare il sync Sheets→Supabase quando editi una cella.

✅ Atteso:
```
✓ Trigger installati: onPartnershipEdit + onPartnershipChange
```

### 3.6 `initialPushPartnershipToSupabase`
**Scopo**: spedisce TUTTE le righe del foglio master a Supabase (popolamento iniziale).

⏳ Può durare 30-60 secondi (75 righe).

✅ Atteso:
```
✓ Push iniziale completato: 75 righe inviate a Supabase
```

Ora torna su Supabase → Table Editor → tabella `PARTNERSHIP` → vedi 75 righe.

---

## PASSO 4 — Pubblica la Web App (per ricevere il webhook)

### 4.1 Distribuisci

1. Apps Script in alto a destra → **"Distribuisci"** (bottone blu) → **"Nuova distribuzione"**
2. Click sull'**ingranaggio** vicino a "Seleziona tipo" → scegli **"App web"**
3. Compila:
   - **Descrizione**: `Partnership webhook v1`
   - **Esegui come**: `Me (tu@email.com)`
   - **Chi ha accesso**: **`Chiunque`** ⚠️ (necessario perché Supabase deve poter chiamare l'URL)
4. Click **"Distribuisci"**
5. Google chiede di nuovo permessi → autorizza

### 4.2 Copia l'URL della Web App

Dopo distribuzione vedi:
```
URL Web app
https://script.google.com/macros/s/AKfycbXXXXXXXXXXX/exec
```

📋 **Copia questo URL**, ti serve al PASSO 5.

---

## PASSO 5 — Supabase: crea il Webhook

### 5.1 Apri Database Webhooks

1. Supabase sidebar sinistra → **"Database"** (icona DB)
2. In alto: tab **"Webhooks"**
3. Click **"Create a new hook"**

### 5.2 Compila il form

| Campo | Valore |
|-------|--------|
| **Name** | `partnership_sync` |
| **Table** | `PARTNERSHIP` (dalla schema `public`) |
| **Events** | ✅ Insert ✅ Update ✅ Delete (tutti e 3) |
| **Type** | `HTTP Request` |
| **HTTP method** | `POST` |
| **HTTP URL** | `<URL_WEBAPP>?secret=<WEBHOOK_SECRET>&t=partnership` |
| **HTTP Headers** | (lasciare default) |
| **HTTP Params** | (lasciare default) |
| **Timeout** | `5000` ms |

⚠️ Sostituisci nel campo URL:
- `<URL_WEBAPP>` con l'URL del PASSO 4.2
- `<WEBHOOK_SECRET>` con il valore che hai messo nelle Properties (PASSO 2.3)

Esempio finale:
```
https://script.google.com/macros/s/AKfycbXX.../exec?secret=jesap-partnership-2026&t=partnership
```

3. Click **"Create webhook"**

---

## ✅ TEST FINALE

### Test A — Sheets → Supabase

1. Apri il foglio, tab "Partnership"
2. Modifica un valore qualsiasi su una riga (es. cambia "Attiva" → "Conclusa")
3. Vai su Supabase → Table Editor → `PARTNERSHIP` → trova quella partnership
4. ✅ Il campo `Status partnership` deve essere aggiornato (entro ~2 secondi)

### Test B — Supabase → Sheets

1. Su Supabase → Table Editor → `PARTNERSHIP`
2. Modifica una cella (es. campo `Tipologia` su una riga)
3. Vai sul foglio "Partnership"
4. ✅ La cella corrispondente nel foglio si aggiorna entro ~2 secondi

### Test C — Django → Sheets

1. Apri il sito Django: http://localhost:8000/partnerships/
2. Crea una nuova Partnership con status "Non finalizzata"
3. ✅ La riga appare in fondo al tab "Partnership" del foglio
4. ✅ La riga appare anche nel tab "Non finalizzate" (via QUERY)

---

## 🆘 TROUBLESHOOTING

### "Webhook non scatta su Supabase"

1. Supabase → Database → Webhooks → click sul tuo webhook → tab "Logs"
2. Se vedi `401 unauthorized`: secret sbagliato, ricontrolla URL e WEBHOOK_SECRET combaciano
3. Se vedi `404`: l'URL della Web App non risponde — ricontrolla che sia distribuita come "Chiunque"

### "Le righe Non finalizzate non vanno via dal foglio Partnership quando cambio status"

Normale. Il foglio master mantiene **tutte** le righe a prescindere dallo status. Il filtro è solo nei tab filtro QUERY (Lead Partnership, Non finalizzate, Attive, Concluse) e su Django.

### "Vedo righe duplicate dopo aver editato"

Apri SQL Editor su Supabase ed esegui:
```sql
SELECT "Partnership", COUNT(*) FROM "PARTNERSHIP"
GROUP BY "Partnership" HAVING COUNT(*) > 1;
```
Se trova duplicati, segnalalo. La PK è `Partnership` (nome) quindi non dovrebbero crearsene.

### "Lo style sui tab filtro non è esattamente uguale al master"

Riesegui `styleFilterTabs` da Apps Script. Funziona idempotente.

### "Le QUERY mostrano #REF! o #ERROR!"

Le formule sono nei tab filtro in cella A1. Click sul tab che ha errore → click A1 → premi Cancella → reinserisci la formula corretta:

| Tab | Formula |
|-----|---------|
| `Lead Partnership` | `=QUERY(Partnership!A1:R; "select B, P where E='In trattativa' order by B label B 'Partnership', P 'URL Cartella Drive'"; 1)` |
| `Non finalizzate` | `=QUERY(Partnership!A1:R; "select B, N, F, G, O where E='Non finalizzata' order by B label B 'Realtà', N 'Contatti', F 'Periodo', G 'Anno', O 'Cartella'"; 1)` |
| `Partnership Attive` | `=QUERY(Partnership!A1:R; "select A, B, C, D, F, G, H, K, P where E='Attiva' or E='In fase di rinnovo' order by B"; 1)` |
| `Partnership Concluse` | `=QUERY(Partnership!A1:R; "select A, B, C, D, F, G, K, P where E='Conclusa' order by F desc"; 1)` |

⚠️ Italiano: il separatore argomenti è `;` (NON `,`). La virgola dentro la stringa SQL della QUERY va invece bene.

### "Voglio disattivare temporaneamente il sync"

Apps Script → Trigger (icona orologio nella sidebar) → elimina i 2 trigger
`onPartnershipEdit` e `onPartnershipChange`. Per riattivare, riesegui `setupPartnershipTriggers`.

---

## 📚 RIEPILOGO ARCHITETTURA

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Foglio "DB Partnership"                                           │
│                                                                    │
│  ┌─────────────────────┐                                           │
│  │ Tab "Partnership"   │  ← MASTER. Edit qui = sync a Supabase    │
│  │ (75 righe, all      │     onPartnershipEdit (Sheets→Supabase)   │
│  │  status mixati)     │                                           │
│  └──────────┬──────────┘                                           │
│             │ formule QUERY()                                      │
│             ▼                                                      │
│  ┌────────────────────────────┐                                    │
│  │ Tab "Lead Partnership"     │  view di status='In trattativa'   │
│  │ Tab "Non finalizzate"      │  view di status='Non finalizzata' │
│  │ Tab "Partnership Attive"   │  view di status IN Attiva/Rinnovo │
│  │ Tab "Partnership Concluse" │  view di status='Conclusa'        │
│  └────────────────────────────┘  (sola lettura, non sync)         │
│                                                                    │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          │ HTTPS (PostgREST + Webhook)
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Supabase tabella "PARTNERSHIP"                                   │
│  PK = "Partnership" (nome)                                         │
│  CHECK status IN (Attiva/Conclusa/In rinnovo/In tratt/Non final)  │
│                                                                    │
└─────────────────────────┬──────────────────────────────────────────┘
                          │
                          │ Django ORM
                          │
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Django dashboard "/partnerships/"                                 │
│  Tab Partnership / Lead Partnership / Non finalizzate              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

**Regola d'oro**: la **PK è il nome** della partnership. Cambi il nome = perdi la sincronizzazione (riga nuova su Supabase). Per cambiare nome serve un'operazione di rename a 2 step (vecchio cancellato + nuovo creato).

---

## 🎯 CHECKLIST FINALE

- [ ] PARTNERSHIP table su Supabase con CHECK constraint a 5 status
- [ ] 75 righe importate (51 originali + 18 non finalizzate + 6 lead)
- [ ] Apps Script configurato con 3 properties
- [ ] Trigger installati (`setupPartnershipTriggers`)
- [ ] Stile uniforme sui 4 tab filtro (`styleFilterTabs`)
- [ ] Web App distribuita con accesso "Chiunque"
- [ ] Webhook Supabase puntato all'URL Web App + secret
- [ ] Test A/B/C tutti verdi

Quando tutti questi sono ✓, il sistema è in produzione 🚀
