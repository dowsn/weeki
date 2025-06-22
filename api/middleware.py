from django.http import HttpResponseForbidden, JsonResponse
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from django.utils.deprecation import MiddlewareMixin
from app.models import Profile
import json
import logging

logger = logging.getLogger(__name__)


class SecurityMiddleware(MiddlewareMixin):

  def _get_request_data(self, request):
    """Safely get data from request regardless of method"""
    if request.method == 'GET':
      return request.GET
    if request.method == 'POST':
      try:
        return json.loads(request.body.decode('utf-8'))
      except json.JSONDecodeError:
        return request.POST
    return {}

  def process_request(self, request):
    # Skip security for token refresh and login endpoints
    EXEMPT_PATHS = [
        # '/api',
        '/api/token/refresh/',
        '/api/send_activation_code',
        '/api/activate_profile',
        '/api/reset_password',
        '/api/google-play-webhook/',
        '/api/login',
        '/api/model_test',
        '/api/test_mail',
        '/api/cron_reminder',
        '/static/fonts/VarelaRound-Regular.woff',
        '/api/register',
        '/admin',
        '/media/',
        '/static/',
    ]

    if any(request.path.startswith(path) for path in EXEMPT_PATHS):
      return None

    try:
      # Get Authorization header
      auth_header = request.headers.get('Authorization')
      if not auth_header or not auth_header.startswith('Bearer '):
        return JsonResponse({'error': 'Authentication required'}, status=401)

      # Validate token
      token = auth_header.split(' ')[1]
      try:
        token_obj = AccessToken(token)
        user_id = token_obj['user_id']

        # Instead of checking request_user_id, attach the user object to request
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
          user = User.objects.get(id=user_id)
          request.user = user
          request.user_id = user_id
          # You can also attach the profile if needed
          # request.profile = user.profile
          request.profile = Profile.objects.get(user=user)
        except User.DoesNotExist:
          return JsonResponse({'error': 'User not found'}, status=404)

      except TokenError as e:
        return JsonResponse({'error': str(e)}, status=401)
    except Exception as e:
      logger.error(f"Token validation error: {str(e)}")
      return JsonResponse({'error': 'Invalid token'}, status=401)

    return None
