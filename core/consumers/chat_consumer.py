import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from core.models import ChatMessage

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        # send recent messages
        await self.send_recent_messages()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        user = self.scope['user'].username if self.scope['user'].is_authenticated else 'Anônimo'
        # persist message and get created timestamp
        created_iso = await self.save_message(message)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'user': user,
                'created': created_iso
            }
        )

    async def send_recent_messages(self, limit=50):
        try:
            msgs = await sync_to_async(list)(ChatMessage.objects.filter(atendimento_id=self.room_name).order_by('-criado_em')[:limit])
            # reverse to chronological
            msgs = list(reversed(msgs))
            for m in msgs:
                await self.send(text_data=json.dumps({'message': m.message, 'user': m.user.get_username() if m.user else 'Anônimo', 'created': m.criado_em.isoformat()}))
        except Exception:
            # ignore DB errors to keep socket alive
            pass

    @sync_to_async
    def save_message(self, message_text):
        try:
            user = self.scope['user'] if self.scope.get('user') and self.scope['user'].is_authenticated else None
            obj = ChatMessage.objects.create(atendimento_id=self.room_name, message=message_text, user=user)
            return obj.criado_em.isoformat()
        except Exception:
            return None

    async def chat_message(self, event):
        payload = {'message': event['message'], 'user': event['user']}
        if 'created' in event:
            payload['created'] = event['created']
        await self.send(text_data=json.dumps(payload))
