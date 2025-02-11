from rest_framework import serializers
from app.models import Chat_Session


class Chat_SessionSerializer(serializers.ModelSerializer):

  class Meta:
    model = Chat_Session
    fields = ('id', 'date', 'time_left', 'title', 'summary')

  def get_date(self, obj):
    return obj.date.strftime('%Y-%m-%d')
