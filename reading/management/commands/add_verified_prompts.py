from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from clips.models import AudioIssue, Clip
from common.normalizer import normalize
from reading.models import Prompt


class Command(BaseCommand):
    help = "Add 100 distinct reading prompts from accepted, non-control Fazu/Gazdada transcriptions. Preview by default."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=100)
        parser.add_argument("--apply", action="store_true")

    @transaction.atomic
    def handle(self, count, apply, **kwargs):
        if count < 1:
            raise CommandError("Count must be positive")
        existing = {normalize(text) for text in Prompt.objects.values_list("text", flat=True)}
        clips = (Clip.objects.filter(is_gold=False, status=Clip.Status.RESOLVED)
                 .filter(Q(batch__name__icontains="Фазу") | Q(batch__name__icontains="ГӀаздада"))
                 .exclude(final_text="")
                 .exclude(id__in=AudioIssue.objects.filter(reviewed_at__isnull=True).values("clip_id"))
                 .select_related("batch"))
        # Use all verified Fazu phrases before Gazdada; stable clip order within sources.
        candidates = sorted(clips, key=lambda clip: ("Фазу" not in clip.batch.name, clip.pk))
        selected = []
        for clip in candidates:
            text = clip.final_text.strip()
            key = normalize(text)
            if not 20 <= len(text) <= 180 or not key or key == "#" or key in existing:
                continue
            existing.add(key)
            selected.append(Prompt(text=text, source=clip.batch.source or clip.batch.name))
            if len(selected) == count:
                break
        if len(selected) != count:
            raise CommandError(f"Only {len(selected)} suitable new phrases; requested {count}. Nothing added.")
        if apply:
            Prompt.objects.bulk_create(selected)
        self.stdout.write(f"{'ADDED' if apply else 'PREVIEW'}: {len(selected)} new phrases; "
                          f"Fazu={sum('Фазу' in p.source for p in selected)}, "
                          f"Gazdada={sum('ГӀаздада' in p.source for p in selected)}")
