#!/usr/bin/env python3
"""
Sync bidirezionale: Google Sheets SOCI <-> Supabase SOCI
Funziona senza server Django. Richiede solo:
  - SUPABASE_URL e SUPABASE_SERVICE_KEY in .env
  - GOOGLE_CREDS_PATH che punta al JSON del service account Google
"""
import os
import json
import hashlib
import requests
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

# ── Configurazione ─────────────────────────────────────────────────────────────
SUPABASE_URL  = os.environ["SUPABASE_URL"]       # es. https://xxxx.supabase.co
SUPABASE_KEY  = os.environ["SUPABASE_SERVICE_KEY"]  # service role key (NON anon)
SHEET_ID      = "1PE8sPI1ZMgWjCYBPEQPs-l795mrDwnu21qoR0IRtR2U"
SHEET_TAB     = "SOCI"
STATE_TAB     = "_sync_state"                    # tab nascosta per tracciare lo stato
TABLE         = "SOCI"
PK            = "ID"
CREDS_PATH    = os.environ.get("GOOGLE_CREDS_PATH", "sync/google_credentials.json")

# Colonne da sincronizzare (solo quelle comuni tra Sheets e Supabase)
SYNC_COLUMNS = [
    "NOME E COGNOME", "NOME 1", "NOME 2", "COGNOME", "SESSO",
    "DATA DI NASCITA", "EMAIL @jesap", "EMAIL personale", "CELLULARE",
    "RUOLO ESTESO", "RUOLO", "AREA DI APPARTENENZA", "STATUS",
    "DATA INIZIO PROVA", "DATA ENTRATA", "DATA USCITA", "PERMANENZA (mesi)",
    "FACOLTA'", "CORSO DI STUDI", "ANNO DI STUDI", "ANNO DI STUDI_1",
    "PM", "SENIOR", "ETÀ", "NOTE", "ID",
]

# ── Supabase ───────────────────────────────────────────────────────────────────
def _sb_headers(extra=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h

def fetch_supabase() -> dict:
    columns = ",".join(f'"{c}"' for c in SYNC_COLUMNS)
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_sb_headers(),
        params={"select": columns},
        timeout=30,
    )
    resp.raise_for_status()
    return {str(r[PK]): r for r in resp.json() if r.get(PK) is not None}

def upsert_supabase(rows: list):
    if not rows:
        return
    # Filtra solo le colonne note
    clean = [{c: r.get(c) for c in SYNC_COLUMNS} for r in rows]
    resp = requests.post(
        f"{SUPABASE_URL}/rest/v1/{TABLE}",
        headers=_sb_headers({"Prefer": "resolution=merge-duplicates,return=minimal"}),
        json=clean,
        timeout=30,
    )
    resp.raise_for_status()

# ── Google Sheets ──────────────────────────────────────────────────────────────
def _get_gc():
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=scopes)
    return gspread.authorize(creds)

def fetch_sheets(gc) -> dict:
    ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_TAB)
    all_rows = ws.get_all_records(expected_headers=SYNC_COLUMNS, default_blank="")
    return {str(r[PK]): r for r in all_rows if r.get(PK)}

def update_sheets(gc, rows_to_update: dict):
    """Aggiorna o appende righe nel foglio. rows_to_update = {id: row_dict}"""
    if not rows_to_update:
        return
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(SHEET_TAB)
    headers = ws.row_values(1)
    pk_col_idx = headers.index(PK)  # 0-based
    all_pk_values = ws.col_values(pk_col_idx + 1)  # 1-based API

    for row_id, data in rows_to_update.items():
        values = [str(data.get(h, "") or "") for h in headers]
        try:
            row_num = all_pk_values.index(str(row_id)) + 1
            end_col = chr(64 + len(headers))
            ws.update(f"A{row_num}:{end_col}{row_num}", [values], raw=False)
        except ValueError:
            # ID non trovato → aggiungi riga nuova
            ws.append_row(values, value_input_option="USER_ENTERED")

# ── Stato sync (tab nascosta _sync_state) ─────────────────────────────────────
def _row_hash(row: dict) -> str:
    normalized = {c: str(row.get(c, "") or "").strip() for c in SYNC_COLUMNS}
    return hashlib.md5(json.dumps(normalized, sort_keys=True).encode()).hexdigest()

def load_state(gc) -> dict:
    sh = gc.open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(STATE_TAB)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(STATE_TAB, rows=2000, cols=2)
        ws.update("A1:B1", [["ID", "hash"]])
        return {}
    records = ws.get_all_records()
    return {str(r["ID"]): r["hash"] for r in records if r.get("ID")}

def save_state(gc, state: dict):
    sh = gc.open_by_key(SHEET_ID)
    ws = sh.worksheet(STATE_TAB)
    ws.clear()
    ws.update("A1:B1", [["ID", "hash"]])
    if state:
        rows = [[k, v] for k, v in state.items()]
        ws.update(f"A2:B{len(rows) + 1}", rows)

# ── Sync principale ────────────────────────────────────────────────────────────
def sync():
    print("▶ Avvio sync SOCI...")
    gc = _get_gc()

    sheets_data   = fetch_sheets(gc)
    supabase_data = fetch_supabase()
    last_state    = load_state(gc)

    all_ids = set(sheets_data) | set(supabase_data)

    to_supabase   = []   # righe cambiate in Sheets → push a Supabase
    to_sheets     = {}   # righe cambiate in Supabase → update Sheets
    new_state     = {}

    for rid in all_ids:
        sh_row = sheets_data.get(rid, {})
        sb_row = supabase_data.get(rid, {})

        sh_hash   = _row_hash(sh_row) if sh_row else None
        sb_hash   = _row_hash(sb_row) if sb_row else None
        prev_hash = last_state.get(str(rid))

        sh_changed = sh_hash is not None and sh_hash != prev_hash
        sb_changed = sb_hash is not None and sb_hash != prev_hash

        if sh_changed and not sb_changed:
            # Solo Sheets è cambiato → manda a Supabase
            to_supabase.append(sh_row)
            new_state[rid] = sh_hash
        elif sb_changed and not sh_changed:
            # Solo Supabase è cambiato → aggiorna Sheets
            to_sheets[rid] = sb_row
            new_state[rid] = sb_hash
        elif sh_changed and sb_changed:
            # Conflitto → Supabase vince (database = source of truth)
            print(f"  ⚠ Conflitto su ID {rid} → Supabase prevale")
            to_sheets[rid] = sb_row
            new_state[rid] = sb_hash
        else:
            # Nessuna modifica
            new_state[rid] = sh_hash or sb_hash or prev_hash

    if to_supabase:
        upsert_supabase(to_supabase)
        print(f"  ✓ {len(to_supabase)} righe Sheets → Supabase")

    if to_sheets:
        update_sheets(gc, to_sheets)
        print(f"  ✓ {len(to_sheets)} righe Supabase → Sheets")

    if not to_supabase and not to_sheets:
        print("  ✓ Già sincronizzati, nessuna modifica")

    save_state(gc, new_state)
    print("▶ Sync completato.")


if __name__ == "__main__":
    sync()
