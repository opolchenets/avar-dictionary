from django.urls import path

from . import views

urlpatterns = [
    path("", views.ClipHomeView.as_view(), name="clip-home"),
    path("next/", views.NextClipView.as_view(), name="clip-next"),
    path("<int:pk>/", views.ClipEditView.as_view(), name="clip-edit"),
    path("review/", views.ReviewQueueView.as_view(), name="clip-review"),
    path("review/edit/<int:pk>/verdict/", views.VerdictView.as_view(), name="clip-verdict"),
    path("review/<int:pk>/resolve/", views.ResolveView.as_view(), name="clip-resolve"),
]
