from django.core.management.base import BaseCommand
from django.db import transaction
from corpus.models import Category, Sentence
from accounts.models import Alliance, District
from gamification.models import Achievement

ALLIANCES = {
    "🔥 Юг": {
        "color": "Красный/оранжевый",
        "districts": ["Тлярата", "Цор", "Чарода"]
    },
    "⚫️ Центр": {
        "color": "Золотой/серый",
        "districts": ["Хунзах", "Унцукуль"]
    },
    "🌿 Запад": {
        "color": "Зелёный",
        "districts": ["Ботлих", "Цумада", "Цунта", "Ахвах"]
    },
    "🔵 Север": {
        "color": "Синий/голубой",
        "districts": ["Гумбет", "Салатавия", "Буйнакск"]
    },
    "🟡 Восток": {
        "color": "Жёлтый/золотой",
        "districts": ["Леваши", "Гуниб", "Шамильский", "Гергебиль"]
    }
}

CATEGORIES = [
    ("Быт", "byt"),
    ("Повседневные предложения", "povsednevnye"),
    ("История", "istoriya"),
    ("Биология", "biologiya"),
    ("Логика и объяснения", "logika"),
]

ACHIEVEMENTS = [
    ("Первый шаг", 1, "🥉"),
    ("Новичок", 5, "🥈"),
    ("Переводчик", 10, "🥇"),
    ("Опытный", 25, "💎"),
    ("Мастер", 50, "🏆"),
    ("Легенда", 100, "👑"),
]

class Command(BaseCommand):
    help = "Seed initial data: Categories, Alliances, Districts, Achievements."

    @transaction.atomic
    def handle(self, *args, **options):
        # 1. Categories
        for name, slug in CATEGORIES:
            Category.objects.get_or_create(slug=slug, defaults={"name": name})
        self.stdout.write(self.style.SUCCESS("Categories created."))

        # 2. Alliances & Districts
        for alliance_name, data in ALLIANCES.items():
            alliance, _ = Alliance.objects.get_or_create(
                name=alliance_name, 
                defaults={"color": data["color"]}
            )
            for dist_name in data["districts"]:
                District.objects.get_or_create(name=dist_name, defaults={"alliance": alliance})
        self.stdout.write(self.style.SUCCESS("Alliances and Districts created."))

        # 3. Achievements
        for name, threshold, icon in ACHIEVEMENTS:
            Achievement.objects.get_or_create(
                threshold=threshold, 
                defaults={"name": name, "icon": icon}
            )
        self.stdout.write(self.style.SUCCESS("Achievements created."))
