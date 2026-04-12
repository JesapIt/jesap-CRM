from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Authenticate with username or full email (case-insensitive for both).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None

        login_id = username.strip()
        if not login_id:
            return None

        UserModel = get_user_model()
        if "@" in login_id:
            user = UserModel.objects.filter(email__iexact=login_id).first()
        else:
            user = UserModel.objects.filter(username__iexact=login_id).first()

        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
