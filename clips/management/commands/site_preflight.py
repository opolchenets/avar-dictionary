from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from clips.models import Clip
from reading.models import Prompt, Recording


class Command(BaseCommand):
    help = "Verify corpus data/media and reject weak test admin credentials before publication."

    def add_arguments(self, parser):
        parser.add_argument("--production", action="store_true")

    def handle(self, production, **kwargs):
        if not Clip.objects.exists() or not Prompt.objects.exists():
            raise CommandError("Corpus data is missing; import the instance first.")
        media = Path(settings.MEDIA_ROOT).resolve()
        missing = []
        for model in [Clip, Recording]:
            for name in model.objects.values_list("audio", flat=True):
                path = (media / name).resolve()
                if media not in path.parents or not path.is_file():
                    missing.append(name)
        if missing:
            raise CommandError(f"Missing or unsafe media paths: {len(missing)}")
        if production:
            if settings.DEBUG:
                raise CommandError("DEBUG must be false.")
            for user in get_user_model().objects.filter(is_staff=True, is_active=True):
                if any(user.check_password(p) for p in ["admin12345", "user12345", "admin", "password", "12345678"]):
                    raise CommandError(f"Replace test password for staff user {user.username}.")
        self.stdout.write(self.style.SUCCESS(f"OK: {Clip.objects.count()} clips; {Prompt.objects.count()} prompts; {Recording.objects.count()} recordings; media verified."))
