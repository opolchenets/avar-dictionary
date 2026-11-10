from django.urls import path

from .views import AsrDemoView

urlpatterns = [path("", AsrDemoView.as_view(), name="asr-demo")]
