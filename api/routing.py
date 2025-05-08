from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Fixed regex pattern - more permissive for the model parameter
    re_path(r'ws/api/chat/(?P<chat_session>[\w-]+)/?$',
            consumers.ChatConsumer.as_asgi()),
    # re_path(r'ws/api/chat/(?P<user_id>\d+)/(?P<chat_session>[\w-]+)/?$',
    #         consumers.ChatConsumer.as_asgi()),
]
