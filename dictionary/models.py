from django.db import models

class Language(models.Model):
    code = models.CharField('Код языка', max_length=5, unique=True, help_text='Например, для аварского код равен av')
    name = models.CharField('Название языка', max_length=64)

    class Meta:
        verbose_name = 'Язык'
        verbose_name_plural = 'Языки'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"

class PartOfSpeech(models.Model):
    code = models.CharField(max_length=8, unique=True) # noun, verb, etc.
    name = models.CharField(max_length=32)

    def __str__(self):
        return self.name

class Word(models.Model):
    text = models.CharField('Слово', max_length=128)
    language = models.ForeignKey(Language, on_delete=models.CASCADE, related_name='words', verbose_name='Язык')
    part_of_speech = models.ForeignKey(PartOfSpeech, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Часть речи')
    transcription = models.CharField('Транскрипция', max_length=128, blank=True)
    alternative_spelling = models.CharField('Альтернативное написание', max_length=128, blank=True)
    lemma = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='word_forms', verbose_name='Лемма')
    description = models.TextField('Описание/Примечание', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    updated_at = models.DateTimeField('Обновлено', auto_now=True)

    class Meta:
        verbose_name = 'Слово'
        verbose_name_plural = 'Слова'
        unique_together = ('text', 'language', 'part_of_speech')
        ordering = ['language', 'text']
        indexes = [
            models.Index(fields=['language', 'text']),
            models.Index(fields=['part_of_speech']),
        ]

    def __str__(self):
        return f"{self.text} ({self.language.code})"

class Translation(models.Model):
    from_word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='translations_from', verbose_name='Исходное слово')
    to_word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='translations_to', verbose_name='Перевод')
    quality = models.PositiveSmallIntegerField('Качество', null=True, blank=True)
    notes = models.TextField('Примечания', blank=True)

    class Meta:
        verbose_name = 'Перевод'
        verbose_name_plural = 'Переводы'
        unique_together = ('from_word', 'to_word')
        ordering = ['from_word', 'to_word']
        indexes = [
            models.Index(fields=['from_word']),
            models.Index(fields=['to_word']),
        ]

    def __str__(self):
        return f"{self.from_word} → {self.to_word}"

class Example(models.Model):
    text = models.TextField('Пример')
    translation = models.TextField('Перевод примера', blank=True)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='examples', verbose_name='Слово')
    source = models.CharField('Источник', max_length=128, blank=True)

    class Meta:
        verbose_name = 'Пример'
        verbose_name_plural = 'Примеры'
        ordering = ['word', 'id']
        indexes = [
            models.Index(fields=['word']),
        ]

    def __str__(self):
        return f"{self.text[:40]}..."

class Synonym(models.Model):
    word1 = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='synonyms1', verbose_name='Слово 1')
    word2 = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='synonyms2', verbose_name='Слово 2 (синоним)')

    class Meta:
        verbose_name = 'Синоним'
        verbose_name_plural = 'Синонимы'
        unique_together = (('word1', 'word2'),)
        ordering = ['word1', 'word2']
        indexes = [
            models.Index(fields=['word1']),
            models.Index(fields=['word2']),
        ]

    def __str__(self):
        return f"{self.word1} ~ {self.word2}"
