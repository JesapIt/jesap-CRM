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

