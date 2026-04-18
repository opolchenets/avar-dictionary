from .models import Notification

def user_notifications(request):
    if not request.user.is_authenticated:
        return {
            'unread_notifications_count': 0,
            'latest_notifications': []
        }
    
    notifications = Notification.objects.filter(user=request.user).select_related(
        'suggestion', 'suggestion__sentence'
    )
    unread_count = notifications.filter(is_read=False).count()
    latest = notifications.order_by('-created_at')[:10]
    
    return {
        'unread_notifications_count': unread_count,
        'latest_notifications': latest
    }
