"""Parser condivisi per i valori testuali importati dal Google Sheet.

Le colonne data/denaro di PROGETTI e PARTNERSHIP sono TEXT: convivono formati
diversi ("01/09/2023", "2023-09-01", "€ 1.234,56", "1234.5"). Un solo parser
evita che form, ordinamento e template interpretino lo stesso valore in modi
diversi.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

DATE_INPUT_FORMATS = ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y')

_MONEY_JUNK = re.compile(r'[^\d,.\-]')
# "1.234" / "12.345.678": punti come separatori delle migliaia (formato IT).
_DOT_THOUSANDS = re.compile(r'^-?[1-9]\d{0,2}(\.\d{3})+$')


def parse_date_text(value):
    """Ritorna una `date` o None se il valore è vuoto / non riconosciuto."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or '').strip()
    if not text:
        return None
    for fmt in DATE_INPUT_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_money(value):
    """Converte un importo testuale in Decimal.

    Ritorna None per valori vuoti, solleva ValueError se il testo non è un numero.
    """
    if value is None:
        return None
    if isinstance(value, (Decimal, int, float)):
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return None
    text = _MONEY_JUNK.sub('', text)
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    elif _DOT_THOUSANDS.match(text):
        text = text.replace('.', '')
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise ValueError(f'Importo non valido: {value!r}')
    if not amount.is_finite():
        raise ValueError(f'Importo non valido: {value!r}')
    return amount


def format_eur(amount):
    """Decimal → "1.234,50 €" (formato italiano)."""
    txt = f'{amount:,.2f}'
    return txt.replace(',', '_').replace('.', ',').replace('_', '.') + ' €'
