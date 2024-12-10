from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Fixed regex pattern - more permissive for the model parameter
    re_path(r'ws/api/chat/(?P<user_id>\d+)/(?P<model>[\w-]+)/?$',
            consumers.ChatConsumer.as_asgi()),
]
