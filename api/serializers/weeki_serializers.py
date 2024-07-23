from rest_framework import serializers
from app.models import Weeki


class WeekiSerializer(serializers.ModelSerializer):

  class Meta:
    model = Weeki
    fields = ('id', 'content', 'category', 'user_id', 'week')
