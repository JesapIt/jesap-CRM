/**
 * Google Apps Script — Foglio SOCI
 *
 * Contiene:
 *   1. Sync bidirezionale real-time: Google Sheets SOCI ↔ Supabase SOCI
 *   2. recordAssociatiEndOfMonth() — registra il conteggio soci a fine mese
 *
 * SETUP sync (esegui una volta):
 *   1. Seleziona tutto questo file e incollalo in Apps Script (sostituendo tutto)
 *   2. Progetto → Proprietà script → aggiungi:
 *        SUPABASE_URL  = https://xxxx.supabase.co
 *        SUPABASE_KEY  = eyJ...  (service role key, NON anon key)
 *   3. Esegui setupTriggers() una volta sola
 *   4. Distribuisci → Nuova distribuzione → App Web (Esegui come: Me, Accesso: Chiunque)
 *   5. Incolla l'URL Web App nel Supabase Database Webhook sulla tabella SOCI
 */

// ── Config sync ────────────────────────────────────────────────────────────
const PROP      = PropertiesService.getScriptProperties();
const SB_URL    = PROP.getProperty("SUPABASE_URL");
const SB_KEY    = PROP.getProperty("SUPABASE_KEY");
const TABLE     = "SOCI";
const PK        = "ID";
const SHEET_TAB = "SOCI";
const SHEET_ID  = "1PE8sPI1ZMgWjCYBPEQPs-l795mrDwnu21qoR0IRtR2U";
const LOCK_KEY  = "_sb_writing"; // evita loop Supabase→Sheets→Supabase

// ── Utility ────────────────────────────────────────────────────────────────
function getSheet_() {
  return SpreadsheetApp.openById(SHEET_ID).getSheetByName(SHEET_TAB);
}

function getHeaders_(sheet) {
  return sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
}

function rowToRecord_(headers, values) {
  const rec = {};
  headers.forEach(function(h, i) {
    rec[h] = (values[i] === "" || values[i] === undefined) ? null : String(values[i]);
  });
  return rec;
}

// ── Supabase REST ──────────────────────────────────────────────────────────
function sbHeaders_(extra) {
  return Object.assign({
    "apikey": SB_KEY,
    "Authorization": "Bearer " + SB_KEY,
    "Content-Type": "application/json",
  }, extra || {});
}

function sbUpsert_(records) {
  if (!records || records.length === 0) return;
  const resp = UrlFetchApp.fetch(SB_URL + "/rest/v1/" + TABLE, {
    method: "POST",
    headers: sbHeaders_({ "Prefer": "resolution=merge-duplicates,return=minimal" }),
    payload: JSON.stringify(Array.isArray(records) ? records : [records]),
    muteHttpExceptions: true,
  });
  if (resp.getResponseCode() >= 300)
    console.error("sbUpsert error " + resp.getResponseCode() + ": " + resp.getContentText());
}

function sbDelete_(pkValue) {
  const resp = UrlFetchApp.fetch(
    SB_URL + "/rest/v1/" + TABLE + "?" + PK + "=eq." + encodeURIComponent(pkValue),
    {
      method: "DELETE",
      headers: sbHeaders_({ "Prefer": "return=minimal" }),
      muteHttpExceptions: true,
    }
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
  const sheet = e.range.getSheet();
  if (sheet.getName() !== SHEET_TAB) return;
  if (PROP.getProperty(LOCK_KEY) === "1") return; // scrittura da Supabase, ignora

  const row = e.range.getRow();
  if (row === 1) return; // intestazione

  const headers   = getHeaders_(sheet);
  const pkIdx     = headers.indexOf(PK);
  if (pkIdx === -1) return;

  const rowValues = sheet.getRange(row, 1, 1, headers.length).getValues()[0];
  const pkValue   = rowValues[pkIdx];
  if (!pkValue) return;

  sbUpsert_(rowToRecord_(headers, rowValues));
  console.log("Sheets→Supabase: upserted ID " + pkValue);
}

function onSheetChange(e) {
  if (e.changeType !== "REMOVE_ROW") return;
  if (PROP.getProperty(LOCK_KEY) === "1") return;

  const sheet   = getSheet_();
  const headers = getHeaders_(sheet);
  const pkIdx   = headers.indexOf(PK);
  if (pkIdx === -1) return;

  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;

  const sheetIds = new Set(
    sheet.getRange(2, pkIdx + 1, lastRow - 1, 1)
      .getValues().flat().map(String).filter(Boolean)
  );

  sbFetchAllIds_().forEach(function(id) {
    if (!sheetIds.has(id)) {
      sbDelete_(id);
      console.log("Sheets→Supabase: deleted ID " + id);
    }
  });
}

// ── Direzione 2: Supabase → Sheets (Web App endpoint) ─────────────────────

function doPost(e) {
  try {
    const body       = JSON.parse(e.postData.contents);
    const type       = body.type;
    const record     = body.record;
    const old_record = body.old_record;

    PROP.setProperty(LOCK_KEY, "1");

    const sheet   = getSheet_();
    const headers = getHeaders_(sheet);
    const pkIdx   = headers.indexOf(PK);
    const allPKs  = sheet.getRange(1, pkIdx + 1, sheet.getLastRow(), 1)
                         .getValues().flat().map(String);

    if (type === "DELETE") {
      const idx = allPKs.indexOf(String(old_record[PK]));
      if (idx > 0) {
        sheet.deleteRow(idx + 1);
        console.log("Supabase→Sheets: deleted ID " + old_record[PK]);
      }
    } else {
      const pkValue = String(record[PK]);
      const rowVals = headers.map(function(h) { return record[h] != null ? record[h] : ""; });
      const idx     = allPKs.indexOf(pkValue);

      if (idx > 0) {
        sheet.getRange(idx + 1, 1, 1, headers.length).setValues([rowVals]);
        console.log("Supabase→Sheets: updated ID " + pkValue);
      } else {
        sheet.appendRow(rowVals);
        console.log("Supabase→Sheets: inserted ID " + pkValue);
      }
    }

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    console.error("doPost error: " + err);
    return ContentService
      .createTextOutput(JSON.stringify({ error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  } finally {
    Utilities.sleep(1500);
    PROP.deleteProperty(LOCK_KEY);
  }
}

// ── Test manuale ───────────────────────────────────────────────────────────

/**
 * Esegui questa funzione per verificare che:
 *   1. Le proprietà script sono impostate correttamente
 *   2. Supabase risponde (credenziali valide)
 *   3. La tabella SOCI esiste e si legge
 * Vai su Esegui → testConnection e controlla il log (Visualizza → Log).
 */
function testConnection() {
  console.log("── Test connessione Supabase ──");
  console.log("URL:  " + SB_URL);
  console.log("KEY:  " + (SB_KEY ? SB_KEY.substring(0, 20) + "..." : "MANCANTE!"));

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
    console.log("✓ OK — trovate " + rows.length + " righe in Supabase SOCI");
  } else {
    console.error("✗ Errore " + resp.getResponseCode() + " — controlla URL/chiave/RLS");
  }
}

// ── Setup trigger (esegui una volta sola) ──────────────────────────────────

function setupTriggers() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  ScriptApp.getProjectTriggers().forEach(function(t) { ScriptApp.deleteTrigger(t); });

  ScriptApp.newTrigger("onSheetEdit").forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger("onSheetChange").forSpreadsheet(ss).onChange().create();

  // Trigger giornaliero per recordAssociatiEndOfMonth (scatta ogni notte a mezzanotte)
  ScriptApp.newTrigger("recordAssociatiEndOfMonth")
    .timeBased().atHour(23).everyDays(1).create();

  console.log("✓ Trigger installati: onSheetEdit, onSheetChange, recordAssociatiEndOfMonth");
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
    if (!statsSheet) {
      statsSheet = ss.insertSheet("Stats");
    }

    if (statsSheet.getRange("G1").getValue() === "") {
      statsSheet.getRange("G1").setValue("Data");
      statsSheet.getRange("H1").setValue("Numero di Associati");
    }

    var columnGValues = statsSheet.getRange("G:G").getValues();
    var lastRow = 0;
    for (var i = columnGValues.length - 1; i >= 0; i--) {
      if (columnGValues[i][0] !== "") {
        lastRow = i + 1;
        break;
      }
    }

    statsSheet.getRange(lastRow + 1, 7, 1, 2).setValues([[today, associati]]);
    Logger.log("Registrato " + associati + " associati il " + today);
  } else {
    Logger.log("Oggi non è l'ultimo giorno del mese. Nessun dato registrato.");
  }
}
