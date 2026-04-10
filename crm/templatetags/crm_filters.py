from django import template

register = template.Library()

@register.filter
def filter_status(queryset, status):
    """Фильтрует QuerySet по статусу"""
    return queryset.filter(status=status)