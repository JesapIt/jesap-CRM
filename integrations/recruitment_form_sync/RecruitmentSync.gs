/**
 * Sync candidature: foglio risposte del form di candidatura → CRM JESAP.
 *
 * Ogni 5 minuti invia al CRM le righe nuove (dall'ultima inviata in poi).
 * Il CRM deduplica: rinviare righe già inviate è innocuo (vedi syncTutto).
 *
 * SETUP (Estensioni → Apps Script sul foglio RISPOSTE del form):
 *   Impostazioni progetto → Proprietà script:
 *     CRM_URL     = https://crm.jesap.it/recruitment/api/candidature/
 *     CRM_TOKEN   = <stesso valore di RECRUITMENT_WEBHOOK_TOKEN su Railway>
 *     SHEET_NAME  = nome del tab con le risposte (es. "Risposte del modulo 1")
 *     HEADER_ROW  = riga delle intestazioni (default 1)
 *   Poi esegui una volta: testConnessione → installaTrigger
 */

const PROPS = PropertiesService.getScriptProperties();
const BATCH = 20;

function _cfg() {
  const cfg = {
    url: PROPS.getProperty('CRM_URL'),
    token: PROPS.getProperty('CRM_TOKEN'),
    sheetName: PROPS.getProperty('SHEET_NAME'),
    headerRow: parseInt(PROPS.getProperty('HEADER_ROW') || '1', 10),
  };
  if (!cfg.url || !cfg.token || !cfg.sheetName) {
    throw new Error('Proprietà script mancanti: servono CRM_URL, CRM_TOKEN, SHEET_NAME');
  }
  return cfg;
}

function _post(cfg, risposte) {
  const resp = UrlFetchApp.fetch(cfg.url, {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + cfg.token },
    payload: JSON.stringify({ risposte: risposte }),
    muteHttpExceptions: true,
  });
  return { code: resp.getResponseCode(), body: resp.getContentText() };
}

function _valore(v) {
  if (v instanceof Date) return v.toISOString();
  return v === null || v === undefined ? '' : String(v);
}

/** Trigger ogni 5 minuti: invia le righe nuove. */
function syncNuoveCandidature() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return;
  try {
    const cfg = _cfg();
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(cfg.sheetName);
    if (!sheet) throw new Error('Tab non trovato: ' + cfg.sheetName);

    const ultimaInviata = parseInt(PROPS.getProperty('LAST_SYNCED_ROW') || String(cfg.headerRow), 10);
    const lastRow = sheet.getLastRow();
    if (lastRow <= ultimaInviata) return;

    const lastCol = sheet.getLastColumn();
    const headers = sheet.getRange(cfg.headerRow, 1, 1, lastCol).getValues()[0].map(String);

    for (let start = ultimaInviata + 1; start <= lastRow; start += BATCH) {
      const n = Math.min(BATCH, lastRow - start + 1);
      const rows = sheet.getRange(start, 1, n, lastCol).getValues();
      const risposte = rows
        .filter(r => r.some(c => c !== '' && c !== null))
        .map(r => {
          const o = {};
          headers.forEach((h, i) => { if (h) o[h] = _valore(r[i]); });
          return o;
        });

      if (risposte.length) {
        const res = _post(cfg, risposte);
        if (res.code !== 200 && res.code !== 201) {
          // 409 = nessuna sessione aperta nel CRM; 401 = token errato. Riprova al prossimo giro.
          console.error('CRM ha risposto ' + res.code + ': ' + res.body);
          return;
        }
        const errori = (JSON.parse(res.body).risultati || []).filter(x => x.stato === 'errore');
        if (errori.length) console.warn('Righe ' + start + '-' + (start + n - 1) + ' con errori: ' + JSON.stringify(errori));
      }
      PROPS.setProperty('LAST_SYNCED_ROW', String(start + n - 1));
    }
  } finally {
    lock.releaseLock();
  }
}

/** Reinvia TUTTE le righe (es. dopo aver aperto una nuova sessione nel CRM). Innocuo: il CRM deduplica. */
function syncTutto() {
  PROPS.deleteProperty('LAST_SYNCED_ROW');
  syncNuoveCandidature();
}

/** Verifica URL + token senza inviare dati. */
function testConnessione() {
  const res = _post(_cfg(), []);
  if (res.code === 200) console.log('✓ OK — CRM raggiungibile, sessione aperta: ' + JSON.parse(res.body).sessione);
  else if (res.code === 409) console.warn('⚠ CRM raggiungibile ma nessuna sessione aperta: aprila dal CRM (Recruitment → Impostazioni).');
  else console.error('✗ Errore ' + res.code + ': ' + res.body);
}

/** Installa il trigger ogni 5 minuti (esegui una volta). */
function installaTrigger() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'syncNuoveCandidature')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('syncNuoveCandidature').timeBased().everyMinutes(5).create();
  console.log('✓ Trigger installato: syncNuoveCandidature ogni 5 minuti');
}
