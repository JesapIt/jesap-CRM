from django import template

register = template.Library()

@register.filter
def format_username(value):
    """
    Formata o username substituindo pontos e underscores por espaços
    e aplicando Title Case.
    Ex: 'daniele.tegliucci' -> 'Daniele Tegliucci'
    """
    if not value:
        return value
    # Substituir . e _ por espaço
    formatted = value.replace('.', ' ').replace('_', ' ')
    # Aplicar Title Case
    return formatted.title()