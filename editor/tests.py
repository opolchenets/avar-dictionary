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
        self.sentence = Sentence.objects.create(
            source_text_ru="Книга", 
            text_av="ТIехь", 
            status=Sentence.Status.TRANSLATED, 
            translated_by=self.user
        )
        self.suggestion = TranslationSuggestion.objects.create(
            sentence=self.sentence,
            proposed_text_av="ЦIияб тIехь",
            author=self.user,
            status=TranslationSuggestion.Status.PENDING,
        )

    def test_accept_suggestion_updates_sentence_and_awards_points(self):
        self.client.login(username="editor", password="Strong-pass123")
        response = self.client.post(
            reverse("editor-suggestions"),
            {
                "id": self.suggestion.id,
                "action": "accept",
            },
        )

        self.assertRedirects(response, reverse("editor-suggestions"))
        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.text_av, "ЦIияб тIехь")
        self.assertEqual(
            PointLedger.objects.filter(
                user=self.user,
                reason=PointLedger.Reason.SUGGESTION_ACCEPTED,
            ).count(),
            1,
        )

    def test_reject_last_pending_suggestion_returns_sentence_to_untranslated(self):
        self.client.login(username="editor", password="Strong-pass123")
        sentence = Sentence.objects.create(
            source_text_ru="Стол",
            status=Sentence.Status.PENDING,
        )
        suggestion = TranslationSuggestion.objects.create(
            sentence=sentence,
            proposed_text_av="Өстел",
            author=self.user,
        )

        self.client.post(
            reverse("editor-suggestions"),
            {
                "id": suggestion.id,
                "action": "reject",
            },
        )

        sentence.refresh_from_db()
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, TranslationSuggestion.Status.REJECTED)
        self.assertEqual(sentence.status, Sentence.Status.UNTRANSLATED)
        self.assertEqual(sentence.text_av, "")

    def test_delete_translation_keeps_sentence_pending_when_suggestions_exist(self):
        self.client.login(username="editor", password="Strong-pass123")
        response = self.client.post(
            reverse("editor-sentences"),
            {
                "sentence_id": self.sentence.id,
                "action": "delete_translation",
            },
        )

        self.assertRedirects(response, reverse("editor-sentences"))
        self.sentence.refresh_from_db()
        self.assertEqual(self.sentence.text_av, "")
        self.assertEqual(self.sentence.status, Sentence.Status.PENDING)

    def test_import_sentences_skips_duplicates(self):
        self.client.login(username="editor", password="Strong-pass123")
        response = self.client.post(
            reverse("editor-import"),
            {
                "sentences": "Книга\nПривет\nПривет\nПока",
            },
        )

        self.assertRedirects(response, reverse("editor-import"))
        self.assertEqual(
            Sentence.objects.filter(source_text_ru__in=["Привет", "Пока"]).count(),
            2,
        )
