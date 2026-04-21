from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django import forms
from .models import Partnership, PartnershipNonFin
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
        choices=[('TRUE', 'TRUE'), ('FALSE', 'FALSE')],
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
