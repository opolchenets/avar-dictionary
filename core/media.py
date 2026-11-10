from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.views.static import serve
from django.http import Http404
from clips.models import Clip
from reading.models import Recording

@login_required
def private_media(request, path):
    if not Clip.objects.filter(audio=path).exists():
        recording = Recording.objects.filter(audio=path).first()
        editor = request.user.is_staff or request.user.is_superuser or getattr(getattr(request.user, "profile", None), "is_editor", False) or getattr(getattr(request.user, "profile", None), "is_co_editor", False)
        if recording is None or (recording.user_id != request.user.pk and not editor):
            raise Http404
    return serve(request, path, document_root=settings.MEDIA_ROOT)
