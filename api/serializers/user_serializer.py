from rest_framework import serializers
from app.models import Profile


class UserSerializer(serializers.ModelSerializer):
  userId = serializers.SerializerMethodField()
  username = serializers.SerializerMethodField()
  profileImage = serializers.SerializerMethodField()

  class Meta:
    model = Profile
    fields = [
        'userId', 'username', 'date_of_birth', 'final_age', 'profileImage',
        'sorting_descending'
    ]

  def get_userId(self, obj):
    return obj.user.id

  def get_username(self, obj):
    return obj.user.username

  def get_profileImage(self, obj):
    if obj.image:
      request = self.context.get('request')
      if request is not None:
        return request.build_absolute_uri(obj.image.url)
      return obj.image.url
    return None
