"""Test della generazione automatica del CODICE PROGETTO."""
from datetime import date, datetime

import pytest

from dashboard.models import Progetti
from dashboard.utils.codice_generator import (
    _extract_mmyy,
    _extract_prefix,
    _next_suffix,
    generate_codice_progetto,
)

pytestmark = pytest.mark.django_db


# ============================================================
# _extract_prefix (puro, no DB)
# ============================================================

def test_prefix_simple():
    assert _extract_prefix('Cesop 2') == 'CE'


def test_prefix_uppercase_always():
    assert _extract_prefix('cesop') == 'CE'
    assert _extract_prefix('CESOP') == 'CE'


def test_prefix_handles_accents():
    assert _extract_prefix('Économie') == 'EC'
    assert _extract_prefix('Àéiou') == 'AE'


def test_prefix_ignores_non_alpha():
    assert _extract_prefix('  123 Fall Rec') == 'FA'
    assert _extract_prefix('!!! a b c') == 'AB'


def test_prefix_short_name_pads_with_x():
    assert _extract_prefix('A') == 'AX'
    assert _extract_prefix('1 Z 2') == 'ZX'


def test_prefix_empty_raises():
    with pytest.raises(ValueError, match='NOME PROGETTO'):
        _extract_prefix('')
    with pytest.raises(ValueError, match='NOME PROGETTO'):
        _extract_prefix('   ')


def test_prefix_no_alpha_raises():
    with pytest.raises(ValueError, match='almeno una lettera'):
        _extract_prefix('123 !!!')


# ============================================================
# _extract_mmyy
# ============================================================

@pytest.mark.parametrize('value,expected', [
    ('27/09/2023', '0923'),
    ('02/10/2023', '1023'),
    ('2023-09-27', '0923'),
    ('27-09-2023', '0923'),
])
def test_mmyy_string_formats(value, expected):
    assert _extract_mmyy(value) == expected


def test_mmyy_date_object():
    assert _extract_mmyy(date(2023, 9, 27)) == '0923'


def test_mmyy_datetime_object():
    assert _extract_mmyy(datetime(2023, 10, 2)) == '1023'


def test_mmyy_invalid_raises():
    with pytest.raises(ValueError):
        _extract_mmyy('not-a-date')
    with pytest.raises(ValueError, match='DATA INIZIO'):
        _extract_mmyy('')
    with pytest.raises(ValueError, match='DATA INIZIO'):
        _extract_mmyy(None)


# ============================================================
# _next_suffix (puro, no DB)
# ============================================================

def test_next_suffix_no_existing():
    assert _next_suffix([], 'CE0923') == 'CE0923'


def test_next_suffix_first_duplicate():
    assert _next_suffix(['CE0923'], 'CE0923') == 'CE09231'


def test_next_suffix_second_duplicate():
    assert _next_suffix(['CE0923', 'CE09231'], 'CE0923') == 'CE09232'


def test_next_suffix_uses_max_not_count():
    """Dopo DELETE di un intermedio, il prossimo deve usare MAX+1."""
    # esistono solo CE0923 e CE09232 (CE09231 cancellato)
    assert _next_suffix(['CE0923', 'CE09232'], 'CE0923') == 'CE09233'


def test_next_suffix_ignores_non_matching():
    assert _next_suffix(['CE1023', 'XX0923', 'CE0923'], 'CE0923') == 'CE09231'


# ============================================================
# generate_codice_progetto (integrato, con DB)
# ============================================================

def test_generates_simple_codice():
    code = generate_codice_progetto('Cesop 2', '27/09/2023')
    assert code == 'CE0923'


def test_generates_with_iso_date():
    code = generate_codice_progetto('Fall Rec 2023', '2023-10-02')
    assert code == 'FA1023'


def test_increments_counter_on_duplicate():
    Progetti.objects.create(codice_progetto='CE0923', nome_progetto='X', data_inizio='27/09/2023')
    code = generate_codice_progetto('Cesop 3', '28/09/2023')
    assert code == 'CE09231'


def test_increments_counter_multiple():
    Progetti.objects.create(codice_progetto='CE0923', nome_progetto='X', data_inizio='27/09/2023')
    Progetti.objects.create(codice_progetto='CE09231', nome_progetto='Y', data_inizio='27/09/2023')
    code = generate_codice_progetto('Cesop 4', '29/09/2023')
    assert code == 'CE09232'


def test_max_suffix_after_delete():
    Progetti.objects.create(codice_progetto='CE0923', nome_progetto='X', data_inizio='27/09/2023')
    Progetti.objects.create(codice_progetto='CE09232', nome_progetto='Z', data_inizio='27/09/2023')
    # CE09231 mai esistito (o cancellato)
    code = generate_codice_progetto('Cesop 5', '30/09/2023')
    assert code == 'CE09233'


def test_different_month_no_collision():
    Progetti.objects.create(codice_progetto='CE0923', nome_progetto='X', data_inizio='27/09/2023')
    code = generate_codice_progetto('Cesop 2', '02/10/2023')
    assert code == 'CE1023'


def test_raises_on_empty_nome():
    with pytest.raises(ValueError):
        generate_codice_progetto('', '27/09/2023')


def test_raises_on_empty_data():
    with pytest.raises(ValueError):
        generate_codice_progetto('Cesop', '')
