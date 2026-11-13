from django.urls import path

from . import views

urlpatterns = [
    path("phrases/", views.PromptManageView.as_view(), name="reading-prompts"),
    path("phrases/<int:pk>/", views.PromptTextUpdateView.as_view(), name="reading-prompt-update"),
    path("feedback/", views.PromptFeedbackQueue.as_view(), name="reading-feedback-queue"),
    path("feedback/<int:pk>/", views.PromptFeedbackVerdict.as_view(), name="reading-feedback-verdict"),
    path("<int:pk>/feedback/", views.PromptFeedbackView.as_view(), name="reading-feedback"),
    path("", views.ReadingHomeView.as_view(), name="reading-home"),
    path("next/", views.NextPromptView.as_view(), name="reading-next"),
    path("<int:pk>/", views.RecordView.as_view(), name="reading-record"),
    path("review/", views.ReviewView.as_view(), name="reading-review"),
    path("review/<int:pk>/", views.VerdictView.as_view(), name="reading-verdict"),
]
