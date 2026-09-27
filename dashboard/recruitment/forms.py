from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from dashboard import choices as ch
from dashboard.models import (
    Candidato, ColloquioIndividuale, GruppoColloquio, RecruitmentSessione, Soci,
)

from . import emails

CELL = {'class': 'cell-input'}


def soci_choices():
    """Choices soci attivi calcolate UNA volta per request (condivise tra le righe dei formset)."""
    soci = Soci.objects.filter(status__iexact='Associato').order_by('nome_e_cognome')
    return [('', '—')] + [(s.pk, s.nome_e_cognome or f'Socio #{s.pk}') for s in soci]


def _condividi_soci(form, nomi_campi, choices):
    for nome in nomi_campi:
        field = form.fields[nome]
        field.queryset = Soci.objects.all()  # validazione: accetta anche ex soci già assegnati
        current = getattr(form.instance, f'{nome}_id', None)
        extra = []
        if current and current not in {c[0] for c in choices}:
            socio = Soci.objects.filter(pk=current).first()
            extra = [(current, f'{socio.nome_e_cognome} (non attivo)' if socio else f'Socio #{current}')]
        field.choices = choices + extra


# ============================================================
# Sessione
# ============================================================

class SessioneForm(forms.ModelForm):
    class Meta:
        model = RecruitmentSessione
        fields = ['nome', 'aperta', 'conferma_automatica', 'link_welcome_day']
        labels = {
            'nome': 'Nome sessione',
            'aperta': 'Sessione aperta (riceve le candidature dal form)',
            'conferma_automatica': 'Invia automaticamente la conferma di ricezione',
            'link_welcome_day': 'Link Welcome Day',
        }
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Es. Spring REC 26'}),
            'link_welcome_day': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
        }


class TemplateEmailForm(forms.Form):
    """Oggetto + corpo per ogni tipo di email. Campo uguale al default → non salvato."""

    def __init__(self, *args, sessione, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessione = sessione
        for tipo, (etichetta, _) in emails.TIPI.items():
            oggetto, corpo = emails.template(sessione, tipo)
            self.fields[f'oggetto__{tipo}'] = forms.CharField(
                label=f'{etichetta} — oggetto', initial=oggetto, max_length=255,
                widget=forms.TextInput(attrs={'class': 'form-control'}),
            )
            self.fields[f'corpo__{tipo}'] = forms.CharField(
                label=f'{etichetta} — testo', initial=corpo,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 7}),
            )

    def gruppi(self):
        """[(tipo, etichetta, segnaposto, campo_oggetto, campo_corpo, personalizzato)] per il template."""
        out = []
        for tipo, (etichetta, extra) in emails.TIPI.items():
            segnaposto = ['nome', 'cognome', 'sessione'] + extra
            out.append((tipo, etichetta, segnaposto, self[f'oggetto__{tipo}'], self[f'corpo__{tipo}'],
                        emails.is_personalizzato(self.sessione, tipo)))
        return out

    def save(self):
        custom = {}
        for tipo in emails.TIPI:
            oggetto = self.cleaned_data[f'oggetto__{tipo}'].strip()
            corpo = self.cleaned_data[f'corpo__{tipo}'].replace('\r\n', '\n').strip()
            default_oggetto, default_corpo = emails.DEFAULT_TEMPLATES[tipo]
            entry = {}
            if oggetto != default_oggetto:
                entry['oggetto'] = oggetto
            if corpo != default_corpo.strip():
                entry['corpo'] = corpo
            if entry:
                custom[tipo] = entry
        self.sessione.template_email = custom
        self.sessione.save(update_fields=['template_email'])


# ============================================================
# Gruppi di colloquio
# ============================================================

class GruppoForm(forms.ModelForm):
    class Meta:
        model = GruppoColloquio
        fields = ['numero', 'data', 'ora', 'luogo', 'recruiter_1', 'recruiter_2', 'recruiter_3', 'note']
        labels = {'luogo': 'Aula / link Meet', 'recruiter_1': 'Recruiter 1', 'recruiter_2': 'Recruiter 2', 'recruiter_3': 'Recruiter 3'}
        widgets = {
            'numero': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'ora': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}, format='%H:%M'),
            'luogo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'meet.google.com/... o aula'}),
            'recruiter_1': forms.Select(attrs={'class': 'form-control'}),
            'recruiter_2': forms.Select(attrs={'class': 'form-control'}),
            'recruiter_3': forms.Select(attrs={'class': 'form-control'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, sessione, **kwargs):
        super().__init__(*args, **kwargs)
        self.sessione = sessione
        _condividi_soci(self, ['recruiter_1', 'recruiter_2', 'recruiter_3'], soci_choices())

    def clean_numero(self):
        numero = self.cleaned_data['numero']
        dup = GruppoColloquio.objects.filter(sessione=self.sessione, numero=numero).exclude(pk=self.instance.pk)
        if dup.exists():
            raise forms.ValidationError(f'Esiste già il gruppo {numero} in questa sessione.')
        return numero


# ============================================================
# Righe dei formset (una per candidato / colloquio)
# ============================================================

class ScreeningRowForm(forms.ModelForm):
    class Meta:
        model = Candidato
        fields = ['esito_screening', 'note']
        widgets = {
            'esito_screening': forms.Select(choices=ch.REC_ESITO_SCREENING_CHOICES, attrs=CELL),
            'note': forms.TextInput(attrs={**CELL, 'placeholder': 'Note'}),
        }


class GruppoRowForm(forms.ModelForm):
    class Meta:
        model = Candidato
        fields = ['gruppo', 'presenza_gruppo', 'punteggio_output', 'link_output',
                  'punteggio_soft_gruppo', 'link_scheda_gruppo', 'esito_gruppo']
        widgets = {
            'gruppo': forms.Select(attrs=CELL),
            'presenza_gruppo': forms.NullBooleanSelect(attrs=CELL),
            'punteggio_output': forms.NumberInput(attrs={**CELL, 'step': '0.01', 'min': 0, 'max': 10}),
            'link_output': forms.TextInput(attrs={**CELL, 'placeholder': 'Link elaborato'}),
            'punteggio_soft_gruppo': forms.NumberInput(attrs={**CELL, 'step': '0.01', 'min': 0, 'max': 10}),
            'link_scheda_gruppo': forms.TextInput(attrs={**CELL, 'placeholder': 'Link scheda'}),
            'esito_gruppo': forms.Select(choices=ch.REC_ESITO_GRUPPO_CHOICES, attrs=CELL),
        }

    def __init__(self, *args, sessione, gruppi_choices, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gruppo'].queryset = GruppoColloquio.objects.filter(sessione=sessione)
        self.fields['gruppo'].choices = gruppi_choices


class ColloquioRowForm(forms.ModelForm):
    class Meta:
        model = ColloquioIndividuale
        fields = ['area', 'data', 'ora', 'link_meet', 'recruiter_hr', 'recruiter_tecnico', 'con_resp_vice',
                  'presenza_confermata', 'presenza', 'durata_minuti', 'punteggio_soft', 'punteggio_hard',
                  'link_scheda', 'esito', 'area_probabile']
        widgets = {
            'area': forms.Select(choices=ch.REC_AREA_CHOICES, attrs=CELL),
            'data': forms.DateInput(attrs={**CELL, 'type': 'date'}, format='%Y-%m-%d'),
            'ora': forms.TimeInput(attrs={**CELL, 'type': 'time'}, format='%H:%M'),
            'link_meet': forms.TextInput(attrs={**CELL, 'placeholder': 'meet.google.com/...'}),
            'recruiter_hr': forms.Select(attrs=CELL),
            'recruiter_tecnico': forms.Select(attrs=CELL),
            'presenza': forms.NullBooleanSelect(attrs=CELL),
            'durata_minuti': forms.NumberInput(attrs={**CELL, 'min': 0, 'placeholder': 'min'}),
            'punteggio_soft': forms.NumberInput(attrs={**CELL, 'step': '0.01', 'min': 0, 'max': 10}),
            'punteggio_hard': forms.NumberInput(attrs={**CELL, 'step': '0.01', 'min': 0, 'max': 10}),
            'link_scheda': forms.TextInput(attrs={**CELL, 'placeholder': 'Link scheda'}),
            'esito': forms.Select(choices=ch.REC_ESITO_INDIVIDUALE_CHOICES, attrs=CELL),
            'area_probabile': forms.Select(choices=ch.REC_AREA_CHOICES, attrs=CELL),
        }

    def __init__(self, *args, soci=None, **kwargs):
        super().__init__(*args, **kwargs)
        _condividi_soci(self, ['recruiter_hr', 'recruiter_tecnico'], soci or [('', '—')])
        if self.instance.tipo == ch.REC_TIPO_SECONDA:
            # "Seconda scelta" ha senso solo sul primo colloquio
            self.fields['esito'].widget.choices = [c for c in ch.REC_ESITO_INDIVIDUALE_CHOICES if c[0] != 'Seconda scelta']


class ProvaRowForm(forms.ModelForm):
    class Meta:
        model = Candidato
        fields = ['area_prova', 'conferma_area', 'mail_jesap_creata', 'form_compilato', 'gruppo_telegram',
                  'esito_finale', 'settimane_prolungamento']
        widgets = {
            'area_prova': forms.Select(choices=ch.REC_AREA_CHOICES, attrs=CELL),
            'esito_finale': forms.Select(choices=ch.REC_ESITO_FINALE_CHOICES, attrs=CELL),
            'settimane_prolungamento': forms.NumberInput(attrs={**CELL, 'min': 1, 'max': 12}),
        }

    def clean(self):
        data = super().clean()
        if data.get('esito_finale') == 'Prolungato' and not data.get('settimane_prolungamento'):
            self.add_error('settimane_prolungamento', 'Indica di quante settimane.')
        return data


# ============================================================
# Scheda candidato
# ============================================================

class CandidatoForm(forms.ModelForm):
    class Meta:
        model = Candidato
        fields = ['nome', 'cognome', 'email', 'telefono', 'data_nascita', 'residenza', 'ateneo', 'facolta',
                  'corso_laurea', 'anno_frequenza', 'area_1', 'area_2', 'cv_url', 'fonte', 'conosce_jesap',
                  'conosce_je_italy', 'motivazione', 'note']
        labels = {
            'data_nascita': 'Data di nascita', 'facolta': 'Facoltà', 'corso_laurea': 'Corso di laurea',
            'anno_frequenza': 'Anno di frequenza', 'area_1': 'Area 1', 'area_2': 'Area 2', 'cv_url': 'Link CV',
            'fonte': 'Come ha conosciuto JESAP', 'conosce_jesap': 'Conosce associati JESAP?',
            'conosce_je_italy': 'Conosce associati JE Italy?',
        }
        widgets = {
            'area_1': forms.Select(choices=ch.REC_AREA_CHOICES, attrs={'class': 'form-control'}),
            'area_2': forms.Select(choices=ch.REC_AREA_CHOICES, attrs={'class': 'form-control'}),
            'motivazione': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs.setdefault('class', 'form-control')


# ============================================================
# Accessi
# ============================================================

class AccessoForm(forms.Form):
    utente = forms.ModelChoiceField(
        queryset=get_user_model().objects.none(), label='Socio da autorizzare',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, candidati_utenti, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields['utente']
        field.queryset = get_user_model().objects.filter(pk__in=[u.pk for u, _ in candidati_utenti])
        field.choices = [('', '—')] + [
            (u.pk, f'{s.nome_e_cognome} · {s.area_di_appartenenza or "-"} ({u.email})') for u, s in candidati_utenti
        ]


def utenti_con_socio(q_soci=Q()):
    """[(user, socio)] per gli utenti registrati collegati a un socio attivo."""
    soci = {(s.email_jesap or '').lower(): s for s in Soci.objects.filter(q_soci, status__iexact='Associato') if s.email_jesap}
    out = []
    for u in get_user_model().objects.filter(is_active=True).order_by('email'):
        s = soci.get((u.email or '').strip().lower())
        if s:
            out.append((u, s))
    return sorted(out, key=lambda us: (us[1].nome_e_cognome or '').lower())
