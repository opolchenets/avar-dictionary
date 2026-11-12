from difflib import SequenceMatcher
from django import template
from django.utils.html import format_html, format_html_join
from common.normalizer import fix_palochka

register = template.Library()

@register.simple_tag
def review_diff(text, reference):
    text, reference = text or "", reference or ""
    a, b = fix_palochka(text).casefold(), fix_palochka(reference).casefold()
    positions = list(range(len(text)))
    marked, missing = set(), set()
    for op, i, j, x, y in SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            marked.update(positions[i:j])
        if op == "insert":
            missing.add(positions[i] if i < len(positions) else len(text))
    pieces = []
    for i in range(len(text) + 1):
        if i in missing:
            pieces.append(format_html('<mark class="review-difference" title="Здесь пропущен текст">[пропуск]</mark>'))
        if i < len(text):
            visible = '·' if text[i] == ' ' and i in marked else text[i]
            pieces.append(format_html('<mark class="review-difference" title="Различие, включая пробелы">{}</mark>', visible) if i in marked else format_html('{}', text[i]))
    return format_html_join('', '{}', ((piece,) for piece in pieces))
