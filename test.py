import smtplib

# --- INSERISCI SOLO LA TUA PASSWORD APP QUI ---
email_account = "noreply@jesap.it"
password_app = "INSERISCI_QUI_LA_TUA_PASSWORD_DI_16_LETTERE" 
# ----------------------------------------------

print("🔄 Tentativo di connessione a smtp.gmail.com sulla porta 587...")

try:
    # Forza la connessione ai server di Google
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.set_debuglevel(1) # Stampa tutto
    
    print("🔄 Avvio della connessione sicura (TLS)...")
    server.starttls()
    
    print(f"🔄 Tentativo di login per {email_account}...")
    server.login(email_account, password_app)
    
    print("\n✅ SBLOCCATO! LOGIN EFFETTUATO CON SUCCESSO!")
    print("Google Workspace accetta le connessioni. Il problema è nel codice di Django.")
    server.quit()

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ ERRORE DI AUTENTICAZIONE GOOGLE (SMTPAuthenticationError):")
    print(e)
    print("👉 Significato: Google Workspace ha l'accesso SMTP bloccato per le app, oppure la password è sbagliata.")
except Exception as e:
    print(f"\n❌ ALTRO ERRORE DI RETE:")
    print(e)