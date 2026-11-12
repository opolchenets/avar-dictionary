import csv
import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Q

from clips.models import AudioIssue, Clip, ClipEdit
from reading.models import Recording


def attribution(user):
    profile = getattr(user, "profile", None)
    district = getattr(profile, "district", None)
    alliance = getattr(district, "alliance", None)
    return (user.pk, user.username, district.name if district else "", alliance.name if alliance else "")


class Command(BaseCommand):
    help = "Preview/export accepted non-control Fazu/Gazdada clips and accepted readings; never export pending data."

    def add_arguments(self, parser):
        parser.add_argument("directory")

    def handle(self, directory, **options):
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        totals = defaultdict(lambda: {"items": 0, "seconds": 0.0})
        fields = ["id", "audio", "text", "seconds", "source", "batch", "author_id", "author", "district", "alliance", "decision"]
        with (root / "transcriptions.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(fields)
            clips = (Clip.objects.filter(is_gold=False, status=Clip.Status.RESOLVED)
                     .filter(Q(batch__name__icontains="Фазу") | Q(batch__name__icontains="ГӀаздада"))
                     .exclude(id__in=AudioIssue.objects.filter(reviewed_at__isnull=True).values("clip_id"))
                     .exclude(final_text="").select_related("batch").order_by("pk"))
            for clip in clips.iterator():
                # One audio row per clip, even if several contributors were accepted.
                matching = (ClipEdit.objects.filter(clip=clip, verdict="accepted", text=clip.final_text)
                            .select_related("user__profile__district__alliance").order_by("reviewed_at", "pk").first())
                author = attribution(matching.user) if matching else ("", "", "", "")
                decision = ("three_agreed" if matching.auto_accepted else "accepted_edit") if matching else "editor_text"
                writer.writerow([clip.pk, clip.audio.name, clip.final_text, clip.duration,
                                 clip.batch.source, clip.batch.name, *author, decision])
                totals[clip.batch.name]["items"] += 1
                totals[clip.batch.name]["seconds"] += clip.duration
        with (root / "readings.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["id", "audio", "text_at_recording", "seconds", "source", "prompt_id",
                             "speaker_id", "speaker", "district", "alliance"])
            recs = (Recording.objects.filter(status="accepted")
                    .select_related("prompt", "user__profile__district__alliance").order_by("pk"))
            for rec in recs.iterator():
                writer.writerow([rec.pk, rec.audio.name, rec.spoken_text, rec.duration, rec.prompt.source,
                                 rec.prompt_id, *attribution(rec.user)])
                totals["Прочтение"]["items"] += 1
                totals["Прочтение"]["seconds"] += rec.duration
        summary = {key: {**value, "minutes": round(value["seconds"] / 60, 3)} for key, value in totals.items()}
        summary["total"] = {"items": sum(x["items"] for x in totals.values()),
                            "seconds": sum(x["seconds"] for x in totals.values())}
        (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        self.stdout.write(json.dumps(summary, ensure_ascii=False))
