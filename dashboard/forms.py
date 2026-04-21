import re
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django import forms
from .models import Partnership, PartnershipNonFin, Progetti
from datetime import datetime


MONTH_CHOICES = [
    ('', 'Mese'),
    ('01', '01 - Janeiro'),
    ('02', '02 - Fevereiro'),
    ('03', '03 - Março'),
    ('04', '04 - Abril'),
    ('05', '05 - Maio'),
    ('06', '06 - Junho'),
    ('07', '07 - Julho'),
    ('08', '08 - Agosto'),
    ('09', '09 - Setembro'),
    ('10', '10 - Outubro'),
    ('11', '11 - Novembro'),
    ('12', '12 - Dezembro'),
]

YEAR_CHOICES = [('', 'Anno')] + [(str(year), str(year)) for year in range(2000, datetime.now().year + 6)]


class MonthYearWidget(forms.MultiWidget):
    def __init__(self, attrs=None):
        widgets = [
            forms.Select(attrs={'class': 'form-control', 'style': 'max-width: 120px;'}, choices=MONTH_CHOICES),
            forms.Select(attrs={'class': 'form-control', 'style': 'max-width: 120px;'}, choices=YEAR_CHOICES),
        ]
        super().__init__(widgets, attrs)

    def decompress(self, value):
        if value:
            value = str(value).strip()
            if '/' in value:
                month, year = value.split('/', 1)
                return [month.zfill(2), year]
        return [None, None]


class MonthYearField(forms.MultiValueField):
    widget = MonthYearWidget

    def __init__(self, *args, **kwargs):
        fields = (
            forms.ChoiceField(choices=MONTH_CHOICES, required=False),
            forms.ChoiceField(choices=YEAR_CHOICES, required=False),
        )
        kwargs.setdefault('require_all_fields', False)
        super().__init__(fields=fields, *args, **kwargs)

    def compress(self, data_list):
        if not data_list:
            return ''

        month = (data_list[0] or '').strip()
        year = (data_list[1] or '').strip()

        if not month and not year:
            return ''

        if month and year:
            return f'{month}/{year}'

        raise forms.ValidationError('Il Periodo deve includere mese e anno.')

class PartnershipForm(forms.ModelForm):
    status_partnership = forms.ChoiceField(
        choices=[('Attiva', 'Attiva'), ('Conclusa', 'Conclusa')],
        required=False,
        label='Status',
        widget=forms.Select(attrs={'class': 'form-control', 'style': 'max-width: 220px;'})
    )
    compenso_economico = forms.ChoiceField(
        choices=[('TRUE', 'Sì'), ('FALSE', 'No')],
        required=False,
        label='Compenso economico',
        widget=forms.Select(attrs={'class': 'form-control', 'style': 'max-width: 220px;'})
    )

    class Meta:
        model = Partnership
        # '__all__' pega todos os campos do models.py, incluindo o campo 'id'
        fields = '__all__' 
        
        # Vamos customizar os rótulos (labels) para ficar mais amigável na tela
        labels = {
            'id': 'ID della Partnership (Codice Manuale)',
            'partnership': 'Nome Azienda / Partnership',
            'status_partnership': 'Status',
            'compenso_economico': 'Compenso economico',
        }

        # Vamos adicionar widgets para facilitar a digitação de datas e estilizar
        widgets = {
            'id': forms.TextInput(attrs={'placeholder': 'Es: 001 ou PART-001', 'class': 'form-control'}),
            'data_firma': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_fine_prevista': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_ultimo_rinnovo': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'anno': forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'pattern': '[0-9]*'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if name == 'id':
                continue

            widget = field.widget
            existing_class = widget.attrs.get('class', '').strip()
            if 'form-control' not in existing_class.split():
                widget.attrs['class'] = f"{existing_class} form-control".strip()

            if isinstance(widget, forms.Textarea):
                field.widget = forms.TextInput(
                    attrs={
                        'class': widget.attrs.get('class', 'form-control'),
                        'style': 'max-width: 360px; width: 100%;'
                    }
                )
                continue

            if isinstance(widget, forms.TextInput):
                widget.attrs['style'] = 'max-width: 360px; width: 100%;'

    def clean_anno(self):
        anno = self.cleaned_data.get('anno')
        if anno in (None, ''):
            return anno

        try:
            anno_int = int(float(anno))
        except (TypeError, ValueError):
            raise forms.ValidationError("Il campo Anno deve contenere un numero intero.")

        if anno_int != float(anno):
            raise forms.ValidationError("Il campo Anno deve contenere un numero intero.")

        if anno_int <= 2010:
            raise forms.ValidationError("Il campo Anno deve essere maggiore di 2010.")

        return anno_int

    def clean_numero_progetti(self):
        numero = self.cleaned_data.get('numero_progetti')
        if numero and numero.strip():
            try:
                int(numero)
            except ValueError:
                raise forms.ValidationError("Il numero di progetti deve essere un numero intero valido.")
        return numero

    def clean_numero_partecipanti(self):
        numero = self.cleaned_data.get('numero_partecipanti')
        if numero and numero.strip():
            try:
                int(numero)
            except ValueError:
                raise forms.ValidationError("Il numero di partecipanti deve essere un numero intero valido.")
        return numero

    def clean_data_firma(self):
        data = self.cleaned_data.get('data_firma')
        if data and data.strip():
            try:
                datetime.strptime(data, '%Y-%m-%d')
            except ValueError:
                raise forms.ValidationError("La data di firma deve essere nel formato YYYY-MM-DD.")
        return data

    def clean_data_ultimo_rinnovo(self):
        data = self.cleaned_data.get('data_ultimo_rinnovo')
        if data and data.strip():
            try:
                datetime.strptime(data, '%Y-%m-%d')
            except ValueError:
                raise forms.ValidationError("La data ultimo rinnovo deve essere nel formato YYYY-MM-DD.")
        return data

    def clean_data_fine_prevista(self):
        data = self.cleaned_data.get('data_fine_prevista')
        if data and data.strip():
            try:
                datetime.strptime(data, '%Y-%m-%d')
            except ValueError:
                raise forms.ValidationError("La data fine prevista deve essere nel formato YYYY-MM-DD.")
        return data


class PartnershipNonFinForm(forms.ModelForm):
    periodo = MonthYearField(label='Periodo', required=False)
    anno = forms.IntegerField(
        required=False,
        label='Anno',
        widget=forms.TextInput(attrs={'class': 'form-control', 'inputmode': 'numeric', 'pattern': '[0-9]*'}),
    )

    class Meta:
        model = PartnershipNonFin
        fields = '__all__'
        labels = {
            'realta': 'Realtà',
            'contatti': 'Contatti',
            'periodo': 'Periodo',
            'anno': 'Anno',
            'cartella': 'Cartella',
        }
        widgets = {
            'realta': forms.TextInput(attrs={'class': 'form-control'}),
            'contatti': forms.TextInput(attrs={'class': 'form-control'}),
            'cartella': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for name, field in self.fields.items():
            if name in {'realta', 'contatti', 'cartella', 'anno'} and hasattr(field.widget, 'attrs'):
                existing_class = field.widget.attrs.get('class', '').strip()
                if 'form-control' not in existing_class.split():
                    field.widget.attrs['class'] = f"{existing_class} form-control".strip()

            if name in {'realta', 'contatti', 'cartella'} and isinstance(field.widget, forms.TextInput):
                field.widget.attrs['style'] = 'max-width: 360px; width: 100%;'

        self.fields['periodo'].widget = MonthYearWidget()

    def clean_anno(self):
        anno = self.cleaned_data.get('anno')
        if anno in (None, ''):
            return None

        try:
            return int(anno)
        except (TypeError, ValueError):
            raise forms.ValidationError('Il campo Anno deve contenere un numero intero valido.')

    def clean_periodo(self):
        periodo = self.cleaned_data.get('periodo')
        if periodo in (None, ''):
            return ''

        periodo = str(periodo).strip()
        if '/' not in periodo:
            raise forms.ValidationError('Il Periodo deve essere nel formato mm/aaaa.')

        month, year = periodo.split('/', 1)
        if len(month) != 2 or not month.isdigit() or not 1 <= int(month) <= 12:
            raise forms.ValidationError('Il Periodo deve essere nel formato mm/aaaa.')
        if len(year) != 4 or not year.isdigit():
            raise forms.ValidationError('Il Periodo deve essere nel formato mm/aaaa.')

        return f'{month}/{year}'


STATO_PROGETTO_CHOICES = [
    ('', '---------'),
    ('Stand-by', 'Stand-by'),
    ('Annullato', 'Annullato'),
    ('In Corso', 'In Corso'),
    ('Concluso', 'Concluso'),
]


def _parse_date_ddmmyyyy_to_iso(value):
    if not value:
        return ''
    value = str(value).strip()
    if not value:
        return ''
    try:
        return datetime.strptime(value, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError:
        return ''


def _format_iso_to_ddmmyyyy(value):
    if value in (None, ''):
        return None
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d').strftime('%d/%m/%Y')
    except ValueError:
        raise forms.ValidationError('La data deve essere valida.')


def _parse_money_to_decimal(raw):
    if raw in (None, ''):
        return None
    text = str(raw).strip()
    if not text:
        return None
    text = re.sub(r'[^\d,.\-]', '', text)
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return Decimal(text)
    except InvalidOperation:
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
    stato = forms.ChoiceField(
        choices=STATO_PROGETTO_CHOICES,
        required=False,
        label='Stato',
        widget=forms.Select(attrs={'class': 'form-control', 'style': 'max-width: 220px;'}),
    )
    coinvolgimento_della_pubblica_amministrazione = forms.TypedChoiceField(
        choices=[('', '---------'), ('True', 'Sì'), ('False', 'No')],
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
        }
        widgets = {
            'codice_progetto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es: PROG-001'}),
            'nome_progetto': forms.TextInput(attrs={'class': 'form-control'}),
            'cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'tipologia_cliente': forms.TextInput(attrs={'class': 'form-control'}),
            'tipologia_di_progetto': forms.TextInput(attrs={'class': 'form-control'}),
            'area_di_pertinenza': forms.TextInput(attrs={'class': 'form-control'}),
            'pm': forms.TextInput(attrs={'class': 'form-control'}),
            'provenienza': forms.TextInput(attrs={'class': 'form-control'}),
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

    def clean_codice_progetto(self):
        value = (self.cleaned_data.get('codice_progetto') or '').strip()
        if not value:
            raise forms.ValidationError('Il codice progetto è obbligatorio.')
        return value

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
