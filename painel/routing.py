from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.urls import re_path
from django.core.asgi import get_asgi_application

from core.consumers.chat_consumer import ChatConsumer
from core.consumers.painel_consumer import PainelDepartamentoConsumer
from core.consumers.user_notifier_consumer import UserNotifierConsumer

# WebSocket URL patterns exported so ASGI app can include HTTP + WS
websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<room_name>[^/]+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/atendimento/(?P<room_name>[^/]+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/chat/user-(?P<user_id>\d+)/$', UserNotifierConsumer.as_asgi()),
    re_path(r'ws/painel/(?P<departamento_id>\d+)/$', PainelDepartamentoConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
})
