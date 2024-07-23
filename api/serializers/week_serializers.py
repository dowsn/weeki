from rest_framework import serializers
from app.models import Week


class WeekSerializer(serializers.ModelSerializer):

  class Meta:
    model = Week
    fields = ('id', 'value')
