"""
Comando di diagnostica SMTP (Google Workspace / Gmail) con smtplib in modalità verbose.
Non usa Django send_mail: isola la connessione al server SMTP.
"""

import smtplib
import ssl
from email.mime.text import MIMEText

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Testa la connessione SMTP con debug verboso (set_debuglevel). "
        "Invia un'email di prova da EMAIL_HOST_USER a se stesso."
    )

    def handle(self, *args, **options):
        user = (getattr(settings, "EMAIL_HOST_USER", None) or "").strip()
        password = getattr(settings, "EMAIL_HOST_PASSWORD", None) or ""
        host = getattr(settings, "EMAIL_HOST", None) or "smtp.gmail.com"
        port = int(getattr(settings, "EMAIL_PORT", None) or 587)
        use_tls = bool(getattr(settings, "EMAIL_USE_TLS", True))

        self.stdout.write(f"Host SMTP: {host}:{port} (STARTTLS={use_tls})")
        self.stdout.write(f"Account (mittente/destinatario): {user!r}")

        if not user:
            self.stderr.write(
                self.style.ERROR(
                    "ERRORE: EMAIL_HOST_USER è vuoto. Controlla .env e settings."
                )
            )
            return
        if not password:
            self.stderr.write(
                self.style.ERROR(
                    "ERRORE: EMAIL_HOST_PASSWORD è vuoto. Controlla .env e settings."
                )
            )
            return

        msg = MIMEText(
            "Messaggio di prova generato da: python manage.py test_email\n"
            "Se lo ricevi, autenticazione e invio SMTP funzionano.",
            "plain",
            "utf-8",
        )
        msg["Subject"] = "Test SMTP JESAP ERP (management command)"
        msg["From"] = user
        msg["To"] = user

        server = None
        try:
            self.stdout.write(self.style.WARNING("--- Inizio conversazione SMTP (debuglevel=1) ---"))
            server = smtplib.SMTP(host, port, timeout=60)
            server.set_debuglevel(1)

            server.ehlo()
            if use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
                server.ehlo()

            server.login(user, password)
            server.sendmail(user, [user], msg.as_string())
            server.quit()
            server = None

            self.stdout.write(self.style.SUCCESS("--- Fine conversazione ---"))
            self.stdout.write(
                self.style.SUCCESS(
                    "OK: email inviata con successo (mittente e destinatario sono lo stesso indirizzo)."
                )
            )

        except smtplib.SMTPAuthenticationError as exc:
            self._print_smtp_auth_error(exc)

        except smtplib.SMTPRecipientsRefused as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"ERRORE SMTP — destinatario rifiutato: {exc!s}\n"
                    "Verifica che l'indirizzo sia consentito dalle policy del dominio."
                )
            )

        except smtplib.SMTPSenderRefused as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"ERRORE SMTP — mittente rifiutato: {exc!s}\n"
                    "Su Google Workspace: controlla restrizioni su 'Invia come' o relay."
                )
            )

        except smtplib.SMTPDataError as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"ERRORE SMTP — dati messaggio rifiutati: {exc!s}\n"
                    "Possibile blocco policy contenuti o limiti del tenant."
                )
            )

        except smtplib.SMTPConnectError as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"ERRORE SMTP — connessione fallita: {exc!s}\n"
                    "Firewall, porta 587 bloccata, o host errato. "
                    "A livello Google di solito non è un 'blocco admin' se non raggiungi proprio il server."
                )
            )

        except smtplib.SMTPException as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"ERRORE SMTP generico: {type(exc).__name__}: {exc!s}\n"
                    "Controlla i log sopra (debuglevel) per il codice di risposta del server."
                )
            )

        except OSError as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"ERRORE di rete/socket: {exc!s}\n"
                    "Rete assente, DNS, firewall locale o proxy che blocca smtp.gmail.com:587."
                )
            )

        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"ERRORE imprevisto: {type(exc).__name__}: {exc!s}"
                )
            )

        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    try:
                        server.close()
                    except Exception:
                        pass

    def _print_smtp_auth_error(self, exc: smtplib.SMTPAuthenticationError) -> None:
        self.stderr.write(self.style.ERROR(f"ERRORE DI AUTENTICAZIONE SMTP: {exc!s}"))
        self.stderr.write(
            self.style.WARNING(
                "Cause frequenti con Google Workspace / Gmail:\n"
                "  • Password normale dell'account: non va; serve una 'Password per le app' "
                "(se abilitata dall'admin) oppure OAuth2.\n"
                "  • Account senza accesso SMTP: l'amministratore può disabilitare "
                "'Accesso app meno sicure' / SMTP per utente o gruppo.\n"
                "  • 2FA attivo senza password per le app: Google rifiuta il login SMTP.\n"
                "  • Utente sospeso o policy 'Context-Aware Access' / IP che bloccano l'accesso.\n"
                "  • Codice 535 o messaggi che citano 'blocked' spesso indicano blocco lato Google "
                "o credenziali errate.\n"
                "Leggi il dettaglio nel traceback SMTP stampato sopra (debuglevel=1)."
            )
        )
