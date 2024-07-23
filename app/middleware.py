from .models import Profile

from django.contrib.auth.decorators import login_required
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.conf import settings

class AppLoginRequiredMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        # Check if the view is part of the 'app' application
        resolved = resolve(request.path)
        if resolved.app_name == 'app':
            if not request.user.is_authenticated:
                return redirect(settings.LOGIN_URL + f'?next={request.path}')
        return None

class AppMiddleWare:

  def __init__(self, get_response):
    self.get_response = get_response

  def __call__(self, request):
    request.profile = None
    if hasattr(request, 'user') and request.user.is_authenticated:
      try:
        user = request.user
        request.profile = Profile.get_user_profile(user.id)
      except Profile.DoesNotExist:
        pass

    response = self.get_response(request)
    return response
