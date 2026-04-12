from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm


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
