from django.urls import path

from . import views

urlpatterns = [
    path("", views.ReadingHomeView.as_view(), name="reading-home"),
    path("next/", views.NextPromptView.as_view(), name="reading-next"),
    path("<int:pk>/", views.RecordView.as_view(), name="reading-record"),
    path("review/", views.ReviewView.as_view(), name="reading-review"),
    path("review/<int:pk>/", views.VerdictView.as_view(), name="reading-verdict"),
]
