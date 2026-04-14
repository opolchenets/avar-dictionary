from django import forms
from corpus.models import Category, Sentence, Terminology


class SentenceImportForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        label="Раздел для всех импортируемых предложений",
        required=False,
        empty_label="Без раздела"
    )
    sentences = forms.CharField(
        label="Список русских предложений",
        widget=forms.Textarea(attrs={"rows": 12}),
        help_text="Одна строка = одно предложение. Вставка текста.",
        required=False
    )
    csv_file = forms.FileField(
        label="Или загрузите CSV-файл",
        help_text="Без заголовков.",
        required=False
    )
    csv_format = forms.ChoiceField(
        label="Формат CSV файла",
        choices=(
            ("1col", "1 колонка (только русские предложения, запятые не делят строку)"),
            ("2col", "2 колонки (русский, перевод) через запятую")
        ),
        initial="1col",
        widget=forms.RadioSelect
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
        fields = ("source_text_ru", "text_av", "category")
        widgets = {
            "source_text_ru": forms.Textarea(attrs={"rows": 4}),
            "text_av": forms.Textarea(attrs={"rows": 4})
        }


class TerminologyForm(forms.ModelForm):
    class Meta:
        model = Terminology
        fields = ("category", "word_ru", "word_av")


class TerminologyImportForm(forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        label="Раздел",
        required=True,
        empty_label="Выберите раздел..."
    )
    csv_file = forms.FileField(
        label="Загрузите CSV-файл",
        help_text="Формат: RU слово, AV перевод. Без заголовков. По одному на строку.",
        required=True
    )
