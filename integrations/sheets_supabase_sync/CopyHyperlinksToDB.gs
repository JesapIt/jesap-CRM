/**
 * Copia i link ipertestuali dalla colonna E del tab "Partnership Non Finalizzate"
 * (foglio "[01] Progetti e Partnership") nella colonna P del tab "Partnership"
 * (foglio "DB Partnership"), abbinando per nome.
 *
 * Esegui copyHyperlinksToDB() dall'editor Apps Script associato al foglio
 * SORGENTE ("[01] Progetti e Partnership").
 */

// ---------- CONFIG (modifica se necessario) ----------
const SRC_SHEET_NAME   = 'Partnership Non Finalizzate'; // tab sorgente
const SRC_NAME_COL     = 2;   // colonna B (nome realtà). Cambia se il nome è altrove.
const SRC_LINK_COL     = 5;   // colonna E (link ipertestuale)
const SRC_HEADER_ROWS  = 1;   // quante righe di intestazione saltare

const DB_FILE_ID       = '1H0ZRXaevp1jAH4XZduwVaWsiNOcU5UH46oq-Q0gFukM';
const DB_SHEET_NAME    = 'Partnership';   // tab destinazione
const DB_NAME_COL      = 1;   // colonna A: nome partnership (PK)
const DB_URL_COL       = 16;  // colonna P: URL Cartella
const DB_HEADER_ROWS   = 1;
// ------------------------------------------------------


/** Entry point. */
function copyHyperlinksToDB() {
  const src = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SRC_SHEET_NAME);
  if (!src) throw new Error('Tab sorgente non trovato: ' + SRC_SHEET_NAME);

  const lastRow = src.getLastRow();
  if (lastRow <= SRC_HEADER_ROWS) {
    Logger.log('Nessuna riga dati nel tab sorgente.');
    return;
  }

  const numRows = lastRow - SRC_HEADER_ROWS;
  const nameRange = src.getRange(SRC_HEADER_ROWS + 1, SRC_NAME_COL, numRows, 1);
  const linkRange = src.getRange(SRC_HEADER_ROWS + 1, SRC_LINK_COL, numRows, 1);

  const names    = nameRange.getValues();
  const linkVals = linkRange.getValues();
  const linkFormulas = linkRange.getFormulas();
  const linkRichText = linkRange.getRichTextValues();

  // Mappa nome -> URL estratto
  const map = {};
  for (let i = 0; i < numRows; i++) {
    const name = String(names[i][0] || '').trim();
    if (!name) continue;

    const url = extractUrl_(linkVals[i][0], linkFormulas[i][0], linkRichText[i][0]);
    if (url) map[normalize_(name)] = url;
  }

  Logger.log('Estratti %s link.', Object.keys(map).length);

  // Apri DB Partnership e aggiorna colonna P
  const dbSS = SpreadsheetApp.openById(DB_FILE_ID);
  const dbSheet = dbSS.getSheetByName(DB_SHEET_NAME);
  if (!dbSheet) throw new Error('Tab DB non trovato: ' + DB_SHEET_NAME);

  const dbLast = dbSheet.getLastRow();
  if (dbLast <= DB_HEADER_ROWS) {
    Logger.log('DB vuoto, nulla da aggiornare.');
    return;
  }
  const dbCount = dbLast - DB_HEADER_ROWS;
  const dbNames = dbSheet.getRange(DB_HEADER_ROWS + 1, DB_NAME_COL, dbCount, 1).getValues();
  const dbUrls  = dbSheet.getRange(DB_HEADER_ROWS + 1, DB_URL_COL, dbCount, 1).getValues();

  let updated = 0;
  let unmatched = [];
  for (let i = 0; i < dbCount; i++) {
    const dbName = String(dbNames[i][0] || '').trim();
    if (!dbName) continue;
    const url = map[normalize_(dbName)];
    if (!url) continue;
    if (dbUrls[i][0] !== url) {
      dbUrls[i][0] = url;
      updated++;
    }
    delete map[normalize_(dbName)];
  }
  unmatched = Object.keys(map);

  if (updated > 0) {
    dbSheet.getRange(DB_HEADER_ROWS + 1, DB_URL_COL, dbCount, 1).setValues(dbUrls);
  }

  Logger.log('Righe aggiornate: %s', updated);
  if (unmatched.length) {
    Logger.log('Nomi sorgente senza match nel DB:\n - %s', unmatched.join('\n - '));
  }
}


/** Prova in ordine: rich-text link, formula =HYPERLINK, URL plain text. */
function extractUrl_(value, formula, richText) {
  // 1) rich text
  if (richText && typeof richText.getLinkUrl === 'function') {
    const u = richText.getLinkUrl();
    if (u) return u.trim();
  }

  // 2) =HYPERLINK("url","label")
  if (formula && typeof formula === 'string') {
    const m = formula.match(/=HYPERLINK\(\s*"([^"]+)"/i);
    if (m && m[1]) return m[1].trim();
  }

  // 3) URL come testo
  if (value && typeof value === 'string') {
    const txt = value.trim();
    if (/^https?:\/\//i.test(txt)) return txt;
  }

  return '';
}


function normalize_(s) {
  return String(s || '')
    .toLowerCase()
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}


/** Solo log, nessuna scrittura: utile per verificare match prima di lanciare. */
function dryRunHyperlinks() {
  const src = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SRC_SHEET_NAME);
  const lastRow = src.getLastRow();
  const numRows = lastRow - SRC_HEADER_ROWS;
  const names = src.getRange(SRC_HEADER_ROWS + 1, SRC_NAME_COL, numRows, 1).getValues();
  const vals  = src.getRange(SRC_HEADER_ROWS + 1, SRC_LINK_COL, numRows, 1).getValues();
  const fors  = src.getRange(SRC_HEADER_ROWS + 1, SRC_LINK_COL, numRows, 1).getFormulas();
  const rich  = src.getRange(SRC_HEADER_ROWS + 1, SRC_LINK_COL, numRows, 1).getRichTextValues();

  for (let i = 0; i < numRows; i++) {
    const n = String(names[i][0] || '').trim();
    if (!n) continue;
    const u = extractUrl_(vals[i][0], fors[i][0], rich[i][0]);
    Logger.log('%s -> %s', n, u || '(nessun link)');
  }
}
