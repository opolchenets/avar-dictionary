import difflib
from django import template
from django.utils.safestring import mark_safe, SafeString
from django.utils.html import escape

register = template.Library()

@register.filter
def highlight_diff(original: str, revised: str) -> SafeString:
    if not original:
        return mark_safe(f'<ins style="color: var(--success); text-decoration: none; background: rgba(40, 167, 69, 0.1);">{escape(revised)}</ins>')
    if not revised:
        return mark_safe(f'<del style="color: var(--danger); text-decoration: line-through; background: rgba(220, 53, 69, 0.1);">{escape(original)}</del>')

    # Use SequenceMatcher to find differences between words or characters
    # Character-level diff for precision in edits
    s = difflib.SequenceMatcher(None, original, revised)
    output = []
    
    for opcode, a0, a1, b0, b1 in s.get_opcodes():
        if opcode == 'equal':
            output.append(escape(original[a0:a1]))
        elif opcode == 'insert':
            output.append(f'<ins style="color: var(--success); text-decoration: none; background: rgba(40, 167, 69, 0.1);">{escape(revised[b0:b1])}</ins>')
        elif opcode == 'delete':
            output.append(f'<del style="color: var(--danger); text-decoration: line-through; background: rgba(220, 53, 69, 0.1);">{escape(original[a0:a1])}</del>')
        elif opcode == 'replace':
            output.append(f'<del style="color: var(--danger); text-decoration: line-through; background: rgba(220, 53, 69, 0.1);">{escape(original[a0:a1])}</del>')
            output.append(f'<ins style="color: var(--success); text-decoration: none; background: rgba(40, 167, 69, 0.1);">{escape(revised[b0:b1])}</ins>')
            
    return mark_safe("".join(output))
