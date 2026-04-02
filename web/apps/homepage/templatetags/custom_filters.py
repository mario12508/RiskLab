from django import template

register = template.Library()

@register.filter(name='split')
def split(value, key):
    """
    Разделяет строку по разделителю и возвращает список.
    Использование в шаблоне: {{ "a,b,c"|split:"," }}
    """
    return value.split(key)