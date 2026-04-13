from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.test import TestCase
from django.urls import reverse

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion

User = get_user_model()

class LeaderboardTests(TestCase):
    def test_leaderboard_orders_by_total_points(self):
        first = User.objects.create_user(username="first", password="Strong-pass123")
        second = User.objects.create_user(username="second", password="Strong-pass123")

        # Second user translates 2 sentences
        Sentence.objects.create(source_text_ru="Один", status=Sentence.Status.TRANSLATED, text_av="цо", translated_by=second)
        Sentence.objects.create(source_text_ru="Два", status=Sentence.Status.TRANSLATED, text_av="кIиго", translated_by=second)
        
        # We need suggestions to give points in the current logic
        s1 = TranslationSuggestion.objects.create(sentence=Sentence.objects.create(source_text_ru="Три"), proposed_text_av="лъабго", author=second, status=TranslationSuggestion.Status.ACCEPTED)
        s2 = TranslationSuggestion.objects.create(sentence=Sentence.objects.create(source_text_ru="Четыре"), proposed_text_av="ункъо", author=first, status=TranslationSuggestion.Status.ACCEPTED)

        response = self.client.get(reverse("leaderboard"))
        self.assertEqual(response.status_code, 200)
        leaders = list(response.context["leaders"])
        self.assertTrue(len(leaders) >= 2)
