-- ============================================================
-- LEADS — BD Lead Control (JESAP)
-- Tabella centrale per pipeline BD (Business Development).
-- Sync bidirezionale con Google Sheet "BD Lead Control" via Apps Script.
--
-- Naming convention: UPPERCASE come EVENTI, FORMAZIONI, PROGETTI, SOCI, PARTNERSHIP.
-- Eseguire una sola volta su Supabase SQL Editor.
-- ============================================================

-- Extension richiesta per il trigger updated_at automatico
CREATE EXTENSION IF NOT EXISTS moddatetime;

-- ============================================================
-- TABELLA principale
-- ============================================================
CREATE TABLE IF NOT EXISTS "LEADS" (
  -- PK generata da Apps Script: "LEAD-YYYYMMDD-HHMMSS-N"
  lead_id              text PRIMARY KEY,

  -- Timestamps business
  data_creazione       date NOT NULL DEFAULT CURRENT_DATE,
  data_primo_contatto  date,

  -- Anagrafica azienda
  azienda              text NOT NULL,
  titolare_azienda     text,

  -- Referente (denormalizzato come nel foglio)
  referente            text,           -- "Nome Cognome" concatenato
  nome_referente       text,
  cognome_referente    text,
  email_referente      text,
  telefono             text,

  -- Business
  prodotto_servizio    text,
  area                 text,           -- CSV: "M&C, HR" (multi-area mantenuto)
  owner                text,           -- nome socio assegnato (text per ora, FK in v2)

  -- Pipeline / status
  fase_attuale         text NOT NULL DEFAULT 'Nuovo',
  stato_lead           text NOT NULL DEFAULT 'Attiva',
  stato_contratto      text DEFAULT 'Da preparare',
  priorita             text,           -- Alta / Media / Bassa

  -- Forecasting
  valore_stimato       numeric(12,2),  -- € senza simbolo (es. 23.00)
  probabilita          smallint CHECK (probabilita IS NULL OR probabilita BETWEEN 0 AND 100),

  -- Calcolato AUTOMATICAMENTE: valore_stimato × probabilita / 100
  valore_ponderato     numeric(12,2)
    GENERATED ALWAYS AS (
      CASE
        WHEN valore_stimato IS NOT NULL AND probabilita IS NOT NULL
        THEN ROUND(valore_stimato * probabilita / 100.0, 2)
        ELSE NULL
      END
    ) STORED,

  -- Prossimo step
  prossima_azione      text,
  data_prossima_azione date,

  -- Alert automatico: true se data_prossima_azione scaduta E lead ancora attiva
  alert_follow_up      boolean
    GENERATED ALWAYS AS (
      data_prossima_azione IS NOT NULL
      AND data_prossima_azione < CURRENT_DATE
      AND stato_lead = 'Attiva'
    ) STORED,

  -- Google Drive
  drive_folder_id      text,
  link_cartella_drive  text,
  cartella_fase_drive  text,

  -- Audit log automatico (JSON array di eventi)
  storico_aggiornamenti jsonb NOT NULL DEFAULT '[]'::jsonb,

  -- Audit Supabase-managed
  ultimo_aggiornamento timestamptz NOT NULL DEFAULT now(),
  created_at           timestamptz NOT NULL DEFAULT now()
);

-- ============================================================
-- INDICI per query frequenti
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_leads_fase     ON "LEADS"(fase_attuale);
CREATE INDEX IF NOT EXISTS idx_leads_stato    ON "LEADS"(stato_lead);
CREATE INDEX IF NOT EXISTS idx_leads_owner    ON "LEADS"(owner);
CREATE INDEX IF NOT EXISTS idx_leads_priorita ON "LEADS"(priorita);
CREATE INDEX IF NOT EXISTS idx_leads_alert    ON "LEADS"(alert_follow_up) WHERE alert_follow_up = TRUE;
CREATE INDEX IF NOT EXISTS idx_leads_valore   ON "LEADS"(valore_ponderato DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_leads_prossima ON "LEADS"(data_prossima_azione);
CREATE INDEX IF NOT EXISTS idx_leads_azienda  ON "LEADS" USING gin (to_tsvector('italian', azienda));

-- ============================================================
-- TRIGGER 1: aggiorna ultimo_aggiornamento ad ogni UPDATE
-- ============================================================
DROP TRIGGER IF EXISTS leads_set_updated ON "LEADS";
CREATE TRIGGER leads_set_updated
  BEFORE UPDATE ON "LEADS"
  FOR EACH ROW
  EXECUTE FUNCTION moddatetime(ultimo_aggiornamento);

-- ============================================================
-- TRIGGER 2: append a storico_aggiornamenti su cambio fase/stato/owner
-- ============================================================
CREATE OR REPLACE FUNCTION log_lead_change() RETURNS trigger AS $$
BEGIN
  IF OLD.fase_attuale     IS DISTINCT FROM NEW.fase_attuale
     OR OLD.stato_lead    IS DISTINCT FROM NEW.stato_lead
     OR OLD.stato_contratto IS DISTINCT FROM NEW.stato_contratto
     OR OLD.owner         IS DISTINCT FROM NEW.owner THEN
    NEW.storico_aggiornamenti := COALESCE(OLD.storico_aggiornamenti, '[]'::jsonb)
      || jsonb_build_array(jsonb_build_object(
        'ts',           now(),
        'fase_da',      OLD.fase_attuale,    'fase_a',      NEW.fase_attuale,
        'stato_da',     OLD.stato_lead,      'stato_a',     NEW.stato_lead,
        'contratto_da', OLD.stato_contratto, 'contratto_a', NEW.stato_contratto,
        'owner_da',     OLD.owner,           'owner_a',     NEW.owner
      ));
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS leads_audit_log ON "LEADS";
CREATE TRIGGER leads_audit_log
  BEFORE UPDATE ON "LEADS"
  FOR EACH ROW
  EXECUTE FUNCTION log_lead_change();

-- ============================================================
-- ROW LEVEL SECURITY (RLS) — disabilitata: l'accesso passa
-- sempre dal pooler con service role key dal backend Django.
-- ============================================================
ALTER TABLE "LEADS" DISABLE ROW LEVEL SECURITY;

-- ============================================================
-- DATI DI TEST (opzionale, da rimuovere in prod dopo verifica)
-- ============================================================
INSERT INTO "LEADS" (
  lead_id, data_primo_contatto, azienda, referente, nome_referente, cognome_referente,
  email_referente, prodotto_servizio, area, owner, fase_attuale, stato_lead,
  stato_contratto, priorita, valore_stimato, probabilita, prossima_azione,
  data_prossima_azione
) VALUES
  ('LEAD-20260609-025327-1', '2026-06-09', 'Acme Corp', 'Mario Rossi', 'Mario', 'Rossi',
   'mario.rossi@acme.com', 'Consulenza digitale', 'IT', 'Totti Francesco',
   'Nuovo', 'Attiva', 'Da preparare', 'Alta', 5000.00, 30, 'Call di scoperta', '2026-06-20'),
  ('LEAD-20260609-025327-2', '2026-05-15', 'Beta Startup', 'Anna Bianchi', 'Anna', 'Bianchi',
   'anna@beta.io', 'Sito web vetrina', 'M&C', 'Totti Francesco',
   'Proposta inviata', 'Attiva', 'Bozza', 'Media', 1200.00, 60, 'Followup email', '2026-06-15'),
  ('LEAD-20260609-025327-3', '2026-04-01', 'Jesap C.', 'Laura Bianchi', 'Laura', 'Bianchi',
   'laura.bianchi@example.com', 'Data Platform Assessment', 'M&C, HR', 'Totti Francesco',
   'Vinta', 'Vinta', 'Firmato', 'Media', 23.00, 100, 'Avviare progetto', '2026-06-21')
ON CONFLICT (lead_id) DO NOTHING;

-- ============================================================
-- VERIFICA: dovrebbe ritornare 3 righe + valore_ponderato calcolato
-- ============================================================
-- SELECT lead_id, azienda, fase_attuale, valore_stimato, probabilita, valore_ponderato, alert_follow_up
-- FROM "LEADS" ORDER BY data_creazione DESC;
