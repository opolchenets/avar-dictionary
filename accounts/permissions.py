from django.contrib.auth.mixins import UserPassesTestMixin


def user_is_editor(user) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser:
        return True
    return hasattr(user, "profile") and user.profile.is_editor


class EditorRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return user_is_editor(self.request.user)
