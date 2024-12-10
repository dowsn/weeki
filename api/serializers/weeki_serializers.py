from rest_framework import serializers
from app.models import Weeki


class WeekiSerializer(serializers.ModelSerializer):

  class Meta:
    model = Weeki
    fields = ('id', 'content', 'topic', 'user_id', 'week')
