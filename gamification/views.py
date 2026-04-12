from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.views.generic import TemplateView

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion

User = get_user_model()

class LeaderboardView(TemplateView):
    template_name = "gamification/leaderboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leaders = (
            User.objects.filter(
                translation_suggestions__status=TranslationSuggestion.Status.ACCEPTED
            )
            .select_related("profile")
            .annotate(
                translation_count=Count("translated_sentences", distinct=True),
                suggestion_count=Count("translation_suggestions", distinct=True),
                accepted_count=Count(
                    "translation_suggestions",
                    filter=Q(
                        translation_suggestions__status=TranslationSuggestion.Status.ACCEPTED
                    ),
                    distinct=True,
                ),
            )
            .order_by("-accepted_count", "-translation_count", "username")
        )
        context["leaders"] = [
            {
                "display_name": leader.profile.display_name or leader.username,
                "username": leader.username,
                "total_points": leader.accepted_count,
                "translation_count": leader.translation_count,
                "suggestion_count": leader.suggestion_count,
                "accepted_count": leader.accepted_count,
            }
            for leader in leaders
        ]
        context["total_participants"] = len(context["leaders"])
        context["total_translations"] = Sentence.objects.filter(status=Sentence.Status.TRANSLATED).count()
        context["total_accepted"] = TranslationSuggestion.objects.filter(
            status=TranslationSuggestion.Status.ACCEPTED
        ).count()
        return context
