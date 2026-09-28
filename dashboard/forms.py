import re
from datetime import datetime
from decimal import Decimal
from random import randint

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator, URLValidator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from . import choices as ch
from .models import Credenziale, Lead, Partnership, Progetti, Soci, Task
from .utils.parsing import parse_date_text, parse_money


DATE_PLACEHOLDER = 'GG/MM/AAAA'


def _normalize_date_text(value):
    if value in (None, '') or not str(value).strip():
        return ''
    parsed = parse_date_text(value)
    if parsed is None:
        raise forms.ValidationError('Data non valida. Usa GG/MM/AAAA.')
    return parsed.strftime('%d/%m/%Y')


class PartnershipForm(forms.ModelForm):
    tipologia = forms.ChoiceField(
        choices=ch.PARTNERSHIP_TIPOLOGIA_CHOICES,
        required=False,
        label='Tipologia',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    oggetto_primario = forms.ChoiceField(
        choices=ch.PARTNERSHIP_OGGETTO_CHOICES,
        required=False,
        label='Oggetto primario',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    status_partnership = forms.ChoiceField(
        choices=ch.PARTNERSHIP_STATUS_CHOICES,
        required=False,
        label='Status',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    durata = forms.ChoiceField(
        choices=ch.PARTNERSHIP_DURATA_CHOICES,
        required=False,
        label='Durata',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    rinnovo = forms.ChoiceField(
        choices=ch.PARTNERSHIP_RINNOVO_CHOICES,
        required=False,
        label='Rinnovo',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    compenso_economico = forms.TypedChoiceField(
        choices=ch.BOOL_SI_NO_CHOICES,
        required=False,
        coerce=lambda v: v == 'True',
        empty_value=None,
        label='Compenso economico',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Partnership
        fields = [
            'partnership', 'id_codice', 'tipologia', 'oggetto_primario',
            'status_partnership', 'data_firma', 'anno', 'durata', 'rinnovo',
            'data_ultimo_rinnovo', 'data_fine_prevista',
            'numero_progetti', 'numero_partecipanti',
            'contatti', 'cartella_sul_drive', 'url_cartella',
            'vantaggi_partner', 'compenso_economico',
        ]
        labels = {
            'partnership': 'Nome Partnership (chiave primaria)',
            'id_codice': 'Codice (es. P001)',
            'tipologia': 'Tipologia',
            'oggetto_primario': 'Oggetto primario',
            'status_partnership': 'Status',
            'data_firma': 'Data firma',
            'anno': 'Anno',
            'durata': 'Durata',
            'rinnovo': 'Rinnovo',
            'data_ultimo_rinnovo': 'Data ultimo rinnovo',
            'data_fine_prevista': 'Data fine prevista',
            'numero_progetti': 'N° progetti',
            'numero_partecipanti': 'N° partecipanti',
            'contatti': 'Contatti',
            'cartella_sul_drive': 'Cartella Drive (nome)',
            'url_cartella': 'URL Cartella Drive',
            'vantaggi_partner': 'Vantaggi partner',
            'compenso_economico': 'Compenso economico',
        }
        widgets = {
            'partnership':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: Hinc Coop'}),
            'id_codice':           forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: P001'}),
            'data_firma':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': DATE_PLACEHOLDER}),
            'data_ultimo_rinnovo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': DATE_PLACEHOLDER}),
            'data_fine_prevista':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': DATE_PLACEHOLDER}),
            'numero_progetti':     forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}),
            'numero_partecipanti': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}),
            'contatti':            forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Una email per riga'}),
            'cartella_sul_drive':  forms.TextInput(attrs={'class': 'form-control'}),
            'url_cartella':        forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
            'vantaggi_partner':    forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'anno':                forms.NumberInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-compila status compenso da boolean
        instance = kwargs.get('instance')
        if instance is not None:
            if instance.compenso_economico is True:
                self.initial['compenso_economico'] = 'True'
            elif instance.compenso_economico is False:
                self.initial['compenso_economico'] = 'False'
            else:
                self.initial['compenso_economico'] = ''

            # Normalizza valori legacy verso i choices ufficiali (case-insensitive).
            # Così un record con "in trattativa" matcha "In trattativa", etc.
            self.initial['tipologia'] = ch.normalize_to_choice(
                getattr(instance, 'tipologia', None), ch.PARTNERSHIP_TIPOLOGIA_VALUES,
            )
            self.initial['oggetto_primario'] = ch.normalize_to_choice(
                getattr(instance, 'oggetto_primario', None), ch.PARTNERSHIP_OGGETTO_VALUES,
            )
            self.initial['status_partnership'] = ch.normalize_to_choice(
                getattr(instance, 'status_partnership', None), ch.PARTNERSHIP_STATUS_VALUES,
            )
            self.initial['durata'] = ch.normalize_to_choice(
                getattr(instance, 'durata', None), ch.PARTNERSHIP_DURATA_VALUES,
            )
            self.initial['rinnovo'] = ch.normalize_to_choice(
                getattr(instance, 'rinnovo', None), ch.PARTNERSHIP_RINNOVO_VALUES,
            )

            # PK readonly su update
            if instance.pk:
                self.fields['partnership'].disabled = True
                self.fields['partnership'].help_text = 'Chiave primaria: non modificabile.'

        for name, field in self.fields.items():
            widget = field.widget
            existing_class = widget.attrs.get('class', '').strip()
            if 'form-control' not in existing_class.split():
                widget.attrs['class'] = f"{existing_class} form-control".strip()

    def clean_partnership(self):
        nome = (self.cleaned_data.get('partnership') or '').strip()
        if not nome:
            raise forms.ValidationError('Il nome della Partnership è obbligatorio.')
        return nome

    def clean_anno(self):
        anno = self.cleaned_data.get('anno')
        if anno in (None, ''):
            return None
        try:
            anno_int = int(anno)
        except (TypeError, ValueError):
            raise forms.ValidationError('Il campo Anno deve essere un numero intero.')
        if anno_int <= 2010:
            raise forms.ValidationError('Il campo Anno deve essere maggiore di 2010.')
        return anno_int

    def _clean_int_text(self, name):
        raw = self.cleaned_data.get(name)
        if raw in (None, ''):
            return ''
        txt = str(raw).strip()
        if not txt or txt == '-':
            return txt
        try:
            int(txt)
        except ValueError:
            raise forms.ValidationError('Inserisci un numero intero valido.')
        return txt

    def clean_numero_progetti(self):
        return self._clean_int_text('numero_progetti')

    def clean_numero_partecipanti(self):
        return self._clean_int_text('numero_partecipanti')

    def clean_data_firma(self):
        return _normalize_date_text(self.cleaned_data.get('data_firma'))

    def clean_data_ultimo_rinnovo(self):
        return _normalize_date_text(self.cleaned_data.get('data_ultimo_rinnovo'))

    def clean_data_fine_prevista(self):
        return _normalize_date_text(self.cleaned_data.get('data_fine_prevista'))


# ============================================================
# Partnership "kind" forms (Lead / Non finalizzata)
# Architettura unificata: una sola tabella PARTNERSHIP separata via Status.
# PartnershipForm (sopra) resta il form "Full" permissivo. PartnershipFullForm
# è un alias backward-compatible con import storico.
# ============================================================

PartnershipFullForm = PartnershipForm


class LeadPartnershipForm(forms.ModelForm):
    """Form ridotto per Lead Partnership (status auto = In trattativa)."""

    class Meta:
        model = Partnership
        fields = ['partnership', 'url_cartella']
        labels = {
            'partnership': 'Nome Partnership',
            'url_cartella': 'URL Cartella Drive',
        }
        widgets = {
            'partnership':  forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: Hinc Coop'}),
            'url_cartella': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance is not None and instance.pk:
            self.fields['partnership'].disabled = True
            self.fields['partnership'].help_text = 'Chiave primaria: non modificabile.'

    def clean_partnership(self):
        nome = (self.cleaned_data.get('partnership') or '').strip()
        if not nome:
            raise forms.ValidationError('Il nome della Partnership è obbligatorio.')
        return nome

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.status_partnership = Partnership.STATUS_TRATTATIVA
        if commit:
            obj.save()
        return obj


class NonFinalizzataForm(forms.ModelForm):
    """Form per Partnership Non Finalizzate (status auto = Non finalizzata)."""

    class Meta:
        model = Partnership
        fields = [
            'partnership', 'contatti', 'data_firma', 'anno',
            'cartella_sul_drive', 'url_cartella',
        ]
        labels = {
            'partnership': 'Nome Realtà',
            'contatti': 'Contatti',
            'data_firma': 'Data primo contatto',
            'anno': 'Anno',
            'cartella_sul_drive': 'Cartella Drive (nome)',
            'url_cartella': 'URL Cartella Drive',
        }
        widgets = {
            'partnership':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: ACME srl'}),
            'contatti':            forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Una email per riga'}),
            'data_firma':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': DATE_PLACEHOLDER}),
            'anno':                forms.NumberInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}),
            'cartella_sul_drive':  forms.TextInput(attrs={'class': 'form-control'}),
            'url_cartella':        forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get('instance')
        if instance is not None and instance.pk:
            self.fields['partnership'].disabled = True
            self.fields['partnership'].help_text = 'Chiave primaria: non modificabile.'

    def clean_partnership(self):
        nome = (self.cleaned_data.get('partnership') or '').strip()
        if not nome:
            raise forms.ValidationError('Il nome è obbligatorio.')
        return nome

    def clean_data_firma(self):
        return _normalize_date_text(self.cleaned_data.get('data_firma'))

    def clean_anno(self):
        anno = self.cleaned_data.get('anno')
        if anno in (None, ''):
            return None
        try:
            anno_int = int(anno)
        except (TypeError, ValueError):
            raise forms.ValidationError('Il campo Anno deve essere un numero intero.')
        if anno_int <= 2010:
            raise forms.ValidationError('Il campo Anno deve essere maggiore di 2010.')
        return anno_int

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.status_partnership = Partnership.STATUS_NON_FINALIZZATA
        if commit:
            obj.save()
        return obj


def _parse_date_ddmmyyyy_to_iso(value):
    """Valore DB (qualsiasi formato data noto) → ISO per <input type="date">."""
    parsed = parse_date_text(value)
    return parsed.isoformat() if parsed else ''


def _format_iso_to_ddmmyyyy(value):
    if value in (None, ''):
        return None
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        raise forms.ValidationError('La data deve essere valida.')


def _parse_money_to_decimal(raw):
    try:
        return parse_money(raw)
    except ValueError:
        raise forms.ValidationError('Inserisci un numero valido (es: 880).')


def _format_money_eur(value):
    if value in (None, ''):
        return ''
    quantized = value.quantize(Decimal('0.01'))
    integer_part, _, decimal_part = f'{quantized:.2f}'.partition('.')
    return f'€ {integer_part},{decimal_part}'


def _extract_number_from_money(raw):
    if raw in (None, ''):
        return ''
    try:
        dec = _parse_money_to_decimal(raw)
    except forms.ValidationError:
        return ''
    if dec is None:
        return ''
    if dec == dec.to_integral_value():
        return str(int(dec))
    return str(dec.normalize())


def _extract_number_from_percentage(raw):
    if raw in (None, ''):
        return ''
    match = re.search(r'-?\d+(?:[.,]\d+)?', str(raw))
    if not match:
        return ''
    num = match.group(0).replace(',', '.')
    try:
        val = float(num)
    except ValueError:
        return ''
    if val == int(val):
        return str(int(val))
    return str(val)


class ProgettoForm(forms.ModelForm):
    tipologia_cliente = forms.ChoiceField(
        choices=ch.TIPOLOGIA_CLIENTE_CHOICES,
        required=False,
        label='Tipologia cliente',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    tipologia_di_progetto = forms.ChoiceField(
        choices=ch.TIPOLOGIA_PROGETTO_CHOICES,
        required=False,
        label='Tipologia di progetto',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    stato = forms.ChoiceField(
        choices=ch.STATO_PROGETTO_CHOICES,
        required=False,
        label='Stato',
        widget=forms.Select(attrs={'class': 'form-control', 'style': 'max-width: 220px;'}),
    )
    area_di_pertinenza = forms.ChoiceField(
        choices=ch.AREA_PERTINENZA_CHOICES,
        required=False,
        label='Area di pertinenza',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    provenienza = forms.ChoiceField(
        choices=ch.PROVENIENZA_CHOICES,
        required=False,
        label='Provenienza',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    coinvolgimento_della_pubblica_amministrazione = forms.TypedChoiceField(
        choices=ch.BOOL_SI_NO_CHOICES,
        required=False,
        coerce=lambda v: v == 'True',
        empty_value=None,
        label='Coinvolgimento della pubblica amministrazione',
        widget=forms.Select(attrs={'class': 'form-control', 'style': 'max-width: 220px;'}),
    )

    anno = forms.IntegerField(
        required=False,
        label='Anno',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'inputmode': 'numeric'}),
    )
    mese_inizio = forms.IntegerField(
        required=False,
        label='Mese inizio',
        min_value=1,
        max_value=12,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12, 'inputmode': 'numeric'}),
    )
    n_risorse_coinvolte = forms.IntegerField(
        required=False,
        label='N° risorse coinvolte',
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'inputmode': 'numeric'}),
    )

    fatturato_senza_iva_field = forms.CharField(
        required=False,
        label='Fatturato (senza IVA)',
        help_text='Inserisci solo il numero (es: 880). Verrà salvato come € 880,00.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: 880', 'inputmode': 'decimal'}),
    )
    iva = forms.CharField(
        required=False,
        label='IVA',
        help_text='Inserisci solo il numero (es: 880). Verrà salvato come € 880,00.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: 880', 'inputmode': 'decimal'}),
    )
    costi = forms.CharField(
        required=False,
        label='Costi',
        help_text='Inserisci solo il numero (es: 880). Verrà salvato come € 880,00.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: 880', 'inputmode': 'decimal'}),
    )
    profitti = forms.CharField(
        required=False,
        label='Profitti',
        help_text='Inserisci solo il numero (es: 880). Verrà salvato come € 880,00.',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: 880', 'inputmode': 'decimal'}),
    )

    soddisfazione_team_in_field = forms.IntegerField(
        required=False,
        label='Soddisfazione team',
        min_value=1,
        max_value=100,
        help_text='Inserisci solo il numero (1-100). Verrà salvato come valore %.',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100, 'inputmode': 'numeric'}),
    )
    soddisfazione_cliente_in_field = forms.IntegerField(
        required=False,
        label='Soddisfazione cliente',
        min_value=1,
        max_value=100,
        help_text='Inserisci solo il numero (1-100). Verrà salvato come valore %.',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 100, 'inputmode': 'numeric'}),
    )

    url_drive = forms.URLField(
        required=False,
        label='URL Drive',
        max_length=500,
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
    )

    class Meta:
        model = Progetti
        fields = [
            'codice_progetto',
            'nome_progetto',
            'cliente',
            'tipologia_cliente',
            'tipologia_di_progetto',
            'stato',
            'area_di_pertinenza',
            'pm',
            'provenienza',
            'data_primo_contatto',
            'data_firma_contratto',
            'data_inizio',
            'mese_inizio',
            'data_fine_contratto',
            'anno',
            'n_risorse_coinvolte',
            'fatturato_senza_iva_field',
            'iva',
            'costi',
            'profitti',
            'descrizione_servizio_offerto',
            'coinvolgimento_della_pubblica_amministrazione',
            'soddisfazione_team_in_field',
            'soddisfazione_cliente_in_field',
            'url_drive',
            'risorsa_1', 'risorsa_2', 'risorsa_3', 'risorsa_4', 'risorsa_5',
            'risorsa_6', 'risorsa_7', 'risorsa_8', 'risorsa_9', 'risorsa_10',
            'risorsa_11', 'risorsa_12', 'risorsa_13', 'risorsa_14', 'risorsa_15',
            'risorsa_16', 'risorsa_17', 'risorsa_18', 'risorsa_19', 'risorsa_20',
        ]
        labels = {
            'codice_progetto': 'Codice progetto',
            'nome_progetto': 'Nome progetto',
            'cliente': 'Cliente',
            'tipologia_cliente': 'Tipologia cliente',
            'tipologia_di_progetto': 'Tipologia di progetto',
            'area_di_pertinenza': 'Area di pertinenza',
            'pm': 'PM',
            'provenienza': 'Provenienza',
            'data_primo_contatto': 'Data primo contatto',
            'data_firma_contratto': 'Data firma contratto',
            'data_inizio': 'Data inizio',
            'data_fine_contratto': 'Data fine contratto',
            'descrizione_servizio_offerto': 'Descrizione servizio offerto',
            'url_drive': 'URL Drive',
        }
        widgets = {
            'codice_progetto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: PROG-001'}),
            'nome_progetto': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'pm': forms.TextInput(attrs={'class': 'form-control'}),
            'data_primo_contatto': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_firma_contratto': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_inizio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_fine_contratto': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'descrizione_servizio_offerto': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    DATE_FIELDS = ('data_primo_contatto', 'data_firma_contratto', 'data_inizio', 'data_fine_contratto')
    MONEY_FIELDS = ('fatturato_senza_iva_field', 'iva', 'costi', 'profitti')
    SATISFACTION_FIELDS = ('soddisfazione_team_in_field', 'soddisfazione_cliente_in_field')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for i in range(1, 21):
            name = f'risorsa_{i}'
            if name in self.fields:
                self.fields[name].label = f'Risorsa {i}'
                self.fields[name].widget = forms.TextInput(attrs={'class': 'form-control'})
                self.fields[name].required = False

        instance = kwargs.get('instance')
        is_creation = instance is None or instance._state.adding or not (instance.pk or '').strip()

        if is_creation:
            self.fields.pop('codice_progetto', None)
            if 'nome_progetto' in self.fields:
                self.fields['nome_progetto'].required = True
                self.fields['nome_progetto'].error_messages['required'] = (
                    'Il NOME PROGETTO è obbligatorio per generare il CODICE.'
                )
            if 'data_inizio' in self.fields:
                self.fields['data_inizio'].required = True
                self.fields['data_inizio'].error_messages['required'] = (
                    'La DATA INIZIO è obbligatoria per generare il CODICE.'
                )
        else:
            if 'codice_progetto' in self.fields:
                self.fields['codice_progetto'].required = False
                self.fields['codice_progetto'].widget = forms.TextInput(attrs={
                    'class': 'form-control',
                    'readonly': 'readonly',
                    'style': 'background-color: #f3f4f6; cursor: not-allowed;',
                })

        if instance is not None:
            for name in self.DATE_FIELDS:
                raw = getattr(instance, name, None)
                if raw:
                    self.initial[name] = _parse_date_ddmmyyyy_to_iso(raw)

            for name in self.MONEY_FIELDS:
                raw = getattr(instance, name, None)
                self.initial[name] = _extract_number_from_money(raw)

            for name in self.SATISFACTION_FIELDS:
                raw = getattr(instance, name, None)
                self.initial[name] = _extract_number_from_percentage(raw)

            raw_bool = getattr(instance, 'coinvolgimento_della_pubblica_amministrazione', None)
            if raw_bool is True:
                self.initial['coinvolgimento_della_pubblica_amministrazione'] = 'True'
            elif raw_bool is False:
                self.initial['coinvolgimento_della_pubblica_amministrazione'] = 'False'
            else:
                self.initial['coinvolgimento_della_pubblica_amministrazione'] = ''

            # Normalizza valori legacy verso i choices ufficiali (case-insensitive).
            self.initial['tipologia_cliente'] = ch.normalize_to_choice(
                getattr(instance, 'tipologia_cliente', None), ch.TIPOLOGIA_CLIENTE_VALUES,
            )
            self.initial['tipologia_di_progetto'] = ch.normalize_to_choice(
                getattr(instance, 'tipologia_di_progetto', None), ch.TIPOLOGIA_PROGETTO_VALUES,
            )
            self.initial['stato'] = ch.normalize_to_choice(
                getattr(instance, 'stato', None), ch.STATO_PROGETTO_VALUES,
            )
            self.initial['area_di_pertinenza'] = ch.normalize_to_choice(
                getattr(instance, 'area_di_pertinenza', None), ch.AREA_PERTINENZA_VALUES,
            )
            self.initial['provenienza'] = ch.normalize_to_choice(
                getattr(instance, 'provenienza', None), ch.PROVENIENZA_VALUES,
            )

    def clean_codice_progetto(self):
        # In edizione il campo è readonly: forza sempre il valore originale
        # per impedire manipolazioni client-side della PK.
        if self.instance and self.instance.pk:
            return self.instance.codice_progetto
        return (self.cleaned_data.get('codice_progetto') or '').strip()

    def _clean_date(self, name):
        value = self.cleaned_data.get(name)
        if value in (None, ''):
            return None
        try:
            parsed = datetime.strptime(str(value), '%Y-%m-%d')
        except ValueError:
            raise forms.ValidationError('La data deve essere valida.')
        return parsed.strftime('%d/%m/%Y')

    def clean_data_primo_contatto(self):
        return self._clean_date('data_primo_contatto')

    def clean_data_firma_contratto(self):
        return self._clean_date('data_firma_contratto')

    def clean_data_inizio(self):
        return self._clean_date('data_inizio')

    def clean_data_fine_contratto(self):
        return self._clean_date('data_fine_contratto')

    def _clean_money(self, name):
        raw = self.cleaned_data.get(name)
        dec = _parse_money_to_decimal(raw)
        if dec is None:
            return ''
        return _format_money_eur(dec)

    def clean_fatturato_senza_iva_field(self):
        return self._clean_money('fatturato_senza_iva_field')

    def clean_iva(self):
        return self._clean_money('iva')

    def clean_costi(self):
        return self._clean_money('costi')

    def clean_profitti(self):
        return self._clean_money('profitti')

    def _clean_percentage(self, name):
        value = self.cleaned_data.get(name)
        if value in (None, ''):
            return ''
        return f'{int(value)}%'

    def clean_soddisfazione_team_in_field(self):
        return self._clean_percentage('soddisfazione_team_in_field')

    def clean_soddisfazione_cliente_in_field(self):
        return self._clean_percentage('soddisfazione_cliente_in_field')

    def clean_anno(self):
        anno = self.cleaned_data.get('anno')
        if anno in (None, ''):
            return None
        if anno <= 2010:
            raise forms.ValidationError('Il campo Anno deve essere maggiore di 2010.')
        return anno


# ============================================================
# LEAD (BD pipeline)
# ============================================================
LEAD_ID_MAX_ATTEMPTS = 5


def _generate_lead_id():
    """Formato Apps Script: LEAD-YYYYMMDD-HHMMSS-N (ora locale Europe/Rome)."""
    now = timezone.localtime()
    return f"LEAD-{now:%Y%m%d-%H%M%S}-{randint(1, 99)}"


def _insert_lead_with_new_id(instance):
    """INSERT forzato con PK nuova: mai UPDATE silenzioso su una lead esistente."""
    for _ in range(LEAD_ID_MAX_ATTEMPTS):
        instance.lead_id = _generate_lead_id()
        if Lead.objects.filter(pk=instance.lead_id).exists():
            continue
        try:
            with transaction.atomic():
                instance.save(force_insert=True)
            return
        except IntegrityError:
            continue
    raise IntegrityError('Impossibile generare un Lead ID univoco.')


class LeadForm(forms.ModelForm):
    """
    Form CRUD per Lead BD.
    PK `lead_id` auto-generata in create (formato LEAD-YYYYMMDD-HHMMSS-N)
    e readonly in update.
    """

    # Forecasting: input semplice numero, parse stesso pattern di ProgettoForm
    valore_stimato_input = forms.CharField(
        required=False,
        label='Valore stimato (€)',
        help_text='Solo il numero (es. 880 o 1.234,56)',
        widget=forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'decimal', 'placeholder': 'Es: 880'}),
    )

    fase_attuale = forms.ChoiceField(
        choices=ch.LEAD_FASE_CHOICES, required=False, label='Fase pipeline',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    stato_lead = forms.ChoiceField(
        choices=ch.LEAD_STATO_CHOICES, required=False, label='Stato lead',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    stato_contratto = forms.ChoiceField(
        choices=ch.LEAD_CONTRATTO_CHOICES, required=False, label='Stato contratto',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    priorita = forms.ChoiceField(
        choices=ch.LEAD_PRIORITA_CHOICES, required=False, label='Priorità',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = Lead
        fields = [
            'lead_id',
            'data_primo_contatto',
            'azienda', 'titolare_azienda',
            'referente', 'nome_referente', 'cognome_referente', 'email_referente', 'telefono',
            'prodotto_servizio', 'area', 'owner',
            'fase_attuale', 'stato_lead', 'stato_contratto', 'priorita',
            'probabilita',
            'prossima_azione', 'data_prossima_azione',
            'drive_folder_id', 'link_cartella_drive',
        ]
        labels = {
            'lead_id': 'Lead ID',
            'data_primo_contatto': 'Data primo contatto',
            'azienda': 'Azienda / Startup-PMI',
            'titolare_azienda': 'Titolare azienda',
            'referente': 'Referente (full name)',
            'nome_referente': 'Nome referente',
            'cognome_referente': 'Cognome referente',
            'email_referente': 'Email referente',
            'telefono': 'Telefono',
            'prodotto_servizio': 'Prodotto / Servizio',
            'area': 'Area (es. "M&C, HR")',
            'owner': 'Owner / PM',
            'probabilita': 'Probabilità (0-100)',
            'prossima_azione': 'Prossima azione',
            'data_prossima_azione': 'Data prossima azione',
            'drive_folder_id': 'Drive Folder ID',
            'link_cartella_drive': 'Link cartella Drive',
        }
        widgets = {
            'lead_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'LEAD-YYYYMMDD-HHMMSS-N (auto)'}),
            'data_primo_contatto': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'azienda': forms.TextInput(attrs={'class': 'form-control'}),
            'titolare_azienda': forms.TextInput(attrs={'class': 'form-control'}),
            'referente': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome Cognome'}),
            'nome_referente': forms.TextInput(attrs={'class': 'form-control'}),
            'cognome_referente': forms.TextInput(attrs={'class': 'form-control'}),
            'email_referente': forms.EmailInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'prodotto_servizio': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CSV multi-area: M&C, HR'}),
            'owner': forms.TextInput(attrs={'class': 'form-control'}),
            'probabilita': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100, 'inputmode': 'numeric'}),
            'prossima_azione': forms.TextInput(attrs={'class': 'form-control'}),
            'data_prossima_azione': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'drive_folder_id': forms.TextInput(attrs={'class': 'form-control'}),
            'link_cartella_drive': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = kwargs.get('instance')
        is_creation = instance is None or not (instance.lead_id or '').strip()

        if is_creation:
            # PK auto-generata: nasconde campo
            self.fields.pop('lead_id', None)
        else:
            # Update: PK readonly
            self.fields['lead_id'].disabled = True
            self.fields['lead_id'].help_text = 'Chiave primaria: non modificabile.'

        # Pre-popola valore_stimato_input da Decimal field reale
        if instance is not None and instance.valore_stimato is not None:
            self.initial['valore_stimato_input'] = str(instance.valore_stimato)

        # Normalizza choices legacy case-insensitive
        if instance is not None:
            for f, vals in (
                ('fase_attuale', ch.LEAD_FASE_VALUES),
                ('stato_lead', ch.LEAD_STATO_VALUES),
                ('stato_contratto', ch.LEAD_CONTRATTO_VALUES),
                ('priorita', ch.LEAD_PRIORITA_VALUES),
            ):
                self.initial[f] = ch.normalize_to_choice(getattr(instance, f, None), vals)

    def clean_lead_id(self):
        # In edit: forza valore originale (preserva PK contro tamper client-side)
        if self.instance and self.instance.lead_id:
            return self.instance.lead_id
        return (self.cleaned_data.get('lead_id') or '').strip()

    def clean_azienda(self):
        v = (self.cleaned_data.get('azienda') or '').strip()
        if not v:
            raise forms.ValidationError("L'azienda è obbligatoria.")
        return v

    def clean_probabilita(self):
        v = self.cleaned_data.get('probabilita')
        if v in (None, ''):
            return None
        try:
            n = int(v)
        except (TypeError, ValueError):
            raise forms.ValidationError('La probabilità deve essere un numero intero 0-100.')
        if not (0 <= n <= 100):
            raise forms.ValidationError('La probabilità deve essere tra 0 e 100.')
        return n

    def clean_email_referente(self):
        v = (self.cleaned_data.get('email_referente') or '').strip().lower()
        return v or None

    def clean_valore_stimato_input(self):
        try:
            value = parse_money(self.cleaned_data.get('valore_stimato_input'))
        except ValueError:
            raise forms.ValidationError('Inserisci un numero valido (es: 880 o 1.234,56).')
        if value is not None:
            # numeric(12,2) su Postgres: oltre → errore DB (500)
            DecimalValidator(max_digits=12, decimal_places=2)(value)
        return value

    # Select vuota → default DB (Postgres applica il DEFAULT solo se la colonna è omessa)
    def clean_fase_attuale(self):
        return self.cleaned_data.get('fase_attuale') or 'Nuovo'

    def clean_stato_lead(self):
        return self.cleaned_data.get('stato_lead') or 'Attiva'

    def clean_stato_contratto(self):
        return self.cleaned_data.get('stato_contratto') or None

    def clean_priorita(self):
        return self.cleaned_data.get('priorita') or None

    def save(self, commit=True):
        """
        Override save per:
        - Auto-generare lead_id in create (formato LEAD-YYYYMMDD-HHMMSS-N)
        - Concatenare nome+cognome in `referente` se non fornito
        - Mappare valore_stimato_input → valore_stimato Decimal
        """
        instance = super().save(commit=False)
        creating = not (instance.lead_id or '').strip()

        # Input vuoto → NULL (permette di cancellare il valore)
        instance.valore_stimato = self.cleaned_data.get('valore_stimato_input')

        # Auto-concatena referente se mancante
        if not (instance.referente or '').strip():
            parts = [instance.nome_referente, instance.cognome_referente]
            joined = ' '.join(p for p in parts if p and p.strip())
            if joined:
                instance.referente = joined

        if creating and commit:
            _insert_lead_with_new_id(instance)
        elif creating:
            instance.lead_id = _generate_lead_id()
        elif commit:
            instance.save()
        return instance


class CaseInsensitivePasswordResetForm(PasswordResetForm):
    """
    Cerca gli utenti per email senza distinguere maiuscole/minuscole (PostgreSQL).
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Indirizzo email"
        self.fields["email"].widget.attrs.setdefault("autocomplete", "email")

    def get_users(self, email):
        UserModel = get_user_model()
        email_field = UserModel.get_email_field_name()
        if not email:
            return
        email = email.strip()
        active_users = UserModel._default_manager.filter(
            **{f"{email_field}__iexact": email},
            is_active=True,
        )
        return (
            user for user in active_users if user.has_usable_password()
        )


class TaskForm(forms.ModelForm):
    area = forms.ChoiceField(
        choices=ch.TASK_AREA_CHOICES,
        label='Area',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    stato = forms.ChoiceField(
        choices=ch.TASK_STATO_CHOICES,
        label='Stato',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    priorita = forms.ChoiceField(
        choices=ch.TASK_PRIORITA_CHOICES,
        required=False,
        label='Priorità',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    effort = forms.ChoiceField(
        choices=ch.TASK_EFFORT_CHOICES,
        required=False,
        label='Effort',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    assegnatari = forms.ModelMultipleChoiceField(
        queryset=Soci.objects.none(),
        required=False,
        label='Assegnatari',
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Task
        fields = [
            'titolo', 'area', 'competenza', 'stato', 'priorita', 'effort',
            'scadenza', 'assegnatari', 'altri_assegnatari', 'descrizione', 'link',
        ]
        labels = {
            'titolo': 'Titolo',
            'competenza': 'Competenza',
            'scadenza': 'Scadenza',
            'altri_assegnatari': 'Altri assegnatari (non in SOCI)',
            'descrizione': 'Descrizione',
            'link': 'Link',
        }
        widgets = {
            'titolo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: Aggiornare foglio soci'}),
            'competenza': forms.TextInput(attrs={'class': 'form-control', 'list': 'competenze-suggerite', 'placeholder': 'Es: Data, Automations'}),
            'scadenza': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'altri_assegnatari': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nomi separati da virgola'}),
            'descrizione': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'link': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Un link per riga'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Soci attivi + eventuali assegnatari già presenti (anche se non più associati)
        visibili = Q(status__iexact='Associato')
        if self.instance.pk:
            visibili |= Q(pk__in=self.instance.assegnatari.values('pk'))
        field = self.fields['assegnatari']
        field.queryset = Soci.objects.filter(visibili).order_by('nome_e_cognome')
        field.label_from_instance = (
            lambda s: ' · '.join(p for p in (s.nome_e_cognome or f'Socio #{s.pk}', s.area_di_appartenenza) if p)
        )

    def clean_competenza(self):
        raw = self.cleaned_data.get('competenza') or ''
        seen = []
        for c in raw.split(','):
            c = c.strip()
            if c and c.lower() not in (s.lower() for s in seen):
                seen.append(c)
        return ', '.join(seen)

    def clean_link(self):
        raw = self.cleaned_data.get('link') or ''
        links = [l.strip() for l in raw.splitlines() if l.strip()]
        validate = URLValidator(schemes=['http', 'https'])
        for l in links:
            try:
                validate(l)
            except ValidationError:
                raise forms.ValidationError(f'Link non valido: {l[:80]} (serve http:// o https://, uno per riga).')
        return '\n'.join(links)


class CredenzialeForm(forms.ModelForm):
    area = forms.ChoiceField(
        choices=ch.CREDENZIALI_AREA_CHOICES,
        label='Area',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        required=False,
        strip=False,
        label='Password',
        widget=forms.PasswordInput(render_value=False, attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )
    note = forms.CharField(
        required=False,
        label='Note (cifrate)',
        help_text='Es. codici di recupero, 2FA, istruzioni di accesso.',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'autocomplete': 'off'}),
    )

    class Meta:
        model = Credenziale
        fields = ['area', 'servizio', 'url', 'username']
        labels = {
            'servizio': 'Servizio / account',
            'url': 'Link di accesso',
            'username': 'Utente / email',
        }
        widgets = {
            'servizio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: Canva, LinkedIn, Google Workspace'}),
            'url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['password'].help_text = 'Lascia vuoto per mantenere la password attuale.'
            self.initial['note'] = self.instance.note
        else:
            self.fields['password'].required = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            instance.password = password
        # Ri-cifra le note solo se cambiate (token Fernet diverso a ogni cifratura)
        note = self.cleaned_data.get('note') or ''
        if note != (self.initial.get('note') or ''):
            instance.note = note
        if commit:
            instance.save()
        return instance
