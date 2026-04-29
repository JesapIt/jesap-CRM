-- ════════════════════════════════════════════════════════════════════════════
-- PARTNERSHIP — Creazione tabella da zero + popolamento completo
-- ════════════════════════════════════════════════════════════════════════════
-- ESEGUIRE UNA SOLA VOLTA su Supabase SQL Editor.
-- Crea la tabella PARTNERSHIP con il giusto schema e CHECK constraint
-- a 5 status, droppando eventuali residui legacy. Popola con 74 righe:
--   • 50 partnership numerate (P001-P051, esclusa P045 senza nome)
--   • 6  lead "In trattativa" (senza ID)
--   • 18 partnership "Non finalizzata"
-- ════════════════════════════════════════════════════════════════════════════

-- 1) DROP residui (sicuro: CASCADE elimina anche eventuali viste dipendenti)
DROP TABLE IF EXISTS "PARTNERSHIP"        CASCADE;
DROP TABLE IF EXISTS "PARTNERSHIP_NON_FIN" CASCADE;

-- 2) CREATE TABLE
CREATE TABLE "PARTNERSHIP" (
  "Partnership"                                   TEXT PRIMARY KEY,
  "ID"                                            TEXT,
  "Tipologia"                                     TEXT,
  "Oggetto primario della partnership"            TEXT,
  "Status partnership"                            TEXT,
  "Data firma"                                    TEXT,
  "ANNO"                                          INTEGER,
  "Durata"                                        TEXT,
  "Rinnovo"                                       TEXT,
  "Data ultimo rinnovo"                           TEXT,
  "Data fine prevista"                            TEXT,
  "Numero di progetti prodotti dalle Partnership" TEXT,
  "Numero di partecipanti"                        TEXT,
  "Contatti"                                      TEXT,
  "Cartella sul drive"                            TEXT,
  "URL Cartella"                                  TEXT,
  "Vantaggi partner"                              TEXT,
  "Compenso economico"                            BOOLEAN DEFAULT FALSE,
  CONSTRAINT "PARTNERSHIP_status_check"
    CHECK ("Status partnership" IS NULL OR "Status partnership" IN (
      'Attiva',
      'Conclusa',
      'In fase di rinnovo',
      'In trattativa',
      'Non finalizzata'
    ))
);

CREATE INDEX idx_partnership_status ON "PARTNERSHIP"("Status partnership");
CREATE INDEX idx_partnership_anno   ON "PARTNERSHIP"("ANNO");
CREATE INDEX idx_partnership_id     ON "PARTNERSHIP"("ID");

COMMENT ON TABLE "PARTNERSHIP" IS 'JESAP — Partnership unificate. PK = nome. Status governa la tab di visualizzazione (Django/Sheets).';

-- 3) INSERT righe principali (50 partnership numerate)
INSERT INTO "PARTNERSHIP" (
  "Partnership","ID","Tipologia","Oggetto primario della partnership",
  "Status partnership","Data firma","ANNO","Durata","Rinnovo",
  "Data ultimo rinnovo","Data fine prevista",
  "Numero di progetti prodotti dalle Partnership","Numero di partecipanti",
  "Contatti","Cartella sul drive","URL Cartella","Vantaggi partner","Compenso economico"
) VALUES
('Hinc Coop','P001',NULL,NULL,'Attiva','6/5/2022',2022,'Indeterminata',NULL,NULL,'-',NULL,NULL,NULL,'07_HINC Coop','https://drive.google.com/drive/u/4/folders/1gvEQlBE8Q7rgZTBdsNM2E5Sk3Yaf42tk',NULL,FALSE),
('Catòlica Consulting Linked','P002',NULL,NULL,'Attiva','20/6/2022',2022,'Indeterminata','Rinnovo tacito',NULL,NULL,NULL,NULL,NULL,'Catòlica Consulting Linked','https://drive.google.com/drive/u/5/folders/1IIVtNESed-2BJhvTamYzZSWFH7ZBriX7',NULL,FALSE),
('IMUN Italia','P003',NULL,NULL,'Conclusa','5/10/2022',2022,NULL,NULL,NULL,NULL,NULL,NULL,E'nicholas.tommasini@gmail.com\ninfo@munitalia.it','25. IMUN Italia','https://drive.google.com/drive/u/4/folders/1_J-W8hULUjIGqCJcYVuOEKMWo3w_iG21',NULL,FALSE),
('LinkHub','P004',NULL,NULL,'Attiva','12/10/2022',2022,'Indeterminata',NULL,NULL,NULL,NULL,NULL,NULL,'12_Linkhub','https://drive.google.com/drive/u/4/folders/1KSOtZ05qAk-3fbZLxSaIPF3M3DYBzUDk',NULL,FALSE),
('BIP Consulting','P005',NULL,NULL,'Attiva','17/10/2022',2022,'Indeterminata','Indefinito',NULL,'-',NULL,NULL,'benedetta.silvestri@bip-group.com','06. BIP Consulting','https://drive.google.com/drive/u/4/folders/130LkPBigIAG-AYIQ4wHEpwsxSV82kl3x',NULL,FALSE),
('Hunters Group','P006',NULL,NULL,'Attiva','22/11/2022',2022,'Indeterminata',NULL,NULL,'-',NULL,NULL,'alessia.fazzolari@huntersgroup.com','20. Hunters Group','https://drive.google.com/drive/u/4/folders/1o-NdIGNjLstUmm48juvV81DhPkpK6BUV',NULL,FALSE),
('Quidgest','P007',NULL,NULL,'Attiva','8/3/2023',2023,'3 anni',NULL,NULL,'8/3/2026',NULL,NULL,NULL,'29. Quidgest','https://drive.google.com/drive/u/4/folders/1qtEDLYBs4GZ-KAwlSccYyW0FiQP6oRG7','Post',FALSE),
('Joule','P008',NULL,NULL,'Conclusa','16/3/2023',2023,'1 anno',NULL,NULL,'16/3/2024',NULL,NULL,'info@joulecompany.it','14. Joule','https://drive.google.com/drive/u/4/folders/1mllqrbmI3NrOdeMo_1DwJr2UwSi9cOvP',NULL,FALSE),
('Cnc Media','P009',NULL,NULL,'Attiva','12/4/2023',2023,'Indeterminata','Indefinito',NULL,NULL,NULL,NULL,NULL,'30. Cnc media','https://drive.google.com/drive/u/4/folders/1WtfUYxTfoexh4OXViPuhdtisfuwKCGyf',NULL,FALSE),
('Studio Malena','P010',NULL,NULL,'Conclusa','21/4/2023',2023,'1 anno',NULL,NULL,'20/4/2024',NULL,NULL,'dott.antoniomalena@gmail.com','31. Studio Malena','https://drive.google.com/drive/u/4/folders/1fnLbvtuIgLLACuZIxqLMBGSPZd8bOAuc','Post e stories',FALSE),
('Marketers Club Venezia','P011',NULL,NULL,'Conclusa','10/5/2023',2023,'Circoscritta all''evento',NULL,NULL,'16/7/2023',NULL,NULL,NULL,'32. Marketers','https://drive.google.com/drive/u/4/folders/1N0wuD51FkhoFOWU2NLk2Z983LwHuBQ5t',NULL,FALSE),
('JECOMM','P012',NULL,NULL,'Conclusa','13/6/2023',2023,'1 anno',NULL,NULL,'13/6/2024',NULL,NULL,NULL,'JECOMM','https://drive.google.com/drive/u/4/folders/1--jpx4I1Atj6noYW3FzobUtef0AQd5Kg',NULL,FALSE),
('InnovUp','P013',NULL,NULL,'Conclusa','8/7/2023',2023,'2 anni','Comunicare intenzione di rinnovo',NULL,'8/7/2025',NULL,NULL,E'info@innovup.net\nlaura.fornara@innovup.net','34. Innovup','https://drive.google.com/drive/u/4/folders/1n7LA4NLyBkxjkfYmxU_s-hPvNb85ASQc',NULL,FALSE),
('Buono & Partners','P014',NULL,NULL,'Conclusa','10/7/2023',2023,'1 anno','Indefinito',NULL,'10/7/2024',NULL,NULL,'b.buono@buonopartners.com','33. Buono & Partners','https://drive.google.com/drive/u/4/folders/1HwT0zxF6m2wQkTRMCb6OSZZgoVpeLMRG',NULL,FALSE),
('Zeta Jobs Academy','P015',NULL,NULL,'Conclusa','25/9/2023',2023,'1 anno',NULL,NULL,'25/9/2024',NULL,NULL,NULL,'70. Zeta Jobs Academy','https://drive.google.com/drive/u/4/folders/1VM4TiLLYxsOeBq_nRa_6FX0L1b-s7fQK','Post',FALSE),
('LVenture','P016',NULL,NULL,'Conclusa','11/11/23',2023,'1 anno',NULL,NULL,'11/11/2024',NULL,NULL,'pietro.nobili@lventuregroup.com','37. LVenture Group','https://drive.google.com/drive/u/4/folders/1Cg7SlsYjW64a6WZqyA-lyBkwhZhlKSt0',NULL,FALSE),
('Giovani Universitari in Parlamento','P017',NULL,NULL,'Conclusa','23/11/2023',2023,'Circoscritta all''evento',NULL,NULL,'-',NULL,NULL,NULL,NULL,NULL,NULL,FALSE),
('Studio Legale Prolaw','P018','Azienda','Formazione','Conclusa','12/1/2024',2024,'6 mesi',NULL,'2/9/2024','2/9/2025',NULL,'2',E's.toro@prolaw.it\ni.manca@prolaw.it','79. Studio Legale Prolaw','https://drive.google.com/drive/folders/1S1w1-gap4hoTLCdJ9i3FTDJ8v1jt7z2_','Post, Esternalizzazione parziale e totale servizi, 1 articolo mensile',FALSE),
('Nova Talent','P019','Azienda','Visibilità','Conclusa','17/2/2024',2024,'1 anno',NULL,NULL,'17/2/2025',NULL,'2','davide.lauritano@novatalent.com','83. Nova Talent','https://drive.google.com/drive/folders/1LdgY5be3r1ceh-BGBXhMxyIxf3oJzUop',NULL,FALSE),
('EFI','P020',NULL,NULL,'Conclusa','21/2/2024',2024,'Circoscritta all''evento','Indefinito',NULL,'22/3/2024',NULL,NULL,E'info@efi-italia.it\nkevin.giorgis@efi-italia.it','82. EFI','https://drive.google.com/drive/folders/1LG3w36-GwAp9UWHEoOKyUSX9evAM_my5',NULL,FALSE),
('Cesop HR','P021','Azienda','Visibilità','Conclusa','13/3/2024',2024,'1 anno','Comunicare intenzione di rinnovo',NULL,'13/3/2025','1','2',E'amministrazione@cesop.it\nf.dechiara@cesop.it\nc.serafini@cesop.it','80. CESOP  Partnership long term','https://drive.google.com/drive/folders/1V47_Sn3msEBuvd0UCoV6cdLue4RIBr-A',NULL,TRUE),
('VGen Finance','P022','Azienda','Visibilità','Attiva','15/3/2024',2024,'Indeterminata','Rinnovo tacito',NULL,'-',NULL,'2','ludovica.franchitti@vgen.it','6. VGen','https://drive.google.com/drive/folders/1mW38U3eY0U4onFHO9dejEf51RENJZMub','Post, sponsorizzazione eventi, partecipazione e supporto logistico negli eventi organizzati con JESAP',FALSE),
('Rome Future Week','P023','Azienda','Visibilità','Conclusa','25/8/2023',2024,'Circoscritta all''evento',NULL,'30/4/2024','22/9/2024',NULL,'2','federica@scaicomunicazione.com','11. Rome Future Week','https://drive.google.com/drive/folders/1K46aCuosCxJu1jIZSXJMQ0soY8P8Fue1','Post e storie',FALSE),
('Assoconsult','P024','Azienda','Formazione','Attiva','14/5/2024',2024,'1 anno',NULL,NULL,'14/5/2025','1','2','segreteriapresidenza@assoconsult.org','38.Assoconsult','https://drive.google.com/drive/u/0/folders/1kGNr4xyXtAdjqfWRTxSOgNDdj1nfOADY','Post, Esternalizzazione parziale e totale servizi, 1 articolo mensile',FALSE),
('Cambly','P025','Azienda','Altro','Conclusa','1/6/2024',2024,'1 anno',NULL,NULL,'1/6/2025',NULL,'2','simona@cambly.com','Cambly','https://drive.google.com/drive/u/0/folders/1164AEQ-y3YWu0Ahl1vEGTW45MVdKnHtV','Post',FALSE),
('Redige','P026','Azienda','Formazione','Conclusa','6/6/2024',2024,'1 anno',NULL,NULL,'6/6/2025',NULL,'2','pontonigianluca@gmail.com   team@redige.it','44. Redige','https://drive.google.com/drive/u/0/folders/1LtCbIEjpOPuFnCyqbv8yJ5t6eJKfrxo9','Post, sponsorizzazione con il Tavolo Romano',FALSE),
('JEMORE','P027','JE italiana','Formazione','Conclusa','14/6/2024',2024,'1 anno','Comunicare intenzione di rinnovo',NULL,'14/6/2025',NULL,'2',NULL,'JEMORE','https://drive.google.com/drive/u/0/folders/1aXg41FCLXUCnTrhR9Bj_EPhUzb7MNf3O','Formazioni Audit, erogazione Business Game a tema Marketing o IT, exchange sessions IT, coinvolgimento in progetti esistenti o futuri',FALSE),
('Pioda','P028','Azienda','Visibilità','Conclusa','4/11/2022',2024,'1 anno',NULL,'3/7/2024','3/7/2025',NULL,'2',NULL,'23. Pioda','https://drive.google.com/drive/folders/1-NOxeVgTLkitiBoDlp7Wo6zLkAKfC9p-',NULL,FALSE),
('GM Ambiente','P029','Azienda','Formazione','Conclusa','12/7/2024',2024,'1 anno',NULL,NULL,'12/7/2025',NULL,'2','v.castellani@gmambiente.it','GM Ambiente & Energia','https://drive.google.com/drive/u/0/folders/1MpOlSWDqVl7pBrMqC_6vfRa6E0QMORY3','Post per formazioni, consigliare la realtà ai nostri clienti',FALSE),
('Auxiell','P030','Azienda','Formazione','Conclusa','23/7/2024',2024,'1 anno',NULL,NULL,'23/7/2025',NULL,'2','giacomo.bisatto@auxiell.com arianna.amatulli@xva-services.com','40. Auxiell','https://drive.google.com/drive/folders/1K46aCuosCxJu1jIZSXJMQ0soY8P8Fue1','Post e Live Stories',FALSE),
('Career Boost','P031','Azienda','Formazione','Conclusa','9/8/2024',2024,'1 anno','Tacito per un anno',NULL,'9/8/2025','3','2','giacomo.suriano@careerboost.it','26. Career Boost','https://drive.google.com/drive/u/0/folders/1LNu07fShJySq7xuOWHFTKSwgQegTPGhj','3 storie mensili, 4 post annuali',FALSE),
('Creo Finance','P032','Azienda','Formazione','Conclusa','2/9/2024',2024,'1 anno','Comunicare intenzione di rinnovo',NULL,'2/9/2025',NULL,'2','d.raciti@creofinance.it','Creo Finance','https://drive.google.com/drive/u/0/folders/1Oc6sdUtJCF47IfZvA0n8iMjnq9CUsp_c','Post, Esternalizzazione Servizi',FALSE),
('Go Bravo','P033','Azienda','Progetto','Conclusa','26/9/2024',2024,'6 mesi','Comunicare intenzione di rinnovo',NULL,'26/3/2025','1','2','sandra.cordoba@gobravo.it','Go Bravo','https://drive.google.com/drive/u/0/folders/1QIWqXCnJTkKHr7Zm1mnDO4iJWaSlAjMy','Company visit e contenuti',TRUE),
('Scientifica Venture Capital','P034','Azienda','Altro','Attiva','23/11/2023',2024,'1 anno',NULL,'2/10/2024','2/10/2025',NULL,'2','roberta@scientifica.vc','36. Scientifica Venture Capital','https://drive.google.com/drive/folders/16QVuVUaaSiTntOWiPXqCTqJQDkwcxMuE',NULL,FALSE),
('JEMP','P035','JE italiana','Formazione','Attiva','6/7/2021',2024,'1 anno',NULL,'4/12/2024','4/12/2025',NULL,'2',NULL,'JEMP','https://drive.google.com/drive/u/0/folders/1lLOYiHKXbHwVWYt-1VYNJ3C5y4FUJjE6',NULL,FALSE),
('Learnn','P036','Azienda','Formazione','Attiva',NULL,NULL,NULL,NULL,'12/12/2024',NULL,NULL,NULL,NULL,NULL,NULL,NULL,FALSE),
('JEVE Ca Foscari','P037','JE italiana','Formazione','Attiva','28/7/2022',2024,'1 anno','Comunicare intenzione di rinnovo','31/12/2024','31/12/2025',NULL,'2',NULL,'JEVE Ca'' Foscari','https://drive.google.com/drive/u/0/folders/1eLw4rzSyHUNjGQ2sECTzMDDZczaPIDt3',NULL,FALSE),
('Tigle','P038','Azienda','Progetto','Attiva','16/4/2024',2025,'1 anno','Comunicare intenzione di rinnovo','15/1/2025','15/1/2026','1','2','info@wwnnet.it','[1_39] Tigle','https://drive.google.com/drive/u/0/folders/15H19REjhGHc7V-S0cGhAZ2CpMqzQMqj8',NULL,FALSE),
('NCode studio','P039','Azienda','Visibilità','Attiva','4/3/2025',2025,'1 anno','Comunicare intenzione di rinnovo',NULL,'4/3/2026',NULL,'2',NULL,'33. NCode Studio','https://drive.google.com/drive/folders/17xuJM1uISFITWsjFjamqLdvH_Vq0JRx2?hl=it',NULL,TRUE),
('JEVIS','P040','JE italiana','Formazione','Attiva','10/3/2025',2025,'1 anno','Comunicare intenzione di rinnovo',NULL,'10/3/2026',NULL,'2',NULL,'32. JEVIS','https://drive.google.com/drive/folders/1UwI2DcKT9X6bRXWYM6hUM4rr1mL0Ggim?hl=it',NULL,FALSE),
('TedXSapienza','P041',NULL,'Visibilità','Attiva','14/3/2025',2025,'1 anno','Comunicare intenzione di rinnovo',NULL,'14/3/2026',NULL,'2',NULL,'35. TedXSapienza','https://drive.google.com/drive/folders/1KlEDad2LlPPFzncHGrUb5qzJGIL0tWAr?hl=it',NULL,FALSE),
('JEParma','P042','JE italiana','Formazione','Attiva','18/3/2025',2025,'1 anno','Comunicare intenzione di rinnovo',NULL,'18/3/2026',NULL,'2',NULL,'34. JEParma','https://drive.google.com/drive/folders/1iBLCZ5fthYAdrJaeq7i1I5hDOfxYuVyq?hl=it',NULL,FALSE),
('CeSFFI','P043','Azienda','Formazione','Attiva','29/4/2025',2025,'1 anno',NULL,NULL,'29/5/2026',NULL,'2',NULL,'36. CeSFFI','https://drive.google.com/drive/folders/17PnV6aMpa_t_sX7qwpCc4UAyFrYS0-IH?usp=drive_link',NULL,FALSE),
('AdLab','P044','Azienda','Visibilità','Attiva','8/5/2025',2025,'1 anno',NULL,NULL,'8/5/2026',NULL,'2',NULL,'37. AdLab','https://drive.google.com/drive/folders/11W7olHigAgHV8BURiQP9CGWgK3HES6Pv?usp=drive_link',NULL,FALSE),
('AMPM Consulting','P046',NULL,NULL,'Attiva',NULL,NULL,'Indeterminata',NULL,NULL,NULL,NULL,NULL,'info@ampmconsulting.it','28. AMPM Consulting','https://drive.google.com/drive/folders/1m6Lnt89ls2NnYWQmJB7SnueEBLT8uHf1',NULL,FALSE),
('Up2Lab','P047',NULL,NULL,'Attiva',NULL,NULL,'Indeterminata',NULL,NULL,NULL,NULL,NULL,'info@up2lab.it','21. Up2Lab','https://drive.google.com/drive/folders/1lsV5hm0VeGjl3HfHUyvda2ryJ5SOa0L_','Esternalizzazione servizi',FALSE),
('HeartBrain','P048','Azienda','Formazione',NULL,'9/6/2025',2025,'Circoscritta all''evento',NULL,NULL,'9/6/2026',NULL,'2',NULL,NULL,NULL,NULL,TRUE),
('Needs Startup Association','P049','Azienda','Visibilità',NULL,'04/09/2026',2026,'Circoscritta all''evento',NULL,NULL,'4/9/2025',NULL,'2',NULL,NULL,NULL,NULL,FALSE),
('Tereso','P050','Azienda','Formazione',NULL,'10/11/2026',2026,'6 mesi',NULL,NULL,'10/5/2026',NULL,'2',NULL,NULL,NULL,NULL,FALSE),
('JEMORE 2025','P051','JE italiana','Formazione',NULL,'08/12/2025',2025,'1 anno',NULL,NULL,'8/12/2026',NULL,'2',NULL,NULL,NULL,NULL,FALSE);

-- 4) INSERT lead "In trattativa" (6 righe, senza ID)
INSERT INTO "PARTNERSHIP" (
  "Partnership","Status partnership","URL Cartella","Compenso economico"
) VALUES
('Lattanzio KIBS (YouThinkPA)', 'In trattativa', 'https://drive.google.com/drive/folders/1JuzUyWixajw-oHR3Q7b4-OcAW5i4COss?usp=drive_link', FALSE),
('Young&Co',                    'In trattativa', 'https://drive.google.com/drive/folders/16k3Ylo_AJ2qceZv4lyHFqWsSg49y_Xjd?usp=drive_link', FALSE),
('XPerta',                      'In trattativa', 'https://drive.google.com/drive/folders/1q2kVqRIOYwOguscKTCYwXwvpFOMQYVLC?usp=drive_link', FALSE),
('Vickey Club',                 'In trattativa', 'https://drive.google.com/drive/folders/1nATGOTX7GfHjILzeLlw7RNrMRWlHquGD?usp=drive_link', FALSE),
('Antonio Scirica',             'In trattativa', 'https://drive.google.com/drive/folders/1jiRvbD7ExAI6sObyub-sDznLGxzXaRlp?usp=drive_link', FALSE),
('NextLeaders Forbes',          'In trattativa', 'https://drive.google.com/drive/folders/15oaMulLLwLNDaaZdEhtQh6r7mXLO_8pE?usp=drive_link', FALSE);

-- 5) INSERT non finalizzate (18 righe)
INSERT INTO "PARTNERSHIP" (
  "Partnership","Status partnership","Contatti","Data firma","ANNO","Cartella sul drive","Compenso economico"
) VALUES
('Sei Ventures',                            'Non finalizzata','Ludovico Uva Gianmaria Zoino',                    '01/09/2023', 2023, '69. Sei Ventures',                                          FALSE),
('Get On Board',                            'Non finalizzata','valerio.guida@getnboardeducation.com',            '01/03/2024', 2024, '42. Get on board',                                          FALSE),
('Trenitalia',                              'Non finalizzata','f.tucciarelli@trenitalia.it',                     '01/03/2024', 2024, '43. Trenitalia',                                            FALSE),
('Domò',                                    'Non finalizzata','ceccariniflaminia@gmail.com',                     '01/04/2024', 2024, '45. Domò',                                                  FALSE),
('TIM',                                     'Non finalizzata',NULL,                                              '01/03/2024', 2024, '48. TIM',                                                   FALSE),
('Angelini Ventures',                       'Non finalizzata','Martina.palmese@angeliniventures.com',            '01/06/2024', 2024, '49. Angelini Ventures',                                     FALSE),
('Enel',                                    'Non finalizzata','Michele Tremori',                                 '01/06/2024', 2024, '50. Enel',                                                  FALSE),
('Elsa',                                    'Non finalizzata','Andrea Schippa',                                  '01/06/2023', 2023, '66. ELSA',                                                  FALSE),
('Fastweb',                                 'Non finalizzata','Elisabetta Boldrini',                             '01/10/2023', 2023, '68. Fastweb',                                               FALSE),
('Adopera',                                 'Non finalizzata','Rossana Marcon Daniela Troiani',                  '01/08/2023', 2023, '71. Adopera',                                               FALSE),
('Palliative Marketing Association',        'Non finalizzata','Danilo Serra Michele Corengia',                   '01/10/2023', 2023, '73. International Association of Palliative Marketing',     FALSE),
('Starting Growth',                         'Non finalizzata',NULL,                                              NULL,         NULL, '76. Starting Growth',                                       FALSE),
('Seedble',                                 'Non finalizzata',NULL,                                              NULL,         NULL, '77. Seedble',                                               FALSE),
('Forum della Meritocrazia',                'Non finalizzata',NULL,                                              NULL,         NULL, '78. Forum della Meritocrazia',                              FALSE),
('Startupper for a day',                    'Non finalizzata','Gian Lorenzo Marchioni Flavio Mancosu',           '01/12/2023', 2023, '81. Startupper for a day',                                  FALSE),
('Skillio',                                 'Non finalizzata','skillio888@gmail.com',                            '01/08/2024', 2024, NULL,                                                        FALSE),
('Giffoni Hub',                             'Non finalizzata','orazio@giffonihub.com',                           '01/08/2024', 2024, 'Giffoni Hub',                                               FALSE),
('Bonus X',                                 'Non finalizzata','chiara.pagano@bonusx.it',                         '01/08/2024', 2024, 'BonusX',                                                    FALSE);

-- 6) RLS (Row Level Security) — apri lettura/scrittura via service_role
--    (Default: tabella pubblica disabilitata → solo service_role legge)
--    Se vuoi che anche la chiave anon legga, abilita RLS e aggiungi una policy.
--    Per ora lascio SENZA RLS — service_role passa sempre.

-- 7) VERIFICA — esegui questa SELECT per controllare il caricamento
SELECT
  "Status partnership" AS status,
  COUNT(*)             AS quante
FROM "PARTNERSHIP"
GROUP BY "Status partnership"
ORDER BY "Status partnership" NULLS LAST;

-- Risultato atteso:
--   Attiva               | 22
--   Conclusa             | 24
--   In trattativa        |  6
--   Non finalizzata      | 18
--   NULL                 |  4   (P048 HeartBrain, P049 Needs, P050 Tereso, P051 JEMORE 2025)
--   ─────────────────────────
--   Totale: 74 righe
