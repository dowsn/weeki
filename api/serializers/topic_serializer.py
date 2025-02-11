from re import M
from rest_framework import serializers
from app.models import Topic


class TopicSerializer(serializers.ModelSerializer):

  class Meta:
    model = Topic
    fields = ('id', 'name', 'description', 'active', 'date_updated')
