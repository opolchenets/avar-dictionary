from django.urls import path

from .views import ProfileView, SignUpView, mark_notifications_read, PublicProfileView


urlpatterns = [
    path("signup/", SignUpView.as_view(), name="signup"),
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/<int:pk>/", PublicProfileView.as_view(), name="public-profile"),
    path("notifications/read/", mark_notifications_read, name="notification-mark-read"),
]
