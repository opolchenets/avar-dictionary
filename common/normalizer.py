"""
Нормализация аварского текста и сравнение строк.

fix_palochka  — привести все варианты палочки к Ӏ (U+04C0), только после кириллической буквы,
                чтобы не трогать цифры и латиницу («1990» и «Ilya» останутся как есть).
normalize     — вид для сравнения: палочка, без регистра, «ё»→«е», без пунктуации и лишних пробелов.
char_errors   — число посимвольных ошибок (расстояние Левенштейна) между нормализованными строками.
similarity    — доля совпадения 0…1 (difflib), для информации.
"""
import difflib
import re

from .constants import PAL, PAL_LOOKALIKES

_PAL_RE = re.compile(r"(?<=[А-Яа-яЁё])[" + re.escape(PAL_LOOKALIKES) + r"|]")


def fix_palochka(text: str) -> str:
    return _PAL_RE.sub(PAL, text or "")


def normalize(text: str) -> str:
    t = fix_palochka(text).lower().replace("ё", "е").replace(PAL.lower(), PAL)
    t = re.sub(r"[^\w\s" + PAL + r"-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def char_errors(a: str, b: str) -> int:
    a, b = normalize(a), normalize(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()
