from django.core.management.base import BaseCommand

from corpus.models import Sentence


SAMPLE_SENTENCES = [
    "Я получаю много денег за то, что я делаю.",
    "Могу я попросить Тома о помощи?",
    "Я соблюдаю правила шестидесяти.",
    "Водить машину — очень веселое занятие.",
    "Мне нужно сделать много работы.",
    "Чтобы не попасть в могилу, я стараюсь делать поменьше.",
    "Я хочу получить это как можно скорее.",
    "Я устал и хочу пойти спать.",
    "Мне от тебя нужно только одно — поговори с нами.",
    "Я хочу выполнять свою работу как можно лучше.",
]


class Command(BaseCommand):
    help = "Populate the database with initial Russian sample sentences when corpus is empty."

    def handle(self, *args, **options):
        if Sentence.objects.exists():
            self.stdout.write(
                self.style.WARNING("Пропущено: в корпусе уже есть предложения.")
            )
            return

        Sentence.objects.bulk_create(
            [Sentence(source_text_ru=text) for text in SAMPLE_SENTENCES]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Добавлены стартовые примеры предложений: {len(SAMPLE_SENTENCES)}."
            )
        )
