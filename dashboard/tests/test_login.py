"""
QA suite — Login & Autenticazione (JESAP CRM).
Esecuzione: `python manage.py test dashboard.tests`
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

User = get_user_model()


class LoginInputAnomaliTests(TestCase):
    """1. Input anomali: vuoti, null, SQL/NoSQL injection, email malformata."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="mario.rossi", email="mario.rossi@jesap.it", password="P@ssw0rd!"
        )

    def setUp(self):
        self.client = Client()
        self.url = reverse("login")

    def test_username_vuoto(self):
        r = self.client.post(self.url, {"username": "", "password": "P@ssw0rd!"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Credenziali non valide")

    def test_password_vuota(self):
        r = self.client.post(self.url, {"username": "mario.rossi", "password": ""})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Credenziali non valide")

    def test_entrambi_vuoti(self):
        r = self.client.post(self.url, {"username": "", "password": ""})
        self.assertContains(r, "Credenziali non valide")

    def test_username_null(self):
        r = self.client.post(self.url, {"password": "P@ssw0rd!"})
        self.assertContains(r, "Credenziali non valide")

    def test_password_null(self):
        r = self.client.post(self.url, {"username": "mario.rossi"})
        self.assertContains(r, "Credenziali non valide")

    def test_sql_injection_username(self):
        payloads = [
            "' OR '1'='1",
            "admin'--",
            "'; DROP TABLE auth_user; --",
            "' UNION SELECT NULL,NULL,NULL --",
        ]
        for p in payloads:
            r = self.client.post(self.url, {"username": p, "password": "x"})
            self.assertContains(r, "Credenziali non valide", msg_prefix=f"payload={p}")
            self.assertTrue(User.objects.filter(username="mario.rossi").exists())

    def test_nosql_injection_payload(self):
        payloads = ['{"$ne": null}', '{"$gt": ""}', "[$ne]=1"]
        for p in payloads:
            r = self.client.post(self.url, {"username": p, "password": p})
            self.assertContains(r, "Credenziali non valide")

    def test_email_malformata(self):
        for bad in ["@jesap.it", "mario@", "mario rossi@jesap.it", "mario@@jesap.it"]:
            r = self.client.post(self.url, {"username": bad, "password": "x"})
            self.assertContains(r, "Credenziali non valide", msg_prefix=f"input={bad}")

    def test_xss_username(self):
        r = self.client.post(
            self.url, {"username": "<script>alert(1)</script>", "password": "x"}
        )
        self.assertContains(r, "Credenziali non valide")
        self.assertNotContains(r, "<script>alert(1)</script>")


class LoginSanitizzazioneTests(TestCase):
    """2. trim() + toLowerCase() su input sporchi."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="anna.bianchi",
            email="anna.bianchi@jesap.it",
            password="Segreta123!",
        )

    def setUp(self):
        self.client = Client()
        self.url = reverse("login")

    def _login_ok(self, username):
        r = self.client.post(
            self.url, {"username": username, "password": "Segreta123!"}, follow=False
        )
        self.assertEqual(r.status_code, 302, msg=f"username={username!r}")

    def test_email_con_spazi_e_maiuscole(self):
        self._login_ok("  Anna.Bianchi@JESAP.it  ")

    def test_username_con_spazi(self):
        self._login_ok("   anna.bianchi   ")

    def test_username_uppercase(self):
        self._login_ok("ANNA.BIANCHI")

    def test_email_uppercase(self):
        self._login_ok("ANNA.BIANCHI@JESAP.IT")

    def test_solo_spazi_rifiutato(self):
        r = self.client.post(self.url, {"username": "     ", "password": "Segreta123!"})
        self.assertContains(r, "Credenziali non valide")

    def test_password_NON_normalizzata(self):
        # La password deve essere case-sensitive e non trimmata.
        r = self.client.post(
            self.url, {"username": "anna.bianchi", "password": " Segreta123! "}
        )
        self.assertContains(r, "Credenziali non valide")
        r = self.client.post(
            self.url, {"username": "anna.bianchi", "password": "segreta123!"}
        )
        self.assertContains(r, "Credenziali non valide")


class LoginErroriGenericiTests(TestCase):
    """3. Messaggio identico per utente inesistente vs password sbagliata."""

    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(
            username="luca.verdi", email="luca.verdi@jesap.it", password="Vera1234!"
        )

    def setUp(self):
        self.client = Client()
        self.url = reverse("login")

    def _msg(self, response):
        msgs = list(response.context["messages"])
        return [str(m) for m in msgs]

    def test_utente_inesistente(self):
        r = self.client.post(self.url, {"username": "ghost", "password": "x"})
        self.assertEqual(self._msg(r), ["Credenziali non valide."])

    def test_password_errata(self):
        r = self.client.post(self.url, {"username": "luca.verdi", "password": "wrong"})
        self.assertEqual(self._msg(r), ["Credenziali non valide."])

    def test_email_inesistente(self):
        r = self.client.post(
            self.url, {"username": "ghost@jesap.it", "password": "x"}
        )
        self.assertEqual(self._msg(r), ["Credenziali non valide."])

    def test_messaggio_identico_tra_casi(self):
        r1 = self.client.post(self.url, {"username": "ghost", "password": "x"})
        r2 = self.client.post(self.url, {"username": "luca.verdi", "password": "wrong"})
        self.assertEqual(self._msg(r1), self._msg(r2))

    def test_no_user_enumeration_via_response(self):
        import re

        r1 = self.client.post(self.url, {"username": "ghost", "password": "x"})
        r2 = self.client.post(self.url, {"username": "luca.verdi", "password": "wrong"})
        self.assertEqual(r1.status_code, r2.status_code)
        # Spoglia il CSRF token (varia ad ogni request) prima del confronto.
        scrub = lambda b: re.sub(rb'value="[A-Za-z0-9]{32,}"', b'value=""', b)
        self.assertEqual(scrub(r1.content), scrub(r2.content))


class LoginEdgeCasesUXTests(TestCase):
    """4. Timeout/latenza, invii multipli, race condition."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="paola.neri",
            email="paola.neri@jesap.it",
            password="Top!Secret9",
        )

    def setUp(self):
        self.client = Client()
        self.url = reverse("login")

    def test_invii_multipli_stesse_credenziali(self):
        for _ in range(5):
            self.client.logout()
            r = self.client.post(
                self.url,
                {"username": "paola.neri", "password": "Top!Secret9"},
                follow=False,
            )
            self.assertEqual(r.status_code, 302)

    def test_invii_multipli_credenziali_errate(self):
        for _ in range(10):
            r = self.client.post(self.url, {"username": "paola.neri", "password": "x"})
            self.assertContains(r, "Credenziali non valide")

    def test_backend_lento_non_crasha(self):
        # Simula latenza nel backend di auth.
        original = __import__(
            "dashboard.auth_backends", fromlist=["EmailOrUsernameModelBackend"]
        ).EmailOrUsernameModelBackend.authenticate

        def slow(self, request, username=None, password=None, **kw):
            import time

            time.sleep(0.5)
            return original(self, request, username, password, **kw)

        with patch(
            "dashboard.auth_backends.EmailOrUsernameModelBackend.authenticate", slow
        ):
            r = self.client.post(
                self.url, {"username": "paola.neri", "password": "Top!Secret9"}
            )
            self.assertEqual(r.status_code, 302)

    def test_payload_enorme_non_crasha(self):
        big = "a" * 10_000
        r = self.client.post(self.url, {"username": big, "password": big})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Credenziali non valide")

    def test_get_login_renderizza(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)


class LoginAutorizzazioneTests(TestCase):
    """5. is_active=False, account sospeso, permessi mancanti."""

    @classmethod
    def setUpTestData(cls):
        cls.attivo = User.objects.create_user(
            username="att.ivo", email="attivo@jesap.it", password="Active1!"
        )
        cls.sospeso = User.objects.create_user(
            username="sos.peso",
            email="sospeso@jesap.it",
            password="Suspended1!",
            is_active=False,
        )

    def setUp(self):
        self.client = Client()
        self.url = reverse("login")

    def test_utente_sospeso_non_autenticato(self):
        r = self.client.post(
            self.url, {"username": "sos.peso", "password": "Suspended1!"}
        )
        self.assertContains(r, "Credenziali non valide")

    def test_utente_sospeso_via_email(self):
        r = self.client.post(
            self.url, {"username": "sospeso@jesap.it", "password": "Suspended1!"}
        )
        self.assertContains(r, "Credenziali non valide")

    def test_messaggio_sospeso_uguale_a_password_errata(self):
        r1 = self.client.post(
            self.url, {"username": "sos.peso", "password": "Suspended1!"}
        )
        r2 = self.client.post(self.url, {"username": "att.ivo", "password": "wrong"})
        msgs = lambda r: [str(m) for m in list(r.context["messages"])]
        self.assertEqual(msgs(r1), msgs(r2))

    def test_utente_attivo_autenticato(self):
        r = self.client.post(
            self.url, {"username": "att.ivo", "password": "Active1!"}, follow=False
        )
        self.assertEqual(r.status_code, 302)

    def test_session_non_creata_per_sospeso(self):
        self.client.post(
            self.url, {"username": "sos.peso", "password": "Suspended1!"}
        )
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_riattivazione_dopo_sospensione(self):
        self.sospeso.is_active = True
        self.sospeso.save()
        r = self.client.post(
            self.url, {"username": "sos.peso", "password": "Suspended1!"}, follow=False
        )
        self.assertEqual(r.status_code, 302)
