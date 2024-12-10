from rest_framework import serializers
from app.models import Conversation


class MessageSerializer(serializers.ModelSerializer):

  class Meta:
    model = Conversation
    fields = ['id', 'sender', 'content', 'date_created']
