# JESAP CRM

[![Made with Django](https://img.shields.io/badge/Django-4.2-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-336791?style=flat&logo=postgresql&logoColor=white)](https://supabase.com/)
[![Deployed on Railway](https://img.shields.io/badge/Hosting-Railway-0B0D0E?style=flat&logo=railway&logoColor=white)](https://railway.app/)
[![Email via Resend](https://img.shields.io/badge/Email-Resend-000000?style=flat)](https://resend.com/)
[![License: Proprietary](https://img.shields.io/badge/license-Internal%20use-blue)](#licenza)

**Il gestionale ufficiale di [JESAP Junior Enterprise](https://www.jesap.it/)** — una piattaforma web full-stack costruita per centralizzare la gestione di soci, partnership commerciali, progetti e processi interni dell'associazione.

🌐 **Live:** [https://crm.jesap.it](https://crm.jesap.it)

---

## Indice

- [Cos'è JESAP CRM](#cosè-jesap-crm)
- [Funzionalità](#funzionalità)
- [Stack tecnologico](#stack-tecnologico)
- [Architettura](#architettura)
- [Workflow di sviluppo](#workflow-di-sviluppo-consigliato)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [Team](#team)
- [Licenza](#licenza)

---

## Cos'è JESAP CRM

JESAP CRM è un sistema gestionale custom-built per **JESAP**, la Junior Enterprise dell'Università del Salento. Sostituisce il caos di fogli Excel e Google Sheets sparsi con un'**unica fonte di verità** per:

- 👥 **Anagrafica soci** — board, aree di competenza, ruoli, periodo associativo
- 🤝 **Partnership** — attive, lead in trattativa, non finalizzate, con tracking documentale
- 📋 **Progetti** — clienti, PM assegnati, stato avanzamento, fatturato, soddisfazione team/cliente
- 🔐 **Autenticazione & RBAC** — login con email/username, registrazione su invito, ruoli Editor/Admin
- 📧 **Comunicazioni** — reset password via email transazionale (Resend)

Tutto integrato con **sincronizzazione bidirezionale Google Sheets ↔ Supabase** via Apps Script per coesistere con i flussi di lavoro esistenti dell'associazione.

---

## Funzionalità

### 🔐 Sicurezza e autenticazione
- Login case-insensitive con email **o** username
- Registrazione a 2 step con token firmato (`signing.TimestampSigner`, scadenza 24h)
- Reset password via link email firmato
- Sessione HttpOnly + Secure + SameSite (Lax) in produzione
- HSTS preload, HTTPS forzato, SECURE_PROXY_SSL_HEADER per TLS upstream
- CSRF protection con domini whitelist configurabili
- RBAC: ruoli `Editor` (gruppo Django) + `Staff` + `Superuser`

### 📊 Gestione operativa
- **CRUD completo** Progetti e Partnership con form validati
- **Ricerca full-text** su nome, codice, PM, cliente, contatti
- **Filtri** per stato, area di pertinenza, tipologia
- **Sorting server-side cross-page** con parser type-aware (date IT/ISO, currency EUR formato 1.234,56, percentuali, testo)
- **Paginazione** con preservation di filtri e sort tra le pagine
- **Status workflow** per Partnership (Attiva ↔ Trattativa ↔ Non finalizzata)
- **Audit log** automatico delle modifiche (`AuditLog` + middleware `CurrentUserMiddleware`)

### 📋 Cataloghi e taxonomy
- Single source of truth in `dashboard/choices.py` allineato col foglio ufficiale Soci
- Normalizzazione legacy `case-insensitive` per dati storici
- Choice validation a livello di model + form + view

### 📧 Email transazionale
- Backend **Resend HTTP API** via `django-anymail` (bypass del blocco SMTP outbound di Railway)
- Template HTML + plain-text per ogni email
- Fallback `console.EmailBackend` automatico in dev

### 🏥 Reliability
- Endpoint `/healthz` per uptime monitoring (verifica connessione DB Postgres)
- Logging strutturato su stdout (catturato da Railway Logs)
- Auto-restart on failure (`restartPolicyType: ON_FAILURE`)
- Cookie hardening + clickjacking protection

---

## Stack tecnologico

### Backend
| Tech | Versione | Ruolo |
|---|---|---|
| **Python** | 3.12 | Linguaggio principale |
| **Django** | 4.2 LTS | Web framework (MVT) |
| **Gunicorn** | 23 | WSGI app server (2 workers, sync) |
| **psycopg** | 3.x | Driver PostgreSQL |
| **dj-database-url** | 3.0 | Parsing DATABASE_URL |
| **django-anymail** | 12 | Backend Resend HTTP |
| **WhiteNoise** | 6.8 | Static files con cache-busting hash |

### Database
| Tech | Versione | Ruolo |
|---|---|---|
| **PostgreSQL** | 15 (Supabase managed) | Database produzione |
| **Supabase** | — | Hosting DB + backups daily |
| **SQLite** | — | Test suite (in-memory) |

### Frontend
| Tech | Ruolo |
|---|---|
| **Django Templates** | Server-side rendering |
| **HTML5 + CSS3 vanilla** | UI custom, no framework JS |
| **JavaScript ES6+** | Interattività progressiva (toggle row, formattazione currency client-side) |
| **Design system custom** | CSS variables, no Tailwind/Bootstrap |

### Infrastruttura
| Servizio | Ruolo |
|---|---|
| **Railway** | Hosting + auto-deploy da `main` |
| **Supabase** | Database + storage + auth backup |
| **Resend** | Email transazionale (API HTTP) |
| **Aruba** | DNS (`jesap.it`) |
| **Let's Encrypt** | SSL auto-rinnovato (gestito da Railway) |
| **GitHub** | Codice + CI + branch protection |

### Integration layer
| Tech | Ruolo |
|---|---|
| **Google Apps Script** | Sync bidirezionale Sheets ↔ Supabase per soci, partnership, progetti |
| **REST API Supabase** | Endpoint di scambio dati col foglio |

### Testing
| Tech | Versione | Ruolo |
|---|---|---|
| **pytest** | 8+ | Test runner |
| **pytest-django** | 4+ | Integrazione Django |
| **257 test** | — | Suite completa (~70 sec esecuzione) |

---

## Architettura

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Google Sheets  │◄───►│  Apps Script     │◄───►│  Supabase        │
│  (foglio Soci)  │     │  (sync layer)    │     │  PostgreSQL      │
└─────────────────┘     └──────────────────┘     └────────┬─────────┘
                                                          │
                                                          │ DATABASE_URL
                                                          │ (pooler)
                                                          ▼
┌──────────────────────────────────────────────────────────────────┐
│                         RAILWAY PROD                             │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  Gunicorn (2 workers)                                      │  │
│  │  ├─ Django 4.2 (setup/, dashboard/)                        │  │
│  │  │   ├─ Views (RBAC + sorting server-side)                 │  │
│  │  │   ├─ Models (Soci, Partnership, Progetti, AuditLog)     │  │
│  │  │   ├─ Forms (validation + choice normalization)          │  │
│  │  │   └─ Templates (HTML + CSS + JS vanilla)                │  │
│  │  ├─ WhiteNoise (static files compressed)                   │  │
│  │  └─ django-anymail (Resend HTTP API)                       │  │
│  └────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
       │                              │
       ▼                              ▼
┌─────────────────┐         ┌─────────────────┐
│  Resend HTTP    │         │  Let's Encrypt  │
│  (transactional │         │  (SSL auto-     │
│   email)        │         │   rinnovo)      │
└─────────────────┘         └─────────────────┘
```

### Pattern architetturali

- **MTV (Model-Template-View)** classico Django, senza JSON API REST esposta
- **Server-side rendering**: zero SPA, zero bundling tool — semplicità prima di tutto
- **Source of truth distribuita**: Google Sheets per data entry, Supabase per source of truth runtime, Django per business logic
- **Stateless app**: nessuna sessione su disco, scaling orizzontale Railway-ready
- **Fail-fast in prod**: settings.py lancia `ImproperlyConfigured` se mancano env vars critiche

---

## Workflow di sviluppo consigliato

### Branching model

Usiamo una variante semplificata di **GitHub Flow**:

```
main  ──────●────●─────●─────●──────►  (protetto, deploy auto)
            │    │     │     │
            ●    │     │     │  feat/add-progetti-export
                 │     │     │
                 ●     │     │  fix/sorting-cross-page
                       │     │
                       ●     │  chore/upgrade-deps
                             │
                             ●  docs/update-readme
```

**Regole:**
- `main` è sempre **deployable** — Railway lo mette online a ogni merge
- Feature branch parte sempre da `main` aggiornato
- Naming convention:
  - `feat/<descrizione>` — nuove funzionalità
  - `fix/<descrizione>` — bugfix
  - `chore/<descrizione>` — maintenance / upgrade deps
  - `docs/<descrizione>` — solo documentazione
  - `refactor/<descrizione>` — refactoring senza nuove feature
- PR aperta verso `main`, mai push diretto

### Commit convention (Conventional Commits)

```
<type>(<scope>): <descrizione breve>

[body opzionale]

[footer opzionale]
```

Esempi reali dal progetto:
```
feat(deploy): railway.app config + production hardening
fix(sorting): server-side cross-page sorting (was per-page only)
fix(email): switch from SMTP to Resend HTTP API via django-anymail
chore(deps): bump django-anymail to 12.0
```

**Types:** `feat` `fix` `chore` `docs` `refactor` `test` `perf` `style` `ci`

### Code review

Ogni PR deve avere:
- [ ] **1 reviewer minimo** (configurato in branch protection)
- [ ] **Test passano** (quando avremo CI attiva)
- [ ] **Descrizione del "perché"** del cambiamento, non solo del "cosa"
- [ ] **Screenshot** se modifica UI
- [ ] **Aggiornamento `.env.example`** se aggiungi env vars

### Quality gates

Prima del merge, controlla:
1. `python manage.py check --deploy` — niente warning di sicurezza
2. `pytest` — tutti i test passano
3. `python manage.py makemigrations --check` — niente migration mancanti
4. Naming consistente coi pattern esistenti
5. Niente segreti hardcoded (Dependabot + push protection lo bloccano)

### Convenzioni di codice

- **Snake_case** per Python (PEP 8)
- **kebab-case** per URL paths
- **Italiano** per nomi business (Soci, Partnership, Progetti), **inglese** per nomi tecnici (views, forms, models)
- **Choices in `dashboard/choices.py`** — mai hardcodare stringhe nelle view
- **Form validators** per logica di pulizia, non nelle view
- **`order_by()` esplicito** sempre, mai assumere ordering implicito
- **`get_object_or_404`** invece di `objects.get()` per fail gracefully
- **Logging stdout** con `print(..., file=sys.stderr, flush=True)` per messaggi di boot, `logger.info/error` per runtime

---

## Deployment

### Continuous Deployment

**Ogni merge su `main` deploya automaticamente su Railway.** Il flusso completo:

```
git push origin main
        │
        ▼
   GitHub webhook → Railway
        │
        ▼
   NIXPACKS builder (Python 3.12)
        │
        ▼
   pip install -r requirements.txt
        │
        ▼
   collectstatic --noinput
        │
        ▼
   migrate --noinput (release phase)
        │
        ▼
   gunicorn setup.wsgi --bind 0.0.0.0:$PORT --workers 2 --timeout 120
        │
        ▼
   Healthcheck su /healthz
        │
        ▼
   🟢 LIVE
```

**Tempi tipici:** 2-4 minuti dal `git push` al sito live.

### Environment variables (Railway)

Variabili critiche (vedi `.env.example`):

| Variable | Esempio | Obbligatoria |
|---|---|---|
| `DEBUG` | `False` | ✅ |
| `SECRET_KEY` | `<random 50 chars>` | ✅ |
| `DATABASE_URL` | `postgresql://...pooler.supabase.com:5432/postgres` | ✅ |
| `ALLOWED_HOSTS` | `crm.jesap.it,*.up.railway.app` | ✅ |
| `CSRF_TRUSTED_ORIGINS` | `https://crm.jesap.it,https://*.up.railway.app` | ✅ |
| `RESEND_API_KEY` | `re_xxxxxxxxx` | ✅ |
| `DEFAULT_FROM_EMAIL` | `JESAP CRM <noreply@jesap.it>` | ✅ |
| `USE_POSTGRES` | `1` | ✅ |
| `PGSSLMODE` | `require` | Consigliato |
| `LOG_LEVEL` | `INFO` | Opzionale |

### Monitoring stack

| Servizio | A cosa serve | Link |
|---|---|---|
| **Railway Dashboard** | Deploy logs, metriche, env vars | [railway.app](https://railway.app) |
| **Supabase Dashboard** | Query DB, backup, logs Postgres | [supabase.com](https://supabase.com) |
| **Resend Dashboard** | Storico email inviate, bounce rate | [resend.com](https://resend.com) |
| **Status Railway** | Down/degraded della piattaforma | [status.railway.com](https://status.railway.com) |
| **Status Supabase** | Down/degraded DB | [status.supabase.com](https://status.supabase.com) |
| **UptimeRobot** (consigliato) | Alert email se `/healthz` non risponde | [uptimerobot.com](https://uptimerobot.com) |
| **Sentry** (consigliato) | Error tracking con traceback | [sentry.io](https://sentry.io) |

---

## Roadmap

### ✅ Completato (MVP)
- Autenticazione + RBAC + reset password
- CRUD Progetti / Partnership / Soci
- Sync Google Sheets ↔ Supabase
- Deploy production-ready su Railway
- Dominio custom `crm.jesap.it` con SSL
- Email transazionale via Resend HTTP API
- Sorting server-side cross-page con parser type-aware
- Audit log automatico
- Suite di 257 test con pytest

### 🚧 Prossimi passi (Q3 2026)
- [ ] **Dashboard analytics**: KPI fatturato, soddisfazione, partnership attive nel tempo
- [ ] **Export Excel/PDF** progetti e partnership
- [ ] **Notifiche in-app** per scadenze (rinnovi partnership, milestone progetti)
- [ ] **API REST** read-only per integrazioni future (es. sito vetrina)
- [ ] **Mobile-responsive** rifinitura UI tablet/smartphone
- [ ] **CI/CD GitHub Actions** con lint + test automatici su PR

### 💭 Idee future
- Calendario eventi/formazioni integrato
- Time tracking per PM e risorse
- Document management (contratti, NDA)
- Dashboard pubblica anonimizzata per il sito JESAP
- Integrazione Slack/Discord per notifiche

---

## Team

**Lead Developer:** [@daniteg71](https://github.com/daniteg71)
**Organizzazione:** [JESAP Junior Enterprise](https://www.jesap.it/)

### Contribuire al progetto

Vuoi proporre una modifica? Sei benvenuto/a:

1. Apri una **Issue** descrivendo il problema/proposta
2. Discutiamo l'approccio
3. Forka, crea il branch, manda la PR
4. Review → merge → deploy 🚀

Linee guida dettagliate in `CONTRIBUTING.md` *(coming soon)*.

---

## Licenza

Codice **proprietario** ad uso interno JESAP Junior Enterprise.
Non distribuibile né riproducibile senza autorizzazione scritta dei proprietari.

Per richieste relative al codice, contattare il consiglio direttivo JESAP.

---

<p align="center">
  <sub>Costruito con ❤️ da JESAP per JESAP — un esempio di come una Junior Enterprise può <strong>essere cliente di se stessa</strong>.</sub>
</p>
