from difflib import SequenceMatcher
from django import template
from django.utils.html import format_html, format_html_join

register = template.Library()

@register.simple_tag
def review_diff(text, reference):
    text, reference = text or "", reference or ""
    pieces = []
    for op, start, end, _, _ in SequenceMatcher(None, text, reference, autojunk=False).get_opcodes():
        if op == "equal":
            pieces.append(text[start:end])
        elif op in ("replace", "delete"):
            pieces.append(format_html('<mark class="review-difference">{}</mark>', text[start:end]))
    return format_html_join('', '{}', ((piece,) for piece in pieces))
