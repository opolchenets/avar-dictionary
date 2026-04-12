from django import forms

from corpus.models import Sentence


class SentenceImportForm(forms.Form):
    sentences = forms.CharField(
        label="Список аварских предложений",
        widget=forms.Textarea(attrs={"rows": 12}),
        help_text="Одна строка = одно предложение. Вставка текста.",
        required=False
    )
    csv_file = forms.FileField(
        label="Или загрузите CSV-файл",
        help_text="Файл может содержать 1 колонку (только аварский текст) или 2 колонки (аварский текст, русский перевод). Без заголовков.",
        required=False
    )

    def clean(self):
        cleaned_data = super().clean()
        sentences = cleaned_data.get("sentences")
        csv_file = cleaned_data.get("csv_file")
        if not sentences and not csv_file:
            raise forms.ValidationError("Заполните текстовое поле или прикрепите CSV-файл.")
        return cleaned_data


class SentenceEditForm(forms.ModelForm):
    class Meta:
        model = Sentence
        fields = ("source_text_av", "text_ru")
        widgets = {
            "source_text_av": forms.Textarea(attrs={"rows": 4}),
            "text_ru": forms.Textarea(attrs={"rows": 4})
        }
