from rest_framework_simplejwt.authentication import JWTAuthentication


class CustomJWTAuthentication(JWTAuthentication):

  def authenticate(self, request):
    try:
      header = self.get_header(request)
      if header is None:
        return None

      raw_token = self.get_raw_token(header)
      if raw_token is None:
        return None

      validated_token = self.get_validated_token(raw_token)
      user = self.get_user(validated_token)

      # Add additional security checks
      if not user.is_active:
        return None

      # You could add rate limiting here

      return (user, validated_token)
    except Exception:
      return None
