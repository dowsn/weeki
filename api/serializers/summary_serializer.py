from rest_framework import serializers
from app.models import Summary


class SummarySerializer(serializers.ModelSerializer):

  class Meta:
    model = Summary
    fields = ('id', 'date', 'content')

  def get_date(self, obj):
    return obj.date.strftime('%Y-%m-%d')
