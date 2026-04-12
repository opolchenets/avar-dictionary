from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from corpus.models import Sentence
from gamification.models import PointLedger
from suggestions.models import SuggestionVote, TranslationSuggestion

User = get_user_model()

class CorpusFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="Strong-pass123")
        self.sentence = Sentence.objects.create(source_text_av="Авар мацI")

    def test_anonymous_cannot_submit_translation(self):
        response = self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_ru": "Перевод"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.text_ru, "")

    def test_first_translation_creates_canonical_translation_and_points(self):
        self.client.login(username="user", password="Strong-pass123")
        response = self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_ru": "Первый перевод"},
        )
        self.assertRedirects(response, reverse("sentence-detail", args=[self.sentence.pk]))
        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.status, Sentence.Status.PENDING)
        self.assertEqual(self.sentence.text_ru, "")
        suggestion = TranslationSuggestion.objects.get(sentence=self.sentence)
        self.assertEqual(suggestion.proposed_text_ru, "Первый перевод")
        self.assertFalse(PointLedger.objects.filter(user=self.user).exists())

    def test_existing_translation_creates_suggestion(self):
        other_user = User.objects.create_user(username="other", password="Strong-pass123")
        self.sentence.text_ru = "Исходный перевод"
        self.sentence.translated_by = other_user
        self.sentence.status = Sentence.Status.TRANSLATED
        self.sentence.save()

        self.client.login(username="user", password="Strong-pass123")
        self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_ru": "Новая версия"},
        )

        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.text_ru, "Исходный перевод")
        suggestion = TranslationSuggestion.objects.get(sentence=self.sentence)
        self.assertEqual(suggestion.proposed_text_ru, "Новая версия")
        self.assertFalse(PointLedger.objects.filter(user=self.user).exists())

    def test_can_vote_for_pending_suggestion(self):
        other_user = User.objects.create_user(username="other", password="Strong-pass123")
        self.sentence.text_ru = "Исходный перевод"
        self.sentence.translated_by = other_user
        self.sentence.status = Sentence.Status.TRANSLATED
        self.sentence.save()
        suggestion = TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_ru="Поддерживаемый вариант",
            author=other_user,
        )

        self.client.login(username="user", password="Strong-pass123")
        response = self.client.post(
            reverse("suggestion-vote-toggle", args=[self.sentence.pk, suggestion.pk]),
            {"next": f"{reverse('sentence-list')}#sentence-{self.sentence.pk}"},
        )

        self.assertEqual(
            response.headers["Location"],
            f"{reverse('sentence-list')}#sentence-{self.sentence.pk}",
        )
        self.assertTrue(
            SuggestionVote.objects.filter(suggestion=suggestion, user=self.user).exists()
        )

    def test_duplicate_suggestion_is_rejected_in_form(self):
        other_user = User.objects.create_user(username="other", password="Strong-pass123")
        self.sentence.text_ru = "Исходный перевод"
        self.sentence.translated_by = other_user
        self.sentence.status = Sentence.Status.TRANSLATED
        self.sentence.save()
        TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_ru="Одинаковый вариант",
            author=other_user,
        )

        self.client.login(username="user", password="Strong-pass123")
        response = self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_ru": "Одинаковый вариант"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Такой вариант уже предложен")

    def test_sentence_list_allows_inline_translation_submission(self):
        self.client.login(username="user", password="Strong-pass123")
        response = self.client.post(
            reverse("sentence-list"),
            {
                "sentence_id": self.sentence.pk,
                "text_ru": "Перевод из списка",
                "next": f"{reverse('sentence-list')}#sentence-{self.sentence.pk}",
            },
        )
        self.assertEqual(
            response.headers["Location"],
            f"{reverse('sentence-list')}#sentence-{self.sentence.pk}",
        )
        self.assertEqual(
            TranslationSuggestion.objects.get(sentence=self.sentence).proposed_text_ru,
            "Перевод из списка",
        )

    def test_sentence_list_shows_pending_suggestions(self):
        other_user = User.objects.create_user(username="other", password="Strong-pass123")
        self.sentence.text_ru = "Исходный перевод"
        self.sentence.translated_by = other_user
        self.sentence.status = Sentence.Status.TRANSLATED
        self.sentence.save()
        TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_ru="Вариант из списка",
            author=other_user,
        )
        response = self.client.get(reverse("sentence-list"))
        self.assertContains(response, "Предложенные варианты")
        self.assertContains(response, "Вариант из списка")

class SeedInitialDataTests(TestCase):
    def test_seed_initial_data_populates_empty_corpus_once(self):
        self.assertEqual(Sentence.objects.count(), 0)
        call_command("seed_initial_data")
        first_count = Sentence.objects.count()
        call_command("seed_initial_data")
        self.assertEqual(first_count, 10)
        self.assertEqual(Sentence.objects.count(), 10)
