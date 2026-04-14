from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.views.generic import TemplateView

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion

User = get_user_model()

from accounts.models import Alliance, District

class LeaderboardView(TemplateView):
    template_name = "gamification/leaderboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 1. Overall User Leaderboard
        user_leaders = (
            User.objects.filter(
                translation_suggestions__status=TranslationSuggestion.Status.ACCEPTED
            )
            .select_related("profile", "profile__district", "profile__district__alliance")
            .annotate(
                accepted_count=Count(
                    "translation_suggestions",
                    filter=Q(translation_suggestions__status=TranslationSuggestion.Status.ACCEPTED),
                    distinct=True,
                ),
            )
            .order_by("-accepted_count", "username")
        )
        context["user_leaders"] = user_leaders

        # 2. District Leaderboard
        district_leaders = (
            District.objects.annotate(
                accepted_count=Count(
                    "profiles__user__translation_suggestions",
                    filter=Q(profiles__user__translation_suggestions__status=TranslationSuggestion.Status.ACCEPTED),
                    distinct=True,
                )
            )
            .filter(accepted_count__gt=0)
            .select_related("alliance")
            .order_by("-accepted_count")
        )
        context["district_leaders"] = district_leaders

        # 3. Alliance Leaderboard
        alliance_leaders = (
            Alliance.objects.annotate(
                accepted_count=Count(
                    "districts__profiles__user__translation_suggestions",
                    filter=Q(districts__profiles__user__translation_suggestions__status=TranslationSuggestion.Status.ACCEPTED),
                    distinct=True,
                )
            )
            .filter(accepted_count__gt=0)
            .order_by("-accepted_count")
        )
        context["alliance_leaders"] = alliance_leaders

        context["total_translations"] = Sentence.objects.filter(status=Sentence.Status.TRANSLATED).count()
        return context
