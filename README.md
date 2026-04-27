# 🚀 JESAP CRM - Guida Rapida

Benvenuto! Segui questi 5 step per avviare il progetto sul tuo PC in modo facile e veloce.

### 1. Clona il progetto e apri VS Code

Apri il terminale del tuo computer e digita:

```bash
git clone https://github.com/JesapIt/jesap-CRM.git
cd jesap-CRM
code .

```

### 2. Crea e attiva l'Ambiente Virtuale

Nel terminale integrato di VS Code, digita:

```bash
python -m venv venv

```

**Per attivare l'ambiente:**

* **Windows:** `.\venv\Scripts\activate`
*(Se ricevi un errore rosso su Windows, sbloccalo prima con: `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`)*
* **Mac/Linux:** `source venv/bin/activate`

### 3. Installa le librerie

Assicurati di vedere la scritta `(venv)` nel terminale e digita:

```bash
pip install -r requirements.txt

```

### 4. Configura il file di sicurezza

Cerca il file `.env.example`, fai Copia e Incolla nella stessa cartella e rinomina la copia semplicemente in **`.env`** (con il punto all'inizio). I dati fittizi al suo interno sono già pronti per farti lavorare!

### 5. Avvia il Database e il Server

```bash
python manage.py migrate
python manage.py runserver

```

🎉 **Fatto!** Apri il browser e vai su: **[http://127.0.0.1:8000/](https://www.google.com/search?q=http://127.0.0.1:8000/)**

---

## Test

La suite di test usa **pytest** + **pytest-django**. Tempo di esecuzione atteso: ~70 secondi per 257 test.

### Esecuzione

Con il `venv` attivo:

```bash
pytest
```

Oppure invocando direttamente l'interprete del venv:

```bash
venv/Scripts/python.exe -m pytest
```

Opzioni utili:

```bash
pytest -v                 # output verbose, mostra ogni test
pytest -x                 # ferma al primo errore
pytest dashboard/tests/test_choices.py   # esegui solo un file
pytest -k normalize       # esegui solo i test che matchano il nome
```

### Configurazione

La suite è configurata tramite tre file alla radice del progetto:

- **`pytest.ini`** — imposta `DJANGO_SETTINGS_MODULE = setup.test_settings` e l'opzione `--no-migrations`.
- **`setup/test_settings.py`** — settings dedicati ai test. Esegue lo stub di `dotenv.load_dotenv` **prima** di importare `setup.settings`, così l'`.env` reale del progetto non viene letto. Forza `DATABASES` a SQLite in-memory: i test non toccano mai Supabase.
- **`conftest.py`** — esegue `django.setup()` e applica i workaround descritti sotto (flip di `Meta.managed`, rinomina di `db_column` problematici).

L'opzione `--no-migrations` fa creare lo schema della test DB tramite **syncdb diretto**, senza eseguire le migration del progetto. Vantaggio: avvio rapido. **Limite: eventuali bug nelle migration non vengono intercettati dai test** — vanno verificati a parte (`python manage.py migrate` su un DB di staging).

### Avvertenze (quirks importanti)

Questi punti sono compromessi consapevoli: chi modifica il codice di Progetti/Partnership deve esserne consapevole.

#### 1. `Meta.managed = True` forzato in fase di test

I modelli `Eventi`, `Formazioni`, `Soci`, `Progetti`, `Partnership`, `PartnershipNonFin` in produzione hanno `Meta.managed = False` (lo schema è gestito direttamente da Supabase). In `conftest.py` viene fatto un flip a `managed = True` solo durante i test, in modo che `syncdb` crei davvero le tabelle nella SQLite di test.

**Conseguenza:** lo schema della test DB è generato dai modelli Django, non da Supabase. Differenze tra i due schemi (tipi di colonna, vincoli, default) possono nascondere bug che si manifestano solo in produzione. Verificare sempre manualmente le modifiche di campo su un'istanza Supabase di staging.

#### 2. Campi con `db_column` contenente `%%`

Alcuni campi di `Progetti` (es. `soddisfazione_team_in_field`, `soddisfazione_cliente_in_field`) hanno `db_column` con `%%` letterale. C'è un quirk di Django: lo schema editor espande `%%` → `%` durante il `CREATE TABLE`, ma il compiler SQL del SELECT cita la stringa letterale `%%`. Risultato: in SQLite il nome colonna creato e quello interrogato non combaciano.

In `conftest.py` questi `db_column` vengono **rinominati solo per i test**.

**Conseguenza:** se si modifica il `db_column` di uno di questi campi, i test possono continuare a passare mentre la produzione si rompe (o viceversa). Verificare sempre il comportamento contro Supabase reale.

#### 3. `pytest.mark.django_db` obbligatorio per `is_valid()` / `full_clean()`

I file `test_forms.py` e `test_models.py` usano `pytestmark = pytest.mark.django_db` a livello di modulo. Questo perché `ModelForm.is_valid()` chiama internamente `validate_unique()` che esegue una `SELECT` sulla DB; lo stesso vale per `Model.full_clean()`. Senza il marker, pytest-django blocca l'accesso al DB e i test falliscono con `RuntimeError: Database access not allowed`.

Quando si aggiungono nuovi test che istanziano un `ModelForm` o invocano `full_clean()`, ricordarsi di includere il marker (a livello di modulo o di funzione).

### Cosa coprono i test

| File | N° test | Copertura |
|------|---------|-----------|
| `test_choices.py` | 80 | Valori letterali della planilha (case + accenti), struttura delle costanti `*_CHOICES`, `normalize_to_choice` (case-insensitive, blank, nessun match, lead interno, apostrofo). |
| `test_forms.py` | 90 | `ChoiceField` con widget `Select`, rifiuto di valori fuori set, accettazione di tutti i valori ufficiali, normalizzazione legacy nel `__init__`, backcompat di `In trattativa`. |
| `test_models.py` | 56 | Presenza di `choices=` sui field, `full_clean()` rifiuta valori fuori set e accetta quelli ufficiali. |
| `test_views.py` | 20 | GET form 200, presenza di `<select>` con le option corrette nell'HTML, POST validi (creano e redirigono), POST invalidi (200 con errore di form), dropdown dei filtri letti da `choices.py`, tab Lead filtra `In trattativa`. |
| `test_login.py` | 31 | Suite di sicurezza preesistente (input anomali, sanitizzazione, errori generici, autorizzazione). |

### Aggiungere o modificare test

I nuovi test vanno in `dashboard/tests/test_*.py`. Si usano fixture pytest e `parametrize` per varianti. Esempio sintetico tratto da `test_choices.py`:

```python
import pytest
from dashboard import choices as ch

@pytest.mark.parametrize('raw,expected', [
    ('in corso', 'In corso'),
    ('IN CORSO', 'In corso'),
    ('  Concluso  ', 'Concluso'),
])
def test_normalize_to_choice_case_insensitive(raw, expected):
    assert ch.normalize_to_choice(raw, ch.STATO_PROGETTO_VALUES) == expected
```

Linee guida:

- Per test che istanziano `ModelForm` o chiamano `full_clean()`: aggiungere `pytestmark = pytest.mark.django_db` in cima al file.
- Per test su view che richiedono autenticazione: usare la fixture `auth_client` definita in `test_views.py`.
- Preferire `parametrize` invece di copiare-incollare assert simili.
- I valori della planilha sono la fonte di verità: in caso di modifica, aggiornare `dashboard/choices.py` e i test si aggiornano automaticamente (le costanti `*_VALUES` sono importate dai test).
