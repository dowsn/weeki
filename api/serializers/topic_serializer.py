from re import M
from rest_framework import serializers
from app.models import Topic, Meeting


class TopicSerializer(serializers.ModelSerializer):

  class Meta:
    model = Topic
    fields = ('id', 'name', 'image', 'description', 'active', 'ordering')


    