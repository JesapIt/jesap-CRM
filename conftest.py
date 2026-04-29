"""Global pytest config.

`setup.test_settings` (vedi pytest.ini) si occupa di stub-are dotenv e
forzare SQLite. Qui flippiamo i model unmanaged → managed in modo che
pytest-django con `--no-migrations` (syncdb) crei davvero le tabelle
nella test DB SQLite.
"""
import django

django.setup()

from dashboard.models import (  # noqa: E402
    Eventi,
    Formazioni,
    Partnership,
    Progetti,
    Soci,
)

for _m in (Eventi, Formazioni, Partnership, Progetti, Soci):
    _m._meta.managed = True

# Workaround per `%%` in db_column: il quirk di formatting del schema editor
# crea la colonna come `(in %)` mentre il compiler SELECT la cita come
# `(in %%)`. In Supabase produzione il nome reale è `(in %%)` letterale,
# ma in SQLite test creiamo/queriamo lo stesso nome (semplificato).
for _fname in ("soddisfazione_team_in_field", "soddisfazione_cliente_in_field"):
    _f = Progetti._meta.get_field(_fname)
    _f.db_column = _fname.upper()
    _f.column = _fname.upper()
