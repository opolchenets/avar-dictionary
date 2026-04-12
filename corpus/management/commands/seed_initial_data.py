from django.core.management.base import BaseCommand

from corpus.models import Sentence


SAMPLE_SENTENCES = [
    "Дие гӏемер гӏарац кьола дица гьабулеб жоялъухъ.",
    "Томида квекийилан гьаризе бегьулищ?",
    "Анлӏгоялда вахъиналъул правила ккун чӏун вуго дун.",
    "Машина бачине цӀакъ кепаб жо буго.",
    "Дица гьабизе кколеб хӀалтӀи гӀемераб буго.",
    "Къаникье инчӀого вукӀине, дица кӀвараб хӀалалъ дагь гьабула.",
    "Дие гьеб бокьун буго щвезе кӏварабго.",
    "Дун свакана гин дие кьижизе ине бокьун буго.",
    "Дие дудаса цохӏо къваригӀараб жо буго — нижгун кӏалъазе.",
    "Дие бокьун буго кӀварабгӀан лъикӀ дирго хӀалтӀи гьабизе.",
]


class Command(BaseCommand):
    help = "Populate the database with initial Avar sample sentences when corpus is empty."

    def handle(self, *args, **options):
        if Sentence.objects.exists():
            self.stdout.write(
                self.style.WARNING("Пропущено: в корпусе уже есть предложения.")
            )
            return

        Sentence.objects.bulk_create(
            [Sentence(source_text_av=text) for text in SAMPLE_SENTENCES]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Добавлены стартовые примеры предложений: {len(SAMPLE_SENTENCES)}."
            )
        )
