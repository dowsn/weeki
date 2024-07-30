from django import template
from django.urls import resolve

register = template.Library()


@register.filter
def replace_spaces_and_decimals(value):
  return str(value).replace(',', '').replace('.', '').replace(' ', '')


@register.filter
def replace_comma_with_dot(value):
  return str(value).replace(',', '.')


@register.simple_tag(takes_context=True)
def active(context, *words):
  request = context['request']
  path = request.path_info.lstrip('/')
  path_parts = path.split('/')

  for word in words:
    if word == 'week':
      # Check if 'week' is an exact match or the start of a path part
      # but not if it's part of 'weeki'
      if any(part == 'week' or (
          part.startswith('week') and not part.startswith('weeki'))
             for part in path_parts):
        return "active"
    elif word == 'weeki':
      # Exact match for 'weeki'
      if 'weeki' in path_parts:
        return "active"
    else:
      # For other words, check if they are in any part of the path
      if any(word in part for part in path_parts):
        return "active"

  return ""
