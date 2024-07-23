from rest_framework import serializers
from app.models import Year


class YearSerializer(serializers.ModelSerializer):

  class Meta:
    model = Year
    fields = ('id', 'value')
