import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings")

# Import Django settings first
from django.conf import settings
if not settings.configured:
  from django.core.wsgi import get_wsgi_application
  get_wsgi_application()

# Then import the rest
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application
import api.routing

# app.routing.websocket_urlpatterns
# Combine the websocket_urlpatterns
combined_patterns = api.routing.websocket_urlpatterns

application = ProtocolTypeRouter({
    "http":
    get_asgi_application(),
    "websocket":
    AuthMiddlewareStack(URLRouter(combined_patterns)),
})
