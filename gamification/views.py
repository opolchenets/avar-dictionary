from django.views.generic import TemplateView

from .ranking import group_rows, user_rows


class LeaderboardView(TemplateView):
    template_name = "gamification/leaderboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rows = user_rows()
        context["user_rows"] = rows
        context["district_rows"] = group_rows(rows, "district")
        context["alliance_rows"] = group_rows(rows, "alliance")
        return context
