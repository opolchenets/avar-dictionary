"""
Загрузить пачку фрагментов.

  python manage.py import_clips путь/к/папке --name "Пачка 1" --source "ГӀаздада…, Абдуразаков" [--gold-share 0.15]

В папке: wavs/*.wav и metadata.csv в формате LJSpeech:  wavs/xxx.wav|черновик ASR|длительность
Необязательно 4-й столбец — эталонный текст: такие фрагменты становятся контрольными.
--gold-share: какую долю фрагментов с эталоном сделать контрольными (остальные — обычные).
"""
import csv
import os
import random

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from clips.models import Batch, Clip


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, p):
        p.add_argument("folder")
        p.add_argument("--name", required=True)
        p.add_argument("--source", default="")
        p.add_argument("--gold-share", type=float, default=1.0)

    def handle(self, folder, name, source, gold_share, **_):
        meta = os.path.join(folder, "metadata.csv")
        if not os.path.exists(meta):
            raise CommandError(f"нет {meta}")
        batch = Batch.objects.create(name=name, source=source)
        n = g = 0
        with open(meta, encoding="utf-8-sig") as f:
            for row in csv.reader(f, delimiter="|"):
                if not row or row[0].startswith("#"):
                    continue
                path, draft = row[0], row[1] if len(row) > 1 else ""
                dur = float(row[2]) if len(row) > 2 and row[2] else 0
                gold = row[3].strip() if len(row) > 3 else ""
                is_gold = bool(gold) and random.random() < gold_share
                clip = Clip(batch=batch, draft_text=draft, duration=dur, source_ref=path,
                            is_gold=is_gold, gold_text=gold if is_gold else "")
                with open(os.path.join(folder, path), "rb") as af:
                    clip.audio.save(f"{batch.pk}_{os.path.basename(path)}", File(af), save=False)
                clip.save()
                n += 1
                g += is_gold
        self.stdout.write(self.style.SUCCESS(f"Пачка «{name}»: {n} фрагментов, из них контрольных {g}"))
