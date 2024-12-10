from .models import Profile

from django.contrib.auth.decorators import login_required
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect

from django.utils import translation
from django.conf import settings


class ProfileLanguageMiddleware:

  def __init__(self, get_response):
    self.get_response = get_response

  def __call__(self, request):
    request.profile = None
    if request.user.is_authenticated:
      try:
        request.profile = Profile.get_user_profile(request.user.id)
        request.language_code = getattr(request.profile.language, 'code',
                                        'EN_en')
        if request.profile and hasattr(request.profile.language, 'locale'):
          user_language = request.profile.language.locale
          translation.activate(user_language)
          request.LANGUAGE_CODE = user_language
        else:
          self._set_default_language(request)
      except Profile.DoesNotExist:
        self._set_default_language(request)
    else:
      self._set_default_language(request)

    response = self.get_response(request)

    # Deactivate the language for this thread to prevent leaking
    translation.deactivate()

    return response

  def _set_default_language(self, request):
    default_language = getattr(settings, 'LANGUAGE_CODE', 'en-us')
    translation.activate(default_language)
    request.LANGUAGE_CODE = default_language


class AppLoginRequiredMiddleware(MiddlewareMixin):

  def process_view(self, request, view_func, view_args, view_kwargs):
    # Check if the view is part of the 'app' application
    resolved = resolve(request.path)
    if resolved.app_name == 'app':
      if not request.user.is_authenticated and 'cron_job' not in request.path:
        return redirect(settings.LOGIN_URL + f'?next={request.path}')
    return None
