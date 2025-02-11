from rest_framework import serializers
from app.models import Profile


class UserSerializer(serializers.ModelSerializer):
  userId = serializers.SerializerMethodField()
  username = serializers.SerializerMethodField()

  class Meta:
    model = Profile
    fields = ['userId', 'username', 'email', 'reminder', 'activated']

  def get_userId(self, obj):
    return obj.user.id

  def get_username(self, obj):
    return obj.user.username
