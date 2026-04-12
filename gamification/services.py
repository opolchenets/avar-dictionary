from gamification.models import PointLedger


def award_points(*, user, reason, points, sentence=None, suggestion=None):
    return PointLedger.objects.create(
        user=user,
        reason=reason,
        points=points,
        sentence=sentence,
        suggestion=suggestion,
    )
