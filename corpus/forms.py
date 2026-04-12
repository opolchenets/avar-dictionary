from django import forms


class SentenceFilterForm(forms.Form):
    STATUS_CHOICES = (
        ("all", "Все"),
        ("untranslated", "Непереведённые"),
        ("pending", "На проверке"),
        ("translated", "Переведённые"),
    )

    q = forms.CharField(label="Поиск", required=False)
    status = forms.ChoiceField(
        label="Статус",
        choices=STATUS_CHOICES,
        required=False,
        initial="all",
    )


class TranslationSubmissionForm(forms.Form):
    text_ru = forms.CharField(
        label="Перевод на русский",
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=5000,
    )
