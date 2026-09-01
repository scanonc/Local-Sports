from users.models import Notification


def unread_notifications(request):
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': Notification.objects.filter(
                user=request.user,
                is_read=False,
            ).count(),
            'unread_notifications': Notification.objects.filter(
                user=request.user,
                is_read=False,
            )[:10],
        }
    return {
        'unread_notifications_count': 0,
        'unread_notifications': [],
    }
