from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from accounts.models import Alliance, District
from corpus.models import Sentence
from suggestions.models import TranslationSuggestion

User = get_user_model()


class LeaderboardTests(TestCase):
    def test_leaderboard_orders_by_total_points(self):
        red = Alliance.objects.create(name="Красный", color="#c00")
        blue = Alliance.objects.create(name="Синий", color="#00c")
        north = District.objects.create(name="Север", alliance=red)
        south = District.objects.create(name="Юг", alliance=blue)

        first = User.objects.create_user(username="first", password="Strong-pass123")
        second = User.objects.create_user(username="second", password="Strong-pass123")
        first.profile.district = south
        first.profile.save()
        second.profile.district = north
        second.profile.save()

        TranslationSuggestion.objects.create(
            sentence=Sentence.objects.create(source_text_ru="Один"),
            proposed_text_av="цо",
            author=second,
            status=TranslationSuggestion.Status.ACCEPTED,
        )
        TranslationSuggestion.objects.create(
            sentence=Sentence.objects.create(source_text_ru="Два"),
            proposed_text_av="кIиго",
            author=second,
            status=TranslationSuggestion.Status.ACCEPTED,
        )
        TranslationSuggestion.objects.create(
            sentence=Sentence.objects.create(source_text_ru="Три"),
            proposed_text_av="лъабго",
            author=first,
            status=TranslationSuggestion.Status.ACCEPTED,
        )

        response = self.client.get(reverse("leaderboard"))
        self.assertEqual(response.status_code, 200)
        user_leaders = list(response.context["user_leaders"])
        district_leaders = list(response.context["district_leaders"])
        alliance_leaders = list(response.context["alliance_leaders"])

        self.assertEqual(user_leaders[0].username, "second")
        self.assertEqual(user_leaders[0].accepted_count, 2)
        self.assertEqual(district_leaders[0].name, "Север")
        self.assertEqual(district_leaders[0].accepted_count, 2)
        self.assertEqual(alliance_leaders[0].name, "Красный")
        self.assertEqual(alliance_leaders[0].accepted_count, 2)
