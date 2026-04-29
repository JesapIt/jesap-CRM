/**
 * ════════════════════════════════════════════════════════════════════════════
 *  PARTNERSHIPS SYNC — Google Sheets ↔ Supabase
 *  JESAP — Junior Enterprise Sapienza
 * ════════════════════════════════════════════════════════════════════════════
 *
 *  Sincronizzazione bidirezionale real-time fra:
 *    • Foglio Google "DB Partnership" tab "Partnership"
 *    • Tabella Supabase "PARTNERSHIP"
 *
 *  Le viste filtro (Lead Partnership, Non finalizzate, Partnership Attive,
 *  Partnership Concluse) sono formule QUERY() nel foglio stesso e NON
 *  vengono toccate dal sync.
 *
 *  ────────────────────────────────────────────────────────────────────────
 *  COSA SERVE PRIMA DI USARE:
 *  ────────────────────────────────────────────────────────────────────────
 *  1. Tabella PARTNERSHIP creata su Supabase (vedi PARTNERSHIP_MIGRATION.sql)
 *  2. Aver impostato 3 Proprietà script (ingranaggio "Impostazioni progetto"
 *     in Apps Script):
 *       • SUPABASE_URL    = https://<tuo-ref>.supabase.co
 *       • SUPABASE_KEY    = service_role key (NON anon!)
 *       • WEBHOOK_SECRET  = stringa random tua scelta
 *  3. Aver verificato che P_SHEET_ID corrisponda al tuo foglio (riga sotto)
 *  ════════════════════════════════════════════════════════════════════════════
 */

// ── 1. CONFIGURAZIONE ──────────────────────────────────────────────────────
const P_SHEET_ID    = "1H0ZRXaevp1jAH4XZduwVaWsiNOcU5UH46oq-Q0gFukM"; // ID foglio DB Partnership
const P_SHEET_TAB   = "Partnership";          // tab master (NON i filtri!)
const P_TABLE       = "PARTNERSHIP";          // tabella Supabase
const P_PK          = "Partnership";          // colonna chiave primaria (= nome)
const P_HEADER_ROW  = 1;
const P_DATA_START  = 2;

// Tab filtro che styleFilterTabs() formatterà come l'header del master
const P_FILTER_TABS = [
  "Lead Partnership",
  "Non finalizzate",
  "Partnership Attive",
  "Partnership Concluse",
];

// Valori validi per Status partnership (deve combaciare col CHECK di Supabase)
const P_STATUS_VALUES = [
  "Attiva",
  "Conclusa",
  "In fase di rinnovo",
  "In trattativa",
  "Non finalizzata",
];

// Tipi colonne (per coercion)
const P_BOOL_FIELDS = new Set(["Compenso economico"]);
const P_INT_FIELDS  = new Set(["ANNO"]);

// Lock keys (anti-loop quando il sync scrive da entrambe le direzioni)
const P_LOCK_KEY = "_p_sb_writing";
function p_rowLockKey_(row) { return "_p_sb_lock_" + row; }

// Properties accessor
const P_PROP = PropertiesService.getScriptProperties();
function P_SB_URL()    { return P_PROP.getProperty("SUPABASE_URL"); }
function P_SB_KEY()    { return P_PROP.getProperty("SUPABASE_KEY"); }
function P_WH_SECRET() { return P_PROP.getProperty("WEBHOOK_SECRET"); }

// ── 2. UTILITY FOGLIO ──────────────────────────────────────────────────────
function p_getSheet_() {
  return SpreadsheetApp.openById(P_SHEET_ID).getSheetByName(P_SHEET_TAB);
}

function p_getHeaders_(sheet) {
  return sheet.getRange(P_HEADER_ROW, 1, 1, sheet.getLastColumn()).getValues()[0];
}

function p_pkColumnIndex_(headers) {
  const idx = headers.indexOf(P_PK);
  if (idx === -1) throw new Error("Colonna '" + P_PK + "' non trovata nella riga " + P_HEADER_ROW);
  return idx;
}

function p_formatDate_(d) {
  const dd = String(d.getDate()).padStart(2, "0");
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  return dd + "/" + mm + "/" + d.getFullYear();
}

/** Riga foglio (array values) → record JSON per Supabase */
function p_rowToRecord_(headers, values) {
  const rec = {};
  headers.forEach(function(h, i) {
    let v = values[i];
    if (v === "" || v === null || v === undefined) { rec[h] = null; return; }
    if (P_BOOL_FIELDS.has(h)) {
      rec[h] = (v === true || String(v).toUpperCase() === "TRUE");
      return;
    }
    if (P_INT_FIELDS.has(h)) {
      const n = parseInt(v, 10);
      rec[h] = isNaN(n) ? null : n;
      return;
    }
    if (v instanceof Date) { rec[h] = p_formatDate_(v); return; }
    rec[h] = String(v);
  });
  return rec;
}

/** Record JSON da Supabase → array values per scrivere su foglio */
function p_recordToRow_(headers, record) {
  return headers.map(function(h) {
    let v = record[h];
    if (v === null || v === undefined) return "";
    if (P_BOOL_FIELDS.has(h)) return (v === true || String(v).toUpperCase() === "TRUE");
    return v;
  });
}

/** Identifica colonne con formula (da non sovrascrivere). Return array bool. */
function p_getWritableCols_(sheet, headerCount) {
  const formulas = sheet.getRange(P_DATA_START, 1, 1, headerCount).getFormulas()[0];
  return formulas.map(function(f) { return !f; });
}

function p_writeRow_(sheet, row, headers, rowVals, writableCols) {
  for (let i = 0; i < headers.length; i++) {
    if (writableCols[i]) sheet.getRange(row, i + 1).setValue(rowVals[i]);
  }
}

/** Trova prima riga libera DOPO l'ultimo PK valorizzato in colonna PK.
 *  Anti-trickeria: ignora celle vuote in altre colonne. */
function p_findAppendRow_(sheet, pkIdx) {
  const last = sheet.getLastRow();
  if (last < P_DATA_START) return P_DATA_START;
  const vals = sheet.getRange(P_DATA_START, pkIdx + 1, last - P_DATA_START + 1, 1).getValues();
  for (let i = vals.length - 1; i >= 0; i--) {
    if (vals[i][0] !== "" && vals[i][0] !== null && vals[i][0] !== undefined) {
      return P_DATA_START + i + 1;
    }
  }
  return P_DATA_START;
}

function p_findRowByPK_(sheet, pkIdx, pkValue) {
  if (!pkValue) return -1;
  const last = sheet.getLastRow();
  if (last < P_DATA_START) return -1;
  const vals = sheet.getRange(P_DATA_START, pkIdx + 1, last - P_DATA_START + 1, 1).getValues();
  for (let i = 0; i < vals.length; i++) {
    if (String(vals[i][0]) === String(pkValue)) return P_DATA_START + i;
  }
  return -1;
}

// ── 3. CHIAMATE SUPABASE REST ──────────────────────────────────────────────
function p_sbHeaders_(extra) {
  return Object.assign({
    "apikey":        P_SB_KEY(),
    "Authorization": "Bearer " + P_SB_KEY(),
    "Content-Type":  "application/json",
  }, extra || {});
}

/** Upsert: PATCH; se non trova la riga fa INSERT. */
function p_sbUpsert_(records) {
  const arr = Array.isArray(records) ? records : [records];
  arr.forEach(function(rec) {
    const pkVal = rec[P_PK];
    if (!pkVal) return;
    const url = P_SB_URL() + "/rest/v1/" + P_TABLE +
      "?" + encodeURIComponent(P_PK) + "=eq." + encodeURIComponent(pkVal);
    const resp = UrlFetchApp.fetch(url, {
      method: "PATCH",
      headers: p_sbHeaders_({ "Prefer": "return=representation" }),
      payload: JSON.stringify(rec),
      muteHttpExceptions: true,
    });
    const code = resp.getResponseCode();
    if (code >= 300) { console.error("PATCH " + code + ": " + resp.getContentText()); return; }
    const body = resp.getContentText().trim();
    if (body === "[]" || body === "") p_sbInsert_(rec);
  });
}

function p_sbInsert_(rec) {
  const resp = UrlFetchApp.fetch(P_SB_URL() + "/rest/v1/" + P_TABLE, {
    method: "POST",
    headers: p_sbHeaders_({ "Prefer": "return=minimal" }),
    payload: JSON.stringify(rec),
    muteHttpExceptions: true,
  });
  if (resp.getResponseCode() >= 300)
    console.error("POST " + resp.getResponseCode() + ": " + resp.getContentText());
}

function p_sbDelete_(pkValue) {
  const url = P_SB_URL() + "/rest/v1/" + P_TABLE +
    "?" + encodeURIComponent(P_PK) + "=eq." + encodeURIComponent(pkValue);
  const resp = UrlFetchApp.fetch(url, {
    method: "DELETE",
    headers: p_sbHeaders_({ "Prefer": "return=minimal" }),
    muteHttpExceptions: true,
  });
  if (resp.getResponseCode() >= 300)
    console.error("DELETE " + resp.getResponseCode() + ": " + resp.getContentText());
}

function p_sbDeleteIn_(pkValues) {
  if (!pkValues || !pkValues.length) return;
  const CHUNK = 100;
  for (let i = 0; i < pkValues.length; i += CHUNK) {
    const list = pkValues.slice(i, i + CHUNK)
      .map(function(v) { return encodeURIComponent(v); })
      .join(",");
    const url = P_SB_URL() + "/rest/v1/" + P_TABLE +
      "?" + encodeURIComponent(P_PK) + "=in.(" + list + ")";
    const resp = UrlFetchApp.fetch(url, {
      method: "DELETE",
      headers: p_sbHeaders_({ "Prefer": "return=minimal" }),
      muteHttpExceptions: true,
    });
    if (resp.getResponseCode() >= 300)
      console.error("DELETE-IN " + resp.getResponseCode() + ": " + resp.getContentText());
    Utilities.sleep(300);
  }
}

function p_sbFetchAllPks_() {
  const url = P_SB_URL() + "/rest/v1/" + P_TABLE +
    "?select=" + encodeURIComponent(P_PK);
  const resp = UrlFetchApp.fetch(url, {
    headers: p_sbHeaders_(), muteHttpExceptions: true,
  });
  if (resp.getResponseCode() >= 300) return [];
  return JSON.parse(resp.getContentText()).map(function(r) { return String(r[P_PK]); });
}

// ── 4. SHEETS → SUPABASE (trigger onEdit / onChange) ───────────────────────
function onPartnershipEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  if (sheet.getName() !== P_SHEET_TAB) return; // ignora i tab filtro

  const row = e.range.getRow();
  if (row < P_DATA_START) return;
  if (P_PROP.getProperty(p_rowLockKey_(row)) === "1") return;

  const headers = p_getHeaders_(sheet);
  const pkIdx   = p_pkColumnIndex_(headers);
  const vals    = sheet.getRange(row, 1, 1, headers.length).getValues()[0];
  const pkValue = vals[pkIdx];
  if (!pkValue) return; // niente nome → niente sync

  p_sbUpsert_(p_rowToRecord_(headers, vals));
  console.log("Sheets→Supabase: upsert '" + pkValue + "'");
}

function onPartnershipChange(e) {
  if (!e || e.changeType !== "REMOVE_ROW") return;
  if (P_PROP.getProperty(P_LOCK_KEY) === "1") return;

  const sheet   = p_getSheet_();
  const headers = p_getHeaders_(sheet);
  const pkIdx   = p_pkColumnIndex_(headers);
  const last    = sheet.getLastRow();

  const sheetPks = new Set();
  if (last >= P_DATA_START) {
    const data = sheet.getRange(P_DATA_START, pkIdx + 1, last - P_DATA_START + 1, 1).getValues();
    data.forEach(function(r) { if (r[0]) sheetPks.add(String(r[0])); });
  }

  const toDelete = p_sbFetchAllPks_().filter(function(pk) { return !sheetPks.has(pk); });
  if (toDelete.length) {
    p_sbDeleteIn_(toDelete);
    console.log("Sheets→Supabase: delete batch " + toDelete.length);
  }
}

// ── 5. SUPABASE → SHEETS (Web App endpoint) ────────────────────────────────
function doPost(e) {
  try {
    if (P_WH_SECRET() && (!e.parameter || e.parameter.secret !== P_WH_SECRET())) {
      return ContentService.createTextOutput(JSON.stringify({ error: "unauthorized" }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    if (e.parameter && e.parameter.t && e.parameter.t !== "partnership") {
      return ContentService.createTextOutput(JSON.stringify({ ok: true, ignored: true }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    const body       = JSON.parse(e.postData.contents);
    const type       = body.type;
    const record     = body.record;
    const old_record = body.old_record;

    const sheet    = p_getSheet_();
    const headers  = p_getHeaders_(sheet);
    const pkIdx    = p_pkColumnIndex_(headers);
    const writable = p_getWritableCols_(sheet, headers.length);
    let touchedRow = -1;
    let setGlobalLock = false;

    try {
      if (type === "DELETE") {
        const row = p_findRowByPK_(sheet, pkIdx, old_record && old_record[P_PK]);
        if (row > 0) {
          touchedRow = row;
          P_PROP.setProperty(p_rowLockKey_(row), "1");
          P_PROP.setProperty(P_LOCK_KEY, "1");
          setGlobalLock = true;
          sheet.deleteRow(row);
          console.log("Supabase→Sheets: delete '" + old_record[P_PK] + "'");
        }
      } else {
        const pkValue = record[P_PK];
        const rowVals = p_recordToRow_(headers, record);
        const row     = p_findRowByPK_(sheet, pkIdx, pkValue);
        const target  = (row > 0) ? row : p_findAppendRow_(sheet, pkIdx);
        touchedRow = target;
        P_PROP.setProperty(p_rowLockKey_(target), "1");
        p_writeRow_(sheet, target, headers, rowVals, writable);
        console.log("Supabase→Sheets: " + (row > 0 ? "update" : "insert") + " '" + pkValue + "' riga " + target);
      }
      return ContentService.createTextOutput(JSON.stringify({ ok: true }))
        .setMimeType(ContentService.MimeType.JSON);
    } finally {
      if (touchedRow > 0) {
        Utilities.sleep(1500);
        P_PROP.deleteProperty(p_rowLockKey_(touchedRow));
      }
      if (setGlobalLock) P_PROP.deleteProperty(P_LOCK_KEY);
    }
  } catch (err) {
    console.error("doPost: " + err);
    return ContentService.createTextOutput(JSON.stringify({ error: String(err) }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// ── 6. SETUP TRIGGER (eseguire UNA SOLA VOLTA) ─────────────────────────────
function setupPartnershipTriggers() {
  const ss = SpreadsheetApp.openById(P_SHEET_ID);

  // Pulisci eventuali trigger duplicati di questo script
  ScriptApp.getProjectTriggers().forEach(function(t) {
    const fn = t.getHandlerFunction();
    if (fn === "onPartnershipEdit" || fn === "onPartnershipChange") {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger("onPartnershipEdit").forSpreadsheet(ss).onEdit().create();
  ScriptApp.newTrigger("onPartnershipChange").forSpreadsheet(ss).onChange().create();
  console.log("✓ Trigger installati: onPartnershipEdit + onPartnershipChange");
}

// ── 7. VERIFICA CONNESSIONE ────────────────────────────────────────────────
function testPartnershipConnection() {
  const url = P_SB_URL();
  const key = P_SB_KEY();
  console.log("URL: " + url);
  console.log("KEY: " + (key ? key.substring(0, 15) + "..." : "MANCANTE!"));

  if (!url || !key) {
    console.error("✗ SUPABASE_URL o SUPABASE_KEY mancanti nelle Proprietà script");
    return;
  }

  const resp = UrlFetchApp.fetch(
    url + "/rest/v1/" + P_TABLE + "?select=" + encodeURIComponent(P_PK) + "&limit=3",
    { headers: p_sbHeaders_(), muteHttpExceptions: true }
  );
  console.log("Status: " + resp.getResponseCode());
  console.log("Body: " + resp.getContentText().substring(0, 400));

  if (resp.getResponseCode() === 200) {
    const rows = JSON.parse(resp.getContentText());
    console.log("✓ Connessione OK — " + rows.length + " righe campione lette");
  } else {
    console.error("✗ Errore — controlla URL/KEY/CHECK constraint/RLS");
  }
}

// ── 8. PUSH INIZIALE Sheet → Supabase ──────────────────────────────────────
function initialPushPartnershipToSupabase() {
  const sheet = p_getSheet_();
  const last  = sheet.getLastRow();
  if (last < P_DATA_START) { console.log("Foglio vuoto"); return; }

  const headers = p_getHeaders_(sheet);
  const rows    = sheet.getRange(P_DATA_START, 1, last - P_DATA_START + 1, headers.length).getValues();
  const recs    = rows
    .map(function(r) { return p_rowToRecord_(headers, r); })
    .filter(function(r) { return r[P_PK] !== null && r[P_PK] !== ""; });

  try {
    P_PROP.setProperty(P_LOCK_KEY, "1");
    for (let i = 0; i < recs.length; i += 200) p_sbUpsert_(recs.slice(i, i + 200));
    console.log("✓ Push iniziale completato: " + recs.length + " righe inviate a Supabase");
  } finally {
    P_PROP.deleteProperty(P_LOCK_KEY);
  }
}

// ── 9. STILE: copia stile header del master sui 4 tab filtro ───────────────
function styleFilterTabs() {
  const ss     = SpreadsheetApp.openById(P_SHEET_ID);
  const master = ss.getSheetByName(P_SHEET_TAB);
  if (!master) { console.error("Foglio master '" + P_SHEET_TAB + "' non trovato"); return; }

  const src = master.getRange(P_HEADER_ROW, 1);
  const style = {
    bg:       src.getBackground(),
    fg:       src.getFontColor(),
    fontSize: src.getFontSize(),
    fontFam:  src.getFontFamily(),
    fontWgt:  src.getFontWeight(),
    hAlign:   src.getHorizontalAlignment(),
    vAlign:   src.getVerticalAlignment(),
    wrap:     src.getWrapStrategy(),
    rowH:     master.getRowHeight(P_HEADER_ROW),
  };
  console.log("Stile sorgente: " + JSON.stringify(style));

  P_FILTER_TABS.forEach(function(name) {
    const sh = ss.getSheetByName(name);
    if (!sh) { console.warn("Tab '" + name + "' non trovato — saltato"); return; }

    const lastCol = Math.max(sh.getLastColumn(), 1);
    sh.getRange(1, 1, 1, lastCol)
      .setBackground(style.bg)
      .setFontColor(style.fg)
      .setFontFamily(style.fontFam)
      .setFontSize(style.fontSize)
      .setFontWeight(style.fontWgt)
      .setHorizontalAlignment(style.hAlign)
      .setVerticalAlignment(style.vAlign)
      .setWrapStrategy(style.wrap);

    sh.setRowHeight(1, style.rowH);
    sh.setFrozenRows(1);

    for (let c = 1; c <= lastCol; c++) sh.autoResizeColumn(c);

    console.log("✓ Stile applicato a '" + name + "' (" + lastCol + " colonne)");
  });
}

// ── 10. APPLICA CONVALIDA STATUS sulla colonna E del master ────────────────
function applyStatusValidation() {
  const sheet = p_getSheet_();
  const lastRow = Math.max(sheet.getMaxRows(), 2000);
  const range = sheet.getRange(P_DATA_START, 5, lastRow - 1, 1); // colonna E
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(P_STATUS_VALUES, true)
    .setAllowInvalid(false)
    .setHelpText("Valori ammessi: " + P_STATUS_VALUES.join(", "))
    .build();
  range.setDataValidation(rule);
  console.log("✓ Convalida status applicata a E" + P_DATA_START + ":E" + lastRow);
}

// ── 11. DIAGNOSTICA ────────────────────────────────────────────────────────
function diagnostics() {
  const ss     = SpreadsheetApp.openById(P_SHEET_ID);
  const master = ss.getSheetByName(P_SHEET_TAB);

  console.log("── Foglio ──");
  console.log("ID:        " + P_SHEET_ID);
  console.log("Master:    " + (master ? "OK ('" + P_SHEET_TAB + "')" : "MANCA!"));
  if (master) {
    console.log("Righe:     " + master.getLastRow());
    console.log("Colonne:   " + master.getLastColumn());
    console.log("Headers:   " + p_getHeaders_(master).join(" | "));
  }

  console.log("\n── Tab filtro ──");
  P_FILTER_TABS.forEach(function(name) {
    const sh = ss.getSheetByName(name);
    console.log((sh ? "✓ " : "✗ ") + name);
  });

  console.log("\n── Properties ──");
  console.log("SUPABASE_URL:   " + (P_SB_URL() ? "OK" : "MANCA"));
  console.log("SUPABASE_KEY:   " + (P_SB_KEY() ? "OK" : "MANCA"));
  console.log("WEBHOOK_SECRET: " + (P_WH_SECRET() ? "OK" : "MANCA"));

  console.log("\n── Trigger ──");
  ScriptApp.getProjectTriggers().forEach(function(t) {
    console.log("• " + t.getHandlerFunction() + " (" + t.getEventType() + ")");
  });
}
