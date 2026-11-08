"""
Загрузить фразы для чтения из текстового файла (одна фраза — одна строка).

  python manage.py import_prompts фразы.txt --source "Название книги"
"""
from django.core.management.base import BaseCommand

from reading.models import Prompt


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, p):
        p.add_argument("file")
        p.add_argument("--source", default="")

    def handle(self, file, source, **_):
        rows = [l.strip() for l in open(file, encoding="utf-8-sig") if l.strip()]
        Prompt.objects.bulk_create([Prompt(text=t, source=source) for t in rows])
        self.stdout.write(self.style.SUCCESS(f"Добавлено фраз: {len(rows)}"))
