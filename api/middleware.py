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
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            try:
                if request.content_type == 'application/json':
                    return json.loads(request.body.decode('utf-8'))
                else:
                    return request.POST
            except (json.JSONDecodeError, UnicodeDecodeError):
                return {}
        return {}

    def process_request(self, request):
        # Skip security for token refresh and login endpoints
        EXEMPT_PATHS = [
            '/api/token/refresh/',
            '/api/token/verify/',
            '/api/send_activation_code',
            '/api/activate_profile',
            '/api/reset_password',
            '/api/google-play-webhook/',
            '/api/login',
            '/api/model_test/',
            '/api/test_mail',
            '/api/cron_reminder',
            '/api/register',
            '/admin/',
            '/media/',
            '/static/',
        ]

        # More efficient path checking
        path = request.path
        if any(path.startswith(exempt_path) for exempt_path in EXEMPT_PATHS):
            logger.debug(f"Skipping auth for exempt path: {path}")
            return None

        # Special handling for OPTIONS requests (CORS preflight)
        if request.method == 'OPTIONS':
            return None

        try:
            # Get Authorization header
            auth_header = request.headers.get('Authorization')

            if not auth_header:
                logger.warning(f"No Authorization header for path: {path}")
                return JsonResponse({
                    'error': True,
                    'message': 'Authentication required',
                    'code': 'no_auth_header'
                }, status=401)

            if not auth_header.startswith('Bearer '):
                logger.warning(f"Invalid Authorization header format for path: {path}")
                return JsonResponse({
                    'error': True,
                    'message': 'Invalid authentication format',
                    'code': 'invalid_auth_format'
                }, status=401)

            # Validate token
            token = auth_header.split(' ')[1]

            try:
                # Validate the access token
                token_obj = AccessToken(token)
                user_id = token_obj['user_id']

                # Check if token is about to expire (within 5 minutes)
                from datetime import datetime, timedelta
                exp_timestamp = token_obj['exp']
                exp_datetime = datetime.fromtimestamp(exp_timestamp)
                time_until_expiry = exp_datetime - datetime.now()

                if time_until_expiry < timedelta(minutes=5):
                    logger.info(f"Token expiring soon for user {user_id}")

                # Get user and attach to request
                from django.contrib.auth import get_user_model
                User = get_user_model()

                try:
                    user = User.objects.select_related('profile').get(id=user_id)
                    request.user = user
                    request.user_id = user_id

                    # Attach profile if it exists
                    if hasattr(user, 'profile'):
                        request.profile = user.profile
                    else:
                        # Create profile if it doesn't exist
                        profile = Profile.objects.create(user=user)
                        request.profile = profile
                        logger.warning(f"Created missing profile for user {user_id}")

                    logger.debug(f"Authenticated user {user_id} for path: {path}")

                except User.DoesNotExist:
                    logger.error(f"User {user_id} from token not found in database")
                    return JsonResponse({
                        'error': True,
                        'message': 'User not found',
                        'code': 'user_not_found'
                    }, status=404)

            except TokenError as e:
                error_str = str(e)
                logger.warning(f"Token validation failed for path {path}: {error_str}")

                # Provide specific error messages
                if "Token is invalid or expired" in error_str:
                    return JsonResponse({
                        'error': True,
                        'message': 'Access token has expired',
                        'code': 'token_expired',
                        'detail': error_str
                    }, status=401)
                elif "Token is blacklisted" in error_str:
                    return JsonResponse({
                        'error': True,
                        'message': 'Token has been revoked',
                        'code': 'token_blacklisted',
                        'detail': error_str
                    }, status=401)
                else:
                    return JsonResponse({
                        'error': True,
                        'message': 'Invalid token',
                        'code': 'token_invalid',
                        'detail': error_str
                    }, status=401)

        except Exception as e:
            logger.error(f"Unexpected error in SecurityMiddleware: {str(e)}", exc_info=True)
            return JsonResponse({
                'error': True,
                'message': 'Authentication error',
                'code': 'auth_error',
                'detail': str(e) if settings.DEBUG else 'Internal error'
            }, status=500)

        return None