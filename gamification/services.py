from django.db.models import Count
from gamification.models import Achievement, PointLedger, UserAchievement
from suggestions.models import TranslationSuggestion


def check_achievements(user):
    accepted_count = TranslationSuggestion.objects.filter(
        author=user,
        status=TranslationSuggestion.Status.ACCEPTED
    ).count()

    # Get achievements the user doesn't have yet
    new_achievements = Achievement.objects.filter(
        threshold__lte=accepted_count
    ).exclude(
        pk__in=UserAchievement.objects.filter(user=user).values_list("achievement_id", flat=True)
    )

    for achievement in new_achievements:
        UserAchievement.objects.get_or_create(user=user, achievement=achievement)


def award_points(*, user, reason, points, sentence=None, suggestion=None):
    ledger = PointLedger.objects.create(
        user=user,
        reason=reason,
        points=points,
        sentence=sentence,
        suggestion=suggestion,
    )
    if reason == PointLedger.Reason.SUGGESTION_ACCEPTED:
        check_achievements(user)
    return ledger
