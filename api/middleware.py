from django.http import HttpResponseForbidden, JsonResponse
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from django.utils.deprecation import MiddlewareMixin
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

      # Get user ID from request
      request_data = self._get_request_data(request)
      request_user_id = request_data.get('userId')

      # Validate token
      token = auth_header.split(' ')[1]
      print("request token")
      print(token)
      try:
        token_obj = AccessToken(token)
        token_user_id = token_obj['user_id']

        # Verify user matches token if userId is in request
        if request_user_id and str(request_user_id) != str(token_user_id):
          return JsonResponse({'error': 'Unauthorized access'}, status=403)

        # Add token data to request for views
        request.token_data = {'user_id': token_user_id}

      except TokenError as e:
        return JsonResponse({'error': str(e)}, status=401)

    except Exception as e:
      logger.error(f"Token validation error: {str(e)}")
      return JsonResponse({'error': 'Invalid token'}, status=401)

    return None
