"""Test schema-level: choices presenti sui model + validazione full_clean."""
import pytest
from django.core.exceptions import ValidationError

from dashboard import choices as ch
from dashboard.models import Partnership, Progetti

# full_clean() → validate_unique() → SELECT.
pytestmark = pytest.mark.django_db


# ============================================================
# Choices declared on model fields
# ============================================================

PROGETTI_FIELD_CHOICES = [
    ('tipologia_cliente', ch.TIPOLOGIA_CLIENTE_VALUES),
    ('tipologia_di_progetto', ch.TIPOLOGIA_PROGETTO_VALUES),
    ('stato', ch.STATO_PROGETTO_VALUES),
    ('area_di_pertinenza', ch.AREA_PERTINENZA_VALUES),
    ('provenienza', ch.PROVENIENZA_VALUES),
]

PARTNERSHIP_FIELD_CHOICES = [
    ('tipologia', ch.PARTNERSHIP_TIPOLOGIA_VALUES),
    ('oggetto_primario', ch.PARTNERSHIP_OGGETTO_VALUES),
    ('status_partnership', ch.PARTNERSHIP_STATUS_VALUES),
    ('durata', ch.PARTNERSHIP_DURATA_VALUES),
    ('rinnovo', ch.PARTNERSHIP_RINNOVO_VALUES),
]


@pytest.mark.parametrize('field_name,values', PROGETTI_FIELD_CHOICES)
def test_progetti_field_has_choices(field_name, values):
    field = Progetti._meta.get_field(field_name)
    assert field.choices is not None
    declared = [v for v, _ in field.choices]
    assert declared == values


@pytest.mark.parametrize('field_name,values', PARTNERSHIP_FIELD_CHOICES)
def test_partnership_field_has_choices(field_name, values):
    field = Partnership._meta.get_field(field_name)
    assert field.choices is not None
    declared = [v for v, _ in field.choices]
    assert declared == values


# ============================================================
# full_clean() rejects out-of-set values
# ============================================================

@pytest.mark.parametrize('field_name,_', PROGETTI_FIELD_CHOICES)
def test_progetti_full_clean_rejects_unknown(field_name, _):
    inst = Progetti(codice_progetto='X', **{field_name: 'XXX_NOT_VALID_XXX'})
    with pytest.raises(ValidationError) as exc:
        inst.full_clean(exclude=['codice_progetto'])
    assert field_name in exc.value.message_dict


@pytest.mark.parametrize('field_name,_', PARTNERSHIP_FIELD_CHOICES)
def test_partnership_full_clean_rejects_unknown(field_name, _):
    inst = Partnership(partnership='X', **{field_name: 'XXX_NOT_VALID_XXX'})
    with pytest.raises(ValidationError) as exc:
        inst.full_clean(exclude=['partnership'])
    assert field_name in exc.value.message_dict


# ============================================================
# full_clean() accepts every official value
# ============================================================

@pytest.mark.parametrize('field_name,value', [
    (fname, v) for fname, vals in PROGETTI_FIELD_CHOICES for v in vals
])
def test_progetti_full_clean_accepts_official(field_name, value):
    inst = Progetti(codice_progetto='X', **{field_name: value})
    # Should not raise on this field; other fields may be missing — exclude them.
    try:
        inst.full_clean(exclude=[
            f.name for f in Progetti._meta.get_fields()
            if f.name != field_name and f.name != 'codice_progetto'
        ])
    except ValidationError as e:
        assert field_name not in e.message_dict, (
            f'{field_name}={value!r} è valore ufficiale ma fallisce: {e.message_dict}'
        )


@pytest.mark.parametrize('field_name,value', [
    (fname, v) for fname, vals in PARTNERSHIP_FIELD_CHOICES for v in vals
])
def test_partnership_full_clean_accepts_official(field_name, value):
    inst = Partnership(partnership='X', **{field_name: value})
    try:
        inst.full_clean(exclude=[
            f.name for f in Partnership._meta.get_fields()
            if f.name != field_name and f.name != 'partnership'
        ])
    except ValidationError as e:
        assert field_name not in e.message_dict, (
            f'{field_name}={value!r} è valore ufficiale ma fallisce: {e.message_dict}'
        )


# ============================================================
# url_drive: URLField, db_column "URL Drive", optional
# ============================================================

# ============================================================
# Auto-generazione CODICE PROGETTO in save()
# ============================================================

def test_save_generates_codice_on_create():
    p = Progetti(nome_progetto='Cesop 2', data_inizio='27/09/2023')
    p.save()
    assert p.codice_progetto == 'CE0923'


def test_save_does_not_change_codice_on_update():
    p = Progetti(nome_progetto='Cesop 2', data_inizio='27/09/2023')
    p.save()
    assert p.codice_progetto == 'CE0923'
    p.cliente = 'ACME'
    p.save()
    p.refresh_from_db()
    assert p.codice_progetto == 'CE0923'


def test_save_respects_explicit_codice_on_create():
    p = Progetti(codice_progetto='MANUAL-001', nome_progetto='X', data_inizio='27/09/2023')
    p.save()
    assert p.codice_progetto == 'MANUAL-001'


def test_save_without_nome_or_data_does_not_generate():
    """Senza nome o data, save() non genera (lasciato al form)."""
    p = Progetti(codice_progetto='FALLBACK', nome_progetto='', data_inizio='')
    p.save()
    assert p.codice_progetto == 'FALLBACK'


def test_progetti_url_drive_field():
    from django.db import models as djmodels
    field = Progetti._meta.get_field('url_drive')
    assert isinstance(field, djmodels.URLField)
    assert field.db_column == 'URL Drive'
    assert field.blank is True
    assert field.null is True
    assert field.max_length == 500
