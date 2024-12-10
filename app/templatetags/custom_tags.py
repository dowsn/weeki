from django import template
from django.urls import resolve
from django.templatetags.static import static
from django.utils.safestring import mark_safe
from django.conf import settings
import os

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


@register.simple_tag
def svg_include(filename):
  # Get the static URL
  static_url = static(f'svgs/{filename}')

  # Remove the STATIC_URL prefix to get the relative path
  relative_path = static_url.replace(settings.STATIC_URL, '')

  # Check in STATICFILES_DIRS
  for static_dir in settings.STATICFILES_DIRS:
    file_path = os.path.join(static_dir, relative_path)
    try:
      with open(file_path, 'r') as svg_file:
        svg_content = svg_file.read()
      return mark_safe(svg_content)
    except (FileNotFoundError, IOError):
      continue

  return f'SVG file {filename} not found'
