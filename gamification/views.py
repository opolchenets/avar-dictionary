from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.views.generic import TemplateView

from corpus.models import Sentence
from suggestions.models import TranslationSuggestion

User = get_user_model()

from accounts.models import Alliance, District

class LeaderboardView(TemplateView):
    template_name = "gamification/leaderboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Рейтинг = сумма очков (правки фрагментов, совпадения, контрольные, старые переводы)
        user_leaders = (
            User.objects.annotate(accepted_count=Sum("point_entries__points"))
            .filter(accepted_count__gt=0)
            .select_related("profile", "profile__district", "profile__district__alliance")
            .order_by("-accepted_count", "username")
        )
        context["user_leaders"] = user_leaders
        context["district_leaders"] = (
            District.objects.annotate(accepted_count=Sum("profiles__user__point_entries__points"))
            .filter(accepted_count__gt=0).select_related("alliance").order_by("-accepted_count")
        )
        context["alliance_leaders"] = (
            Alliance.objects.annotate(accepted_count=Sum("districts__profiles__user__point_entries__points"))
            .filter(accepted_count__gt=0).order_by("-accepted_count")
        )
        context["total_translations"] = Sentence.objects.filter(status=Sentence.Status.TRANSLATED).count()
        return context
