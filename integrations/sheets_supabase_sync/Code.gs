/**
 * Google Apps Script — Foglio SOCI (JESAP)
 *
 * Contiene:
 *   1. Sync bidirezionale real-time: Google Sheets "Soci total" ↔ Supabase "SOCI"
 *   2. recordAssociatiEndOfMonth() — registra conteggio soci a fine mese
 *   3. testConnection()           — verifica credenziali/collegamento Supabase
 *
 * L'automazione NON dipende da Django: Supabase Database Webhook scatta
 * direttamente ad ogni INSERT/UPDATE/DELETE sulla tabella SOCI (qualunque
 * sia la sorgente: sito Django, SQL editor, API), e chiama il Web App
 * di questo script. Analogamente, Sheets → Supabase passa direttamente
 * via PostgREST. Django può essere off.
 *
 * SETUP (una volta sola):
 *   1. Incolla questo file in Apps Script (Estensioni → Apps Script)
 *   2. Progetto → Proprietà script:
 *        SUPABASE_URL = https://<project-ref>.supabase.co
 *        SUPABASE_KEY = eyJ... (service_role key, NON anon)
 *   3. Esegui setupTriggers() una volta
 *   4. Esegui testConnection() per verifica
 *   5. Distribuisci → Nuova distribuzione → App Web
 *        (Esegui come: Me, Accesso: Chiunque)
 *   6. In Supabase: Database → Webhooks → crea webhook su tabella SOCI
 *        eventi INSERT/UPDATE/DELETE, URL = <web-app-url>?secret=<WEBHOOK_SECRET>
 *   7. (Facoltativo) Esegui initialPushSheetToSupabase() per popolare la prima volta
 */

// ── Config ─────────────────────────────────────────────────────────────────
const PROP        = PropertiesService.getScriptProperties();
const SB_URL      = PROP.getProperty("SUPABASE_URL");
const SB_KEY      = PROP.getProperty("SUPABASE_KEY");
const WH_SECRET   = PROP.getProperty("WEBHOOK_SECRET");
const TABLE       = "SOCI";
const PK          = "ID";
const SHEET_ID    = "1PE8sPI1ZMgWjCYBPEQPs-l795mrDwnu21qoR0IRtR2U";
const SHEET_TAB   = "Soci total";
const HEADER_ROW  = 5;
const DATA_START  = 6;
const LOCK_KEY    = "_sb_writing"; // evita loop Supabase→Sheets→Supabase
const BOOL_FIELDS = new Set(["PM", "SENIOR"]);
const INT_FIELDS  = new Set(["PERMANENZA (mesi)", "ID"]);

// ── Utility ────────────────────────────────────────────────────────────────
function getSheet_() {
  return SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_TAB);
}

function getHeaders_(sheet) {
  return sheet.getRange(HEADER_ROW, 1, 1, sheet.getLastColumn()).getValues()[0];
}

function pkColumnIndex_(headers) {
  const idx = headers.indexOf(PK);
  if (idx === -1) throw new Error("Colonna " + PK + " non trovata a riga " + HEADER_ROW);
  return idx;
}

/** Formatta un oggetto Date come DD/MM/YYYY (formato originale dello Sheet). */
function formatDate_(d) {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return dd + "/" + mm + "/" + d.getFullYear();
}

/** Sheet row values → record Supabase (gestisce booleani, interi e date).
 *  Se writableCols è passato, salta le colonne "formula" (non le manda a Supabase). */
function rowToRecord_(headers, values, writableCols) {
  const rec = {};
  headers.forEach(function(h, i) {
    if (writableCols && !writableCols[i]) return; // colonna calcolata da formula → skip
    let v = values[i];
    if (v === "" || v === null || v === undefined) { rec[h] = null; return; }
    if (BOOL_FIELDS.has(h)) {
      rec[h] = (v === true || String(v).toUpperCase() === "TRUE") ? "TRUE" : "FALSE";
      return;
    }
    if (INT_FIELDS.has(h)) {
      const n = parseInt(v, 10);
      rec[h] = isNaN(n) ? null : n;
      return;
    }
    // Google Sheets converte automaticamente date-like in oggetti Date
    if (v instanceof Date) { rec[h] = formatDate_(v); return; }
    rec[h] = String(v);
  });
  return rec;
}

/** Rileva quali colonne hanno una formula nella prima riga dati (DATA_START).
 *  Restituisce array di booleani: true = scrivibile, false = ha formula (skip). */
function getWritableCols_(sheet, headerCount) {
  const formulas = sheet.getRange(DATA_START, 1, 1, headerCount).getFormulas()[0];
  return formulas.map(function(f) { return !f; });
}

/** Trova la prima riga libera dopo l'ultimo ID presente in colonna PK.
 *  Non usa getLastRow() per evitare "salti" causati da valori sparsi sotto i dati. */
function findAppendRow_(sheet, pkIdx) {
  const last = sheet.getLastRow();
  if (last < DATA_START) return DATA_START;
  const vals = sheet.getRange(DATA_START, pkIdx + 1, last - DATA_START + 1, 1).getValues();
  for (let i = vals.length - 1; i >= 0; i--) {
    const v = vals[i][0];
    if (v !== "" && v !== null && v !== undefined) return DATA_START + i + 1;
  }
  return DATA_START;
}

/** Scrive una riga saltando le colonne con formula. */
function writeRow_(sheet, row, headers, rowVals, writableCols) {
  for (let i = 0; i < headers.length; i++) {
    if (writableCols[i]) {
      sheet.getRange(row, i + 1).setValue(rowVals[i]);
    }
  }
}

/** Record Supabase → riga Sheet (gestisce booleani per checkbox). */
function recordToRow_(headers, record) {
  return headers.map(function(h) {
    let v = record[h];
    if (v === null || v === undefined) return "";
    if (BOOL_FIELDS.has(h)) return String(v).toUpperCase() === "TRUE";
    return v;
  });
}

/** Trova la riga (1-based) con dato ID in colonna PK, -1 se assente. */
function findRowByPK_(sheet, pkIdx, pkValue) {
  if (pkValue === "" || pkValue === null || pkValue === undefined) return -1;
  const last = sheet.getLastRow();
  if (last < DATA_START) return -1;
  const vals = sheet.getRange(DATA_START, pkIdx + 1, last - DATA_START + 1, 1).getValues();
  for (let i = 0; i < vals.length; i++) {
    if (String(vals[i][0]) === String(pkValue)) return DATA_START + i;
  }
  return -1;
}

// ── Supabase REST ──────────────────────────────────────────────────────────
function sbHeaders_(extra) {
  return Object.assign({
    "apikey": SB_KEY,
    "Authorization": "Bearer " + SB_KEY,
    "Content-Type": "application/json",
  }, extra || {});
}

/**
 * Upsert sicuro: tenta PATCH sulla riga esistente (by PK).
 * Se 0 righe aggiornate (Content-Range: * /0) fa POST (insert).
 * Non dipende da vincoli UNIQUE su Postgres.
 */
function sbUpsert_(records) {
  const arr = Array.isArray(records) ? records : [records];
  arr.forEach(function(rec) {
    const pkVal = rec[PK];
    if (pkVal === null || pkVal === undefined) {
      // Nessun ID → solo insert
      sbPost_(rec);
      return;
    }
    const patchResp = UrlFetchApp.fetch(
      SB_URL + "/rest/v1/" + TABLE + "?" + PK + "=eq." + encodeURIComponent(pkVal),
      {
        method: "PATCH",
        headers: sbHeaders_({ "Prefer": "return=representation", "Content-Type": "application/json" }),
        payload: JSON.stringify(rec),
        muteHttpExceptions: true,
      }
    );
    const code = patchResp.getResponseCode();
    if (code >= 300) {
      console.error("PATCH error " + code + ": " + patchResp.getContentText());
      return;
    }
    // PATCH ritorna array vuoto [] se nessuna riga trovata → fai INSERT
    const body = patchResp.getContentText().trim();
    if (body === "[]" || body === "") sbPost_(rec);
  });
}

function sbPost_(rec) {
  const resp = UrlFetchApp.fetch(SB_URL + "/rest/v1/" + TABLE, {
    method: "POST",
    headers: sbHeaders_({ "Prefer": "return=minimal" }),
    payload: JSON.stringify(rec),
    muteHttpExceptions: true,
  });
  if (resp.getResponseCode() >= 300)
    console.error("POST error " + resp.getResponseCode() + ": " + resp.getContentText());
}

function sbDelete_(pkValue) {
  const resp = UrlFetchApp.fetch(
    SB_URL + "/rest/v1/" + TABLE + "?" + PK + "=eq." + encodeURIComponent(pkValue),
    { method: "DELETE", headers: sbHeaders_({ "Prefer": "return=minimal" }), muteHttpExceptions: true }
  );
  if (resp.getResponseCode() >= 300)
    console.error("sbDelete error " + resp.getResponseCode() + ": " + resp.getContentText());
}

function sbFetchAllIds_() {
  const resp = UrlFetchApp.fetch(
    SB_URL + "/rest/v1/" + TABLE + "?select=" + PK,
    { headers: sbHeaders_(), muteHttpExceptions: true }
  );
  if (resp.getResponseCode() >= 300) return [];
  return JSON.parse(resp.getContentText()).map(function(r) { return String(r[PK]); });
}

// ── Direzione 1: Sheets → Supabase ────────────────────────────────────────
function onSheetEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  if (sheet.getName() !== SHEET_TAB) return;
  if (PROP.getProperty(LOCK_KEY) === "1") return; // scrittura proveniente da Supabase

  const row = e.range.getRow();
  if (row < DATA_START) return; // intestazione o righe di riepilogo

  const headers  = getHeaders_(sheet);
  const pkIdx    = pkColumnIndex_(headers);
  const writable = getWritableCols_(sheet, headers.length);
  const vals     = sheet.getRange(row, 1, 1, headers.length).getValues()[0];
  const pkValue  = vals[pkIdx];
  if (!pkValue) return; // riga senza ID → non sync

  sbUpsert_(rowToRecord_(headers, vals, writable));
  console.log("Sheets→Supabase: upsert ID " + pkValue);
}

function onSheetChange(e) {
  if (!e || e.changeType !== "REMOVE_ROW") return;
  if (PROP.getProperty(LOCK_KEY) === "1") return;

  const sheet   = getSheet_();
  const headers = getHeaders_(sheet);
  const pkIdx   = pkColumnIndex_(headers);
  const last    = sheet.getLastRow();

  const sheetIds = new Set();
  if (last >= DATA_START) {
    sheet.getRange(DATA_START, pkIdx + 1, last - DATA_START + 1, 1)
      .getValues().flat().map(String).filter(Boolean)
      .forEach(function(id) { sheetIds.add(id); });
  }

  sbFetchAllIds_().forEach(function(id) {
    if (!sheetIds.has(id)) {
      sbDelete_(id);
      console.log("Sheets→Supabase: delete ID " + id);
    }
  });
}

// ── Direzione 2: Supabase → Sheets (Web App endpoint) ─────────────────────
function doPost(e) {
  try {
    // Verifica secret (se configurato)
    if (WH_SECRET && (!e.parameter || e.parameter.secret !== WH_SECRET)) {
      return ContentService.createTextOutput(JSON.stringify({ error: "unauthorized" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const body       = JSON.parse(e.postData.contents);
    const type       = body.type;          // INSERT | UPDATE | DELETE
    const record     = body.record;
    const old_record = body.old_record;

    PROP.setProperty(LOCK_KEY, "1");

    const sheet    = getSheet_();
    const headers  = getHeaders_(sheet);
    const pkIdx    = pkColumnIndex_(headers);
    const writable = getWritableCols_(sheet, headers.length);

    if (type === "DELETE") {
      const row = findRowByPK_(sheet, pkIdx, old_record && old_record[PK]);
      if (row > 0) { sheet.deleteRow(row); console.log("Supabase→Sheets: delete ID " + old_record[PK]); }
    } else {
      const pkValue = record[PK];
      const rowVals = recordToRow_(headers, record);
      const row     = findRowByPK_(sheet, pkIdx, pkValue);
      if (row > 0) {
        writeRow_(sheet, row, headers, rowVals, writable);
        console.log("Supabase→Sheets: update ID " + pkValue);
      } else {
        const newRow = findAppendRow_(sheet, pkIdx);
        writeRow_(sheet, newRow, headers, rowVals, writable);
        console.log("Supabase→Sheets: insert ID " + pkValue + " riga " + newRow);
      }
    }

    return ContentService.createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    console.error("doPost error: " + err);
    return ContentService.createTextOutput(JSON.stringify({ error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    Utilities.sleep(1500); // lascia sedimentare le scritture prima di riabilitare i trigger
    PROP.deleteProperty(LOCK_KEY);
  }
}

// ── Setup trigger (esegui una volta) ──────────────────────────────────────
function setupTriggers() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  ScriptApp.getProjectTriggers().forEach(function(t) { ScriptApp.deleteTrigger(t); });

  ScriptApp.newTrigger("onSheetEdit").forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger("onSheetChange").forSpreadsheet(ss).onChange().create();
  ScriptApp.newTrigger("recordAssociatiEndOfMonth").timeBased().atHour(23).everyDays(1).create();

  console.log("✓ Trigger installati: onSheetEdit, onSheetChange, recordAssociatiEndOfMonth");
}

// ── Test manuali ───────────────────────────────────────────────────────────

/**
 * Testa che PATCH aggiorni (non dupplichi) una riga esistente.
 * Modifica NOTE di una riga reale e verifica il risultato.
 * Cambia TEST_ID con un ID presente nel tuo Sheet.
 */
function testUpsertUpdate() {
  const TEST_ID   = 20140088; // ← metti un ID reale
  const TEST_NOTE = "test-upsert-" + new Date().getTime();

  sbUpsert_([{ [PK]: TEST_ID, "NOTE": TEST_NOTE }]);

  const resp = UrlFetchApp.fetch(
    SB_URL + "/rest/v1/" + TABLE + "?" + PK + "=eq." + TEST_ID + "&select=" + PK + ",NOTE",
    { headers: sbHeaders_(), muteHttpExceptions: true }
  );
  const rows = JSON.parse(resp.getContentText());
  if (rows.length === 1 && rows[0]["NOTE"] === TEST_NOTE)
    console.log("✓ UPSERT OK — riga aggiornata, nessun duplicato");
  else if (rows.length > 1)
    console.error("✗ DUPLICATO — trovate " + rows.length + " righe con ID " + TEST_ID);
  else
    console.error("✗ Fallito — risposta: " + resp.getContentText());
}

/**
 * Testa che le date non vengano distorte.
 * Legge la prima riga dati dallo Sheet e logga i campi data così come
 * verranno inviati a Supabase. Verifica che siano DD/MM/YYYY.
 */
function testDateFormat() {
  const sheet   = getSheet_();
  const headers = getHeaders_(sheet);
  const vals    = sheet.getRange(DATA_START, 1, 1, headers.length).getValues()[0];
  const rec     = rowToRecord_(headers, vals);
  const dateFields = ["DATA DI NASCITA","DATA INIZIO PROVA","DATA ENTRATA","DATA USCITA"];
  dateFields.forEach(function(f) {
    console.log(f + " → " + JSON.stringify(rec[f]));
  });
  console.log("Se i valori sopra sono DD/MM/YYYY o null il fix è ok.");
}

function testConnection() {
  console.log("── Test connessione Supabase ──");
  console.log("URL: " + SB_URL);
  console.log("KEY: " + (SB_KEY ? SB_KEY.substring(0, 20) + "..." : "MANCANTE!"));

  if (!SB_URL || !SB_KEY) {
    console.error("✗ SUPABASE_URL o SUPABASE_KEY mancanti nelle Proprietà script");
    return;
  }
  const resp = UrlFetchApp.fetch(
    SB_URL + "/rest/v1/" + TABLE + "?select=" + PK + "&limit=3",
    { headers: sbHeaders_(), muteHttpExceptions: true }
  );
  console.log("Status: " + resp.getResponseCode());
  console.log("Body:   " + resp.getContentText().substring(0, 500));

  if (resp.getResponseCode() === 200) {
    const rows = JSON.parse(resp.getContentText());
    console.log("✓ OK — trovate " + rows.length + " righe in Supabase " + TABLE);
  } else {
    console.error("✗ Errore " + resp.getResponseCode() + " — controlla URL/chiave/RLS");
  }
}

// ── Bulk initial sync (una tantum) ─────────────────────────────────────────
function initialPushSheetToSupabase() {
  const sheet = getSheet_();
  const last  = sheet.getLastRow();
  if (last < DATA_START) return;
  const headers  = getHeaders_(sheet);
  const writable = getWritableCols_(sheet, headers.length);
  const rows     = sheet.getRange(DATA_START, 1, last - DATA_START + 1, headers.length).getValues();
  const recs     = rows.map(function(r) { return rowToRecord_(headers, r, writable); })
                       .filter(function(r) { return r[PK] !== null; });
  try {
    PROP.setProperty(LOCK_KEY, "1");
    for (let i = 0; i < recs.length; i += 500) sbUpsert_(recs.slice(i, i + 500));
    console.log("✓ Push iniziale completato: " + recs.length + " righe");
  } finally {
    PROP.deleteProperty(LOCK_KEY);
  }
}

// ══════════════════════════════════════════════════════════════════════════
// FUNZIONE ESISTENTE — registra conteggio soci a fine mese
// ══════════════════════════════════════════════════════════════════════════
function recordAssociatiEndOfMonth() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var conteggioSheet = ss.getSheetByName("Soci total");
  if (!conteggioSheet) {
    Logger.log("Il foglio 'Soci total' non è stato trovato.");
    return;
  }

  var associati = conteggioSheet.getRange("B1").getValue();
  var today     = new Date();
  var tomorrow  = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  if (tomorrow.getMonth() !== today.getMonth()) {
    var statsSheet = ss.getSheetByName("Stats");
    if (!statsSheet) statsSheet = ss.insertSheet("Stats");

    if (statsSheet.getRange("G1").getValue() === "") {
      statsSheet.getRange("G1").setValue("Data");
      statsSheet.getRange("H1").setValue("Numero di Associati");
    }

    var columnGValues = statsSheet.getRange("G:G").getValues();
    var lastRow = 0;
    for (var i = columnGValues.length - 1; i >= 0; i--) {
      if (columnGValues[i][0] !== "") { lastRow = i + 1; break; }
    }

    statsSheet.getRange(lastRow + 1, 7, 1, 2).setValues([[today, associati]]);
    Logger.log("Registrato " + associati + " associati il " + today);
  } else {
    Logger.log("Oggi non è l'ultimo giorno del mese. Nessun dato registrato.");
  }
}
