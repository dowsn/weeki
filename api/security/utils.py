from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
import base64
import json
from datetime import datetime


class TokenManager:

  @staticmethod
  def create_tokens(user):
    try:
      refresh = RefreshToken.for_user(user)
      return {'refresh': str(refresh), 'access': str(refresh.access_token)}
    except Exception as e:
      print(f"Error creating tokens: {str(e)}")
      raise
