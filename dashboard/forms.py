from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django import forms
from .models import Partnership
from datetime import datetime

class PartnershipForm(forms.ModelForm):
    class Meta:
        model = Partnership
        # '__all__' pega todos os campos do models.py, incluindo o campo 'id'
        fields = '__all__' 
        
        # Vamos customizar os rótulos (labels) para ficar mais amigável na tela
        labels = {
            'id': 'ID della Partnership (Codice Manuale)',
            'partnership': 'Nome Azienda / Partnership',
            'status_partnership': 'Status',
        }

        # Vamos adicionar widgets para facilitar a digitação de datas e estilizar
        widgets = {
            'id': forms.TextInput(attrs={'placeholder': 'Es: 001 ou PART-001', 'class': 'form-control'}),
            'data_firma': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_fine_prevista': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'data_ultimo_rinnovo': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'anno': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def clean_anno(self):
        anno = self.cleaned_data.get('anno')
        if anno is not None and anno < 1900:
            raise forms.ValidationError("Il anno deve essere maggiore o uguale a 1900.")
        return anno

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
