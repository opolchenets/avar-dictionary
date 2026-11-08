from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import District
from .models import UserProfile

User = get_user_model()

class SimpleSignUpForm(UserCreationForm):
    district = forms.ModelChoiceField(
        queryset=District.objects.select_related("alliance").all(),
        label="Ваш район",
        required=True,
        empty_label="Выберите район...",
    )

    rights_consent = forms.BooleanField(
        required=True,
        label="Я согласен(на), что мои записи и правки станут частью общего корпуса «Авар МацӀ» и проект сможет свободно использовать их для развития аварского языка — обучать модели, делиться с исследователями и партнёрами, в том числе на коммерческой основе.",
        error_messages={"required": "Чтобы участвовать, отметьте согласие."},
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "district")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.help_text = ""
        # Optionally group by alliance in label
        self.fields["district"].label_from_instance = lambda obj: f"{obj.name} ({obj.alliance.name})"


class ProfileDisplayNameForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ("display_name",)
        labels = {
            "display_name": "Никнейм",
        }
        help_texts = {
            "display_name": "Можно оставить пустым, тогда будет показываться логин.",
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        self.fields["display_name"].required = False
        self.fields["display_name"].widget.attrs.update(
            {
                "placeholder": (
                    self.user.username if self.user is not None else "Ваш никнейм"
                ),
                "maxlength": "150",
            }
        )
