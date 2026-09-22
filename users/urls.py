from django.urls import path

from .views import (
    FavoritePlayerListView,
    FavoritePlayerToggleView,
    NotificationListView,
    SignUpView,
    UserLoginView,
    UserLogoutView,
    mark_notification_read,
)

app_name = 'users'

urlpatterns = [
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('notifications/', NotificationListView.as_view(), name='notifications'),
    path('notifications/<int:pk>/read/', mark_notification_read, name='mark_notification_read'),
    path('favorites/', FavoritePlayerListView.as_view(), name='favorites'),
    path('players/<int:pk>/favorite/', FavoritePlayerToggleView.as_view(), name='favorite_toggle'),
]