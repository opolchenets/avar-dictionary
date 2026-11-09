"""
Удалить пользователей вместе со всем, что они сделали на сайте (для очистки тестовых данных).

  python manage.py remove_users                   — показать, кто будет удалён (все, кроме admin)
  python manage.py remove_users --keep admin ali  — кого оставить (по логину)
  python manage.py remove_users --go              — удалить (спросит подтверждение)

Удаляются: правки фрагментов, озвучки (и их файлы), согласия, очки, голоса и переводы старого раздела.
Фрагменты, которые эти люди закрыли, возвращаются в работу. Сами пачки и фразы остаются.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from clips.models import Clip, ClipEdit
from gamification.models import PointLedger
from reading.models import Consent, Recording
from suggestions.models import SuggestionVote, TranslationSuggestion


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, p):
        p.add_argument("--keep", nargs="+", default=["admin"], metavar="ЛОГИН")
        p.add_argument("--go", action="store_true", help="удалить (без него — только показать)")
        p.add_argument("--yes", action="store_true", help="не спрашивать подтверждение")

    def handle(self, keep, go, yes, **_):
        User = get_user_model()
        users = User.objects.exclude(username__in=keep).order_by("username")
        self.stdout.write(f"Остаются: {', '.join(keep)}")
        for u in users:
            self.stdout.write(f"  удалить: {u.username:<20} правок {ClipEdit.objects.filter(user=u).count():>4}  "
                              f"озвучек {Recording.objects.filter(user=u).count():>3}")
        if not users:
            self.stdout.write("Удалять некого.")
            return
        if not go:
            self.stdout.write("Это просмотр. Чтобы удалить: python manage.py remove_users --go")
            return
        if not yes and input(f"Удалить {users.count()} пользователей и всё, что они сделали? [y/n] ").strip().lower() != "y":
            self.stdout.write("Отменено.")
            return
        with transaction.atomic():
            touched = set(ClipEdit.objects.filter(user__in=users).values_list("clip_id", flat=True))
            files = [r.audio for r in Recording.objects.filter(user__in=users)]
            PointLedger.objects.filter(user__in=users).delete()
            ClipEdit.objects.filter(user__in=users).delete()
            Recording.objects.filter(reviewed_by__in=users).update(reviewed_by=None)
            ClipEdit.objects.filter(reviewed_by__in=users).update(reviewed_by=None)
            Recording.objects.filter(user__in=users).delete()
            Consent.objects.filter(user__in=users).delete()
            SuggestionVote.objects.filter(user__in=users).delete()
            TranslationSuggestion.objects.filter(reviewed_by__in=users).update(reviewed_by=None)
            TranslationSuggestion.objects.filter(author__in=users).delete()
            # фрагменты, где остались чужие правки или не осталось ничего, — пересчитать статус
            for c in Clip.objects.filter(pk__in=touched, is_gold=False):
                left = list(c.edits.all())
                if not any(e.verdict == "accepted" for e in left):
                    c.final_text = ""
                    c.status = Clip.Status.OPEN if len(left) < Clip.REQUIRED_EDITS else Clip.Status.DISPUTED
                    c.save(update_fields=["final_text", "status", "updated_at"])
            n = users.count()
            users.delete()
        for f in files:
            f.delete(save=False)
        self.stdout.write(self.style.SUCCESS(f"Удалено пользователей: {n}. Фрагментов возвращено в работу: {len(touched)}"))
