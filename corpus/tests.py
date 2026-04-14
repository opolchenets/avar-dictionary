from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion

User = get_user_model()


class CorpusFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="user", password="Strong-pass123")
        self.sentence = Sentence.objects.create(source_text_ru="Книга")

    def test_anonymous_cannot_submit_translation(self):
        response = self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_av": "ТIехь"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.text_av, "")

    def test_first_translation_creates_pending_suggestion(self):
        self.client.login(username="user", password="Strong-pass123")
        response = self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_av": "ТIехь"},
        )
        self.assertRedirects(response, reverse("sentence-detail", args=[self.sentence.pk]))
        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.status, Sentence.Status.PENDING)
        self.assertEqual(self.sentence.text_av, "")
        suggestion = TranslationSuggestion.objects.get(sentence=self.sentence)
        self.assertEqual(suggestion.proposed_text_av, "ТIехь")

    def test_existing_translation_creates_suggestion(self):
        other_user = User.objects.create_user(username="other", password="Strong-pass123")
        self.sentence.text_av = "ТIехь"
        self.sentence.translated_by = other_user
        self.sentence.status = Sentence.Status.TRANSLATED
        self.sentence.save()

        self.client.login(username="user", password="Strong-pass123")
        self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_av": "ТIехьча"},
        )

        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.text_av, "ТIехь")
        suggestion = TranslationSuggestion.objects.get(sentence=self.sentence, proposed_text_av="ТIехьча")
        self.assertEqual(suggestion.proposed_text_av, "ТIехьча")

    def test_sentence_list_shows_pending_suggestions(self):
        other_user = User.objects.create_user(username="other", password="Strong-pass123")
        self.sentence.text_av = "ТIехь"
        self.sentence.translated_by = other_user
        self.sentence.status = Sentence.Status.TRANSLATED
        self.sentence.save()
        TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_av="Вариант",
            author=other_user,
        )
        response = self.client.get(reverse("sentence-list"))
        self.assertContains(response, "Другие предложенные варианты")
        self.assertContains(response, "Вариант")

    def test_sentence_list_post_ignores_external_redirect_target(self):
        self.client.login(username="user", password="Strong-pass123")
        response = self.client.post(
            reverse("sentence-list"),
            {
                "sentence_id": self.sentence.pk,
                "text_av": "ТIехь",
                "next": "https://evil.example/phishing",
            },
        )

        self.assertRedirects(response, reverse("sentence-list"))

    def test_duplicate_suggestion_is_rejected(self):
        TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_av="ТIехь",
            author=self.user,
        )
        self.client.login(username="user", password="Strong-pass123")

        response = self.client.post(
            reverse("sentence-detail", args=[self.sentence.pk]),
            {"text_av": "ТIехь"},
        )

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertIn("Такой вариант уже предложен", form.errors["text_av"][0])
