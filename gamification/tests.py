from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion


User = get_user_model()


class LeaderboardTests(TestCase):
    def test_leaderboard_orders_by_total_points(self):
        first = User.objects.create_user(username="first", password="Strong-pass123")
        second = User.objects.create_user(username="second", password="Strong-pass123")
        first_sentence = Sentence.objects.create(source_text_av="Первое", status=Sentence.Status.TRANSLATED, text_ru="one", translated_by=first)
        second_sentence = Sentence.objects.create(source_text_av="Второе", status=Sentence.Status.TRANSLATED, text_ru="two", translated_by=second)
        third_sentence = Sentence.objects.create(source_text_av="Третье", status=Sentence.Status.TRANSLATED, text_ru="three", translated_by=second)
        TranslationSuggestion.objects.create(
            sentence=first_sentence,
            proposed_text_ru="one",
            author=first,
            status=TranslationSuggestion.Status.ACCEPTED,
        )
        TranslationSuggestion.objects.create(
            sentence=second_sentence,
            proposed_text_ru="two",
            author=second,
            status=TranslationSuggestion.Status.ACCEPTED,
        )
        TranslationSuggestion.objects.create(
            sentence=third_sentence,
            proposed_text_ru="three",
            author=second,
            status=TranslationSuggestion.Status.ACCEPTED,
        )

        response = self.client.get(reverse("leaderboard"))

        leaders = list(response.context["leaders"])
        self.assertEqual(leaders[0]["username"], "second")
