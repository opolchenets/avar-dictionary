"""
Пачки фрагментов: список, переименование, удаление.

  python manage.py batches                         — список пачек (id, название, фрагментов, проверочных, правок)
  python manage.py batches --rename 3 "Новое имя"  — переименовать
  python manage.py batches --delete 1 2            — удалить пачки ВМЕСТЕ с их фрагментами, правками и очками

Обычное удаление через админку запрещено (on_delete=PROTECT), чтобы данные не пропадали случайно.
Эта команда — осознанное удаление: спрашивает подтверждение и удаляет всё связанное.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q

from clips.models import Batch, Clip, ClipEdit
from gamification.models import PointLedger


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, p):
        p.add_argument("--delete", nargs="+", type=int, metavar="ID")
        p.add_argument("--rename", nargs=2, metavar=("ID", "NAME"))
        p.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")

    def handle(self, delete=None, rename=None, yes=False, **_):
        if rename:
            b = Batch.objects.filter(pk=int(rename[0])).first()
            if not b:
                raise CommandError(f"нет пачки {rename[0]}")
            b.name = rename[1]
            b.save(update_fields=["name"])
            self.stdout.write(self.style.SUCCESS(f"Пачка {b.pk} теперь называется «{b.name}»"))
            return
        qs = Batch.objects.annotate(
            n=Count("clips", distinct=True),
            g=Count("clips", filter=Q(clips__is_gold=True), distinct=True),
            e=Count("clips__edits", distinct=True),
        ).order_by("id")
        if delete:
            qs = qs.filter(pk__in=delete)
            if not qs:
                raise CommandError("таких пачек нет")
        for b in qs:
            self.stdout.write(f"{b.pk:>4}  {b.name:<35} фрагментов {b.n:>4}  проверочных {b.g:>4}  правок {b.e:>4}  {b.source}")
        if not delete:
            return
        if not yes and input("Удалить эти пачки вместе с фрагментами, правками и очками? [y/n] ").strip().lower() != "y":
            self.stdout.write("Отменено.")
            return
        with transaction.atomic():
            clips = Clip.objects.filter(batch__in=qs)
            files = [c.audio for c in clips]
            PointLedger.objects.filter(clip__in=clips).delete()
            ClipEdit.objects.filter(clip__in=clips).delete()
            n = clips.count()
            clips.delete()
            Batch.objects.filter(pk__in=[b.pk for b in qs]).delete()
        for f in files:   # аудиофайлы — после успешного удаления из базы
            f.delete(save=False)
        self.stdout.write(self.style.SUCCESS(f"Удалено пачек: {len(delete)}, фрагментов: {n}"))
