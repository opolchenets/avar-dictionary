import csv

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from corpus.models import Sentence
from gamification.models import PointLedger
from suggestions.models import SuggestionVote, TranslationSuggestion

User = get_user_model()

class EditorFlowTests(TestCase):
    def setUp(self):
        self.editor = User.objects.create_user(username="editor", password="Strong-pass123")
        self.editor.profile.role = self.editor.profile.Role.EDITOR
        self.editor.profile.save()

        self.user = User.objects.create_user(username="user", password="Strong-pass123")
        self.sentence = Sentence.objects.create(source_text_av="Авар текст", text_ru="Старый перевод", status=Sentence.Status.TRANSLATED, translated_by=self.user)
        self.suggestion = TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_ru="Новый перевод",
            author=self.user,
            status=TranslationSuggestion.Status.PENDING,
        )

    def test_non_editor_cannot_access_editor(self):
        self.client.login(username="user", password="Strong-pass123")
        response = self.client.get(reverse("editor-dashboard"))
        self.assertRedirects(response, reverse("home"))

    def test_accept_suggestion_updates_canonical_translation_and_awards_points(self):
        self.client.login(username="editor", password="Strong-pass123")
        response = self.client.post(
            reverse("editor-suggestions"),
            {
                "id": self.suggestion.id,
                "action": "accept",
                "editor_note": "Ок",
            },
        )

        self.assertRedirects(response, reverse("editor-suggestions"))
        self.sentence.refresh_from_db()
        self.suggestion.refresh_from_db()
        self.assertEqual(self.sentence.text_ru, "Новый перевод")
        self.assertEqual(self.suggestion.status, TranslationSuggestion.Status.ACCEPTED)
        self.assertEqual(
            PointLedger.objects.filter(
                user=self.user,
                reason=PointLedger.Reason.SUGGESTION_ACCEPTED,
            ).count(),
            1,
        )
        self.assertEqual(
            PointLedger.objects.get(
                user=self.user,
                reason=PointLedger.Reason.SUGGESTION_ACCEPTED,
            ).points,
            1,
        )

    def test_accept_first_suggestion_creates_canonical_translation(self):
        fresh_sentence = Sentence.objects.create(source_text_av="Новое аварское предложение", status=Sentence.Status.PENDING)
        fresh_suggestion = TranslationSuggestion.objects.create(
            sentence=fresh_sentence,
            proposed_text_ru="Первый принятый перевод",
            author=self.user,
            status=TranslationSuggestion.Status.PENDING,
        )

        self.client.login(username="editor", password="Strong-pass123")
        self.client.post(
            reverse("editor-suggestions"),
            {
                "id": fresh_suggestion.id,
                "action": "accept",
                "editor_note": "Берём",
            },
        )

        fresh_sentence.refresh_from_db()
        self.assertEqual(fresh_sentence.status, Sentence.Status.TRANSLATED)
        self.assertEqual(fresh_sentence.text_ru, "Первый принятый перевод")

    def test_reject_suggestion_keeps_canonical_translation(self):
        self.client.login(username="editor", password="Strong-pass123")
        self.client.post(
            reverse("editor-suggestions"),
            {
                "id": self.suggestion.id,
                "action": "reject",
                "editor_note": "Нет",
            },
        )

        self.sentence.refresh_from_db()
        self.suggestion.refresh_from_db()
        self.assertEqual(self.sentence.text_ru, "Старый перевод")
        self.assertEqual(self.suggestion.status, TranslationSuggestion.Status.REJECTED)

    def test_import_skips_duplicates_and_blanks(self):
        self.client.login(username="editor", password="Strong-pass123")
        response = self.client.post(
            reverse("editor-import"),
            {
                "sentences": "Авар текст\n\nНовое предложение\nНовое предложение\nЕщё одно",
            },
        )

        self.assertRedirects(response, reverse("editor-import"))
        self.assertEqual(Sentence.objects.count(), 3)

    def test_csv_export_contains_only_approved_corpus(self):
        self.client.login(username="editor", password="Strong-pass123")
        response = self.client.get(reverse("editor-export"))

        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(response.content.decode("utf-8").splitlines()))
        self.assertEqual(len(rows), 1)

    def test_editor_queue_prefers_more_voted_pending_suggestions(self):
        another = TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_ru="Ещё один вариант",
            author=self.user,
            status=TranslationSuggestion.Status.PENDING,
        )
        voter = User.objects.create_user(username="voter", password="Strong-pass123")
        SuggestionVote.objects.create(suggestion=another, user=voter)

        self.client.login(username="editor", password="Strong-pass123")
        response = self.client.get(reverse("editor-suggestions"))

        suggestions = list(response.context["suggestions"])
        self.assertEqual(suggestions[0].pk, another.pk)
