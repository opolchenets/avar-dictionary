from django import forms
from django.utils.html import strip_tags
from .models import Category


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
    category = forms.ModelChoiceField(
        label="Раздел",
        queryset=Category.objects.all(),
        required=False,
        empty_label="Все разделы",
        to_field_name="slug",
    )


class TranslationSubmissionForm(forms.Form):
    text_av = forms.CharField(
        label="Перевод на аварский",
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=5000,
    )

    def clean_text_av(self):
        data = self.cleaned_data["text_av"]
        return strip_tags(data)
