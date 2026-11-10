"""Portable, checksummed migration of an instance between SQLite/PostgreSQL."""
import hashlib
import json
import shutil
from pathlib import Path
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.serializers import register_serializer
from clips.models import Clip, Batch, ClipEdit
from reading.models import Prompt, Recording


def counts():
    return {model._meta.label: model.objects.count() for model in
            [get_user_model(), Batch, Clip, ClipEdit, Prompt, Recording]}


def digest(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


class Command(BaseCommand):
    help = "Export with writes stopped; import only into a migrated, empty instance."

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["export", "import"])
        parser.add_argument("directory")

    def handle(self, action, directory, **kwargs):
        directory = Path(directory).resolve()
        media = Path(settings.MEDIA_ROOT)
        if action == "export":
            register_serializer("json_precise", "core.precise_json")
            if directory.exists():
                raise CommandError("Export destination must not exist.")
            if directory == media.resolve() or media.resolve() in directory.parents:
                raise CommandError("Export destination must be outside media.")
            directory.mkdir(parents=True)
            with (directory / "database.json").open("w", encoding="utf-8") as output:
                call_command("dumpdata", format="json_precise", natural_foreign=True, exclude=["contenttypes", "auth.permission", "sessions"],
                             stdout=output, verbosity=0)
            shutil.copytree(media, directory / "media")
            files = {f.relative_to(directory).as_posix(): digest(f) for f in directory.rglob("*") if f.is_file()}
            manifest = {"version": 1, "counts": counts(), "files": files}
            (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        else:
            manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("version") != 1:
                raise CommandError("Unsupported transfer version.")
            for name, expected in manifest["files"].items():
                path = (directory / name).resolve()
                if directory not in path.parents or not path.is_file() or digest(path) != expected:
                    raise CommandError(f"Corrupt or unsafe transfer file: {name}")
            if get_user_model().objects.exists() or any(counts().values()):
                raise CommandError("Target instance is not empty; refusing to overwrite.")
            if media.exists() and any(media.iterdir()):
                raise CommandError("Target media must be empty.")
            copied = False
            try:
                shutil.copytree(directory / "media", media, dirs_exist_ok=True)
                copied = True
                with transaction.atomic():
                    call_command("loaddata", str(directory / "database.json"), verbosity=0)
                    if counts() != manifest["counts"]:
                        raise CommandError("Restored counts differ from source.")
                    for model in [Clip, Recording]:
                        for name in model.objects.values_list("audio", flat=True):
                            path = (media / name).resolve()
                            if media.resolve() not in path.parents or not path.is_file():
                                raise CommandError(f"Missing restored audio: {name}")
            except Exception:
                # Only remove the exact files we copied into the verified empty target.
                if copied:
                    for name in manifest["files"]:
                        if name.startswith("media/"):
                            target = media / Path(name).relative_to("media")
                            if target.is_file():
                                target.unlink()
                raise
        self.stdout.write(self.style.SUCCESS(json.dumps(counts())))
