from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import make_password


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authenticate with username or full email (case-insensitive for both).
    Costanza temporale anti-user-enumeration: password check viene eseguita anche se
    l'utente non esiste (dummy hash) per non rivelare l'esistenza dell'account.
    """

    _DUMMY_HASH = make_password('dummy-not-a-real-password')

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        # Sanitizzazione: trim + lowercase (email e username sono case-insensitive)
        login_id = (username or '').strip().lower()
        if not login_id:
            return None

        UserModel = get_user_model()
        if "@" in login_id:
            user = UserModel.objects.filter(email__iexact=login_id).first()
        else:
            user = UserModel.objects.filter(username__iexact=login_id).first()

        if user is None:
            # Dummy check per equalizzare i tempi di risposta
            from django.contrib.auth.hashers import check_password
            check_password(password, self._DUMMY_HASH)
            return None

        if not user.check_password(password):
            return None
        # is_active + permessi: blocca utenti disattivati
        if not self.user_can_authenticate(user):
            return None
        return user
