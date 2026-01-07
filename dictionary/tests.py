from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Example,
    Language,
    PartOfSpeech,
    Synonym,
    Translation,
    Word,
)
from .serializers import (
    TranslationSerializer,
    WordSerializer,
    WordShortSerializer,
)


class SynonymFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.lang = Language.objects.create(code="av", name="Avar")
        self.word1 = Word.objects.create(text="a", language=self.lang)
        self.word2 = Word.objects.create(text="b", language=self.lang)
        self.word3 = Word.objects.create(text="c", language=self.lang)
        Synonym.objects.create(word1=self.word1, word2=self.word2)
        Synonym.objects.create(word1=self.word2, word2=self.word3)

    def test_filter_by_word_id(self):
        url = reverse("synonym-list") + f"?word_id={self.word2.id}"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 2)


class SearchWordsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.lang_av = Language.objects.create(code="av", name="Avar")
        self.lang_ru = Language.objects.create(code="ru", name="Russian")
        self.word_av = Word.objects.create(
            text="abar",
            language=self.lang_av,
            transcription="aba",
            alternative_spelling="abar'",
            description="test description",
        )
        self.word_ru = Word.objects.create(
            text="абажур",
            language=self.lang_ru,
        )

    def test_search_words_by_query_matches_multiple_fields(self):
        url = reverse("word-search") + "?q=aba"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.word_av.id)

    def test_search_words_by_language(self):
        url = reverse("word-search") + f"?language={self.lang_ru.code}"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.word_ru.id)

    def test_search_words_with_invalid_language_returns_empty(self):
        url = reverse("word-search") + "?language=xx"
        response = self.client.get(url)
        self.assertEqual(response.data, [])


class QuickTranslateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.lang_av = Language.objects.create(code="av", name="Avar")
        self.lang_ru = Language.objects.create(code="ru", name="Russian")
        self.word_av1 = Word.objects.create(text="alfa", language=self.lang_av)
        self.word_av2 = Word.objects.create(text="arg", language=self.lang_av)
        self.word_ru1 = Word.objects.create(text="альфа", language=self.lang_ru)
        self.word_ru2 = Word.objects.create(text="арг", language=self.lang_ru)
        Translation.objects.create(from_word=self.word_av1, to_word=self.word_ru1)
        Translation.objects.create(from_word=self.word_ru2, to_word=self.word_av2)

    def test_quick_translate_requires_params(self):
        url = reverse("quick-translate")
        response = self.client.get(url, {"word": "a"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data, {"error": "Required: word, from, to"})

    def test_quick_translate_empty_results(self):
        url = reverse("quick-translate")
        response = self.client.get(url, {"word": "zzz", "from": "av", "to": "ru"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_quick_translate_includes_reverse_translations(self):
        url = reverse("quick-translate")
        response = self.client.get(url, {"word": "a", "from": "av", "to": "ru"})
        self.assertEqual(response.status_code, 200)
        pairs = {(item["from_word"]["id"], item["to_word"]["id"]) for item in response.data}
        self.assertIn((self.word_av1.id, self.word_ru1.id), pairs)
        self.assertIn((self.word_av2.id, self.word_ru2.id), pairs)


class QueryParamsFilterMixinViewSetTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.lang_av = Language.objects.create(code="av", name="Avar")
        self.lang_ru = Language.objects.create(code="ru", name="Russian")
        self.pos_noun = PartOfSpeech.objects.create(code="noun", name="Noun")
        self.pos_verb = PartOfSpeech.objects.create(code="verb", name="Verb")
        self.word_av_noun = Word.objects.create(
            text="abar",
            language=self.lang_av,
            part_of_speech=self.pos_noun,
        )
        self.word_av_verb = Word.objects.create(
            text="abaz",
            language=self.lang_av,
            part_of_speech=self.pos_verb,
        )
        self.word_ru = Word.objects.create(text="дом", language=self.lang_ru)
        self.translation = Translation.objects.create(
            from_word=self.word_av_noun,
            to_word=self.word_ru,
        )
        self.example = Example.objects.create(
            text="пример",
            translation="example",
            word=self.word_av_noun,
        )

    def test_word_viewset_filters_by_language(self):
        url = reverse("word-list") + f"?language={self.lang_ru.code}"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.word_ru.id)

    def test_word_viewset_filters_by_part_of_speech(self):
        url = reverse("word-list") + f"?part_of_speech={self.pos_verb.id}"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.word_av_verb.id)

    def test_translation_viewset_filters_by_from_word(self):
        url = reverse("translation-list") + f"?from_word_id={self.word_av_noun.id}"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.translation.id)

    def test_example_viewset_filters_by_word(self):
        url = reverse("example-list") + f"?word_id={self.word_av_noun.id}"
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.example.id)


class SerializerTests(TestCase):
    def setUp(self):
        self.lang_av = Language.objects.create(code="av", name="Avar")
        self.lang_ru = Language.objects.create(code="ru", name="Russian")
        self.word_av = Word.objects.create(text="abar", language=self.lang_av)
        self.word_ru = Word.objects.create(text="дом", language=self.lang_ru)
        self.translation = Translation.objects.create(
            from_word=self.word_av,
            to_word=self.word_ru,
            quality=4,
            notes="note",
        )
        self.word_alt = Word.objects.create(text="abar2", language=self.lang_av)
        Synonym.objects.create(word1=self.word_av, word2=self.word_alt)
        Synonym.objects.create(word1=self.word_alt, word2=self.word_av)

    def test_word_short_serializer_includes_language(self):
        data = WordShortSerializer(self.word_av).data
        self.assertEqual(data["language"], {"id": self.lang_av.id, "code": "av", "name": "Avar"})

    def test_translation_serializer_includes_nested_words(self):
        data = TranslationSerializer(self.translation).data
        self.assertEqual(data["quality"], 4)
        self.assertEqual(data["notes"], "note")
        self.assertEqual(data["from_word"]["id"], self.word_av.id)
        self.assertEqual(data["to_word"]["id"], self.word_ru.id)

    def test_word_serializer_deduplicates_synonyms(self):
        data = WordSerializer(self.word_av).data
        synonym_ids = {item["id"] for item in data["synonyms"]}
        self.assertEqual(synonym_ids, {self.word_alt.id})
