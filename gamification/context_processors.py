from django.db.models import Sum
from .models import PointLedger

def user_points(request):
    if request.user.is_authenticated:
        points = PointLedger.objects.filter(user=request.user).aggregate(total=Sum('points'))['total'] or 0
        return {'user_total_points': points}
    return {}
