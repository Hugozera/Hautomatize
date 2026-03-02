import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from core.models import Notification

class UserNotifierConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user_id = self.scope['url_route']['kwargs'].get('user_id')
        # require authenticated user matching the requested id
        if not self.scope.get('user') or not getattr(self.scope['user'], 'is_authenticated', False):
            await self.close()
            return
        if str(self.scope['user'].id) != str(user_id):
            await self.close()
            return
        self.group_name = f'chat_user-{user_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        # Deliver any pending notifications stored while user was offline
        try:
            user = self.scope.get('user')
            if user and getattr(user, 'is_authenticated', False):
                pending = await sync_to_async(list)(Notification.objects.filter(user=user, delivered=False).order_by('created'))
                for n in pending:
                    try:
                        await self.send(text_data=json.dumps(n.payload))
                        # mark delivered
                        n.delivered = True
                        n.save()
                    except Exception:
                        # if sending fails, keep it for next time
                        pass
        except Exception:
            pass

    async def disconnect(self, close_code):
        try:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)
        except Exception:
            pass

    async def receive(self, text_data):
        # notifier is read-only from client side; ignore received messages
        return

    async def chat_message(self, event):
        # forward event payload directly to client
        try:
            await self.send(text_data=json.dumps(event))
        except Exception:
            pass
