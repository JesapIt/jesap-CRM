from django.db import models

class Socio(models.Model):
    email = models.EmailField(unique=True)
    # Aggiungi qui gli altri campi che hai su Supabase (nome, cognome, ecc.)

    class Meta:
        db_table = 'soci' # Il nome della tabella su Supabase
        managed = False   # Fondamentale: dice a Django "non toccare questa tabella, esiste già"