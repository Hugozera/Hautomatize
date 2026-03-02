import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from core.models import ChatMessage, ChatPresence, ConversationMessage, Conversation, ConversationParticipant, Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def _display_name(user):
    if not user:
        return 'Anônimo'
    return (user.get_full_name() or user.username or 'Anônimo').strip()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        # If this is a conversation room, ensure the connecting user is a participant
        try:
            if self.room_name.startswith('conv-'):
                conv_id = int(self.room_name.split('-')[1])
                user_id = None
                if self.scope.get('user') and getattr(self.scope['user'], 'is_authenticated', False):
                    user_id = self.scope['user'].id
                allowed = await sync_to_async(lambda: ConversationParticipant.objects.filter(conversation_id=conv_id, user_id=user_id).exists())()
                if not allowed:
                    await self.close()
                    return
        except Exception:
            # if anything goes wrong, refuse the connection
            await self.close()
            return
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        # mark presence and notify group
        await self.set_presence(True)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'presence_update',
            }
        )
        # send recent messages and presence list
        await self.send_recent_messages()
        await self.send_presence_list()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        await self.set_presence(False)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'presence_update',
            }
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        user_obj = self.scope.get('user')
        user = _display_name(user_obj) if getattr(user_obj, 'is_authenticated', False) else 'Anônimo'

        # call signaling relay
        if data.get('action') in ('call_offer', 'call_answer', 'call_ice', 'call_end'):
            await self.channel_layer.group_send(self.room_group_name, {
                'type': 'call_signal',
                'action': data.get('action'),
                'from_user': user,
                'data': data.get('data') or {},
            })
            return

        # typing indicator
        if data.get('action') == 'typing':
            typing = bool(data.get('typing'))
            await self.channel_layer.group_send(self.room_group_name, {'type': 'typing_event', 'user': user, 'typing': typing})
            return

        # normal message flow
        message = data.get('message')
        if message is None:
            return
        attachments = data.get('attachments') if isinstance(data.get('attachments'), list) else []
        # persist message and get created timestamp
        created_iso = None
        if self.room_name.startswith('conv-'):
            conv_id = int(self.room_name.split('-')[1])
            created_iso = await self.save_conversation_message(conv_id, message, attachments)
        else:
            created_iso = await self.save_message(message)
        payload = {
            'type': 'chat_message',
            'message': message,
            'user': user,
            'created': created_iso,
            'attachments': attachments,
        }
        if self.room_name.startswith('conv-'):
            try:
                payload['conversation_id'] = int(self.room_name.split('-')[1])
            except Exception:
                pass
        # include client id if provided to allow deduplication on clients
        if isinstance(data, dict) and data.get('cid'):
            payload['cid'] = data.get('cid')

        await self.channel_layer.group_send(self.room_group_name, payload)

    async def send_recent_messages(self, limit=50):
        try:
            if self.room_name.startswith('conv-'):
                conv_id = int(self.room_name.split('-')[1])
                msgs = await sync_to_async(list)(ConversationMessage.objects.filter(conversation_id=conv_id).order_by('-criado_em')[:limit])
            else:
                msgs = await sync_to_async(list)(ChatMessage.objects.filter(atendimento_id=self.room_name).order_by('-criado_em')[:limit])
            # reverse to chronological
            msgs = list(reversed(msgs))
            for m in msgs:
                await self.send(text_data=json.dumps({'type': 'message', 'message': m.message, 'user': _display_name(m.user), 'created': m.criado_em.isoformat(), 'attachments': (m.attachments if hasattr(m, 'attachments') else [])}))
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

    @sync_to_async
    def save_conversation_message(self, conv_id, message_text, attachments=None):
        try:
            user = self.scope['user'] if self.scope.get('user') and self.scope['user'].is_authenticated else None
            obj = ConversationMessage.objects.create(conversation_id=conv_id, message=message_text, user=user, attachments=(attachments or []))
            try:
                Conversation.objects.filter(pk=conv_id).update(atualizado_em=obj.criado_em)
            except Exception:
                pass
            # notify participants via user-specific groups
            try:
                channel_layer = get_channel_layer()
                participants = ConversationParticipant.objects.filter(conversation_id=conv_id)
                payload = {
                    'type': 'chat_message',
                    'message': message_text,
                    'user': _display_name(user),
                    'created': obj.criado_em.isoformat(),
                    'conversation_id': conv_id,
                    'attachments': (attachments or []),
                }
                # persist a Notification for each participant (except sender) and attempt immediate group_send
                for p in participants:
                    if p.user:
                        if user and p.user.id == user.id:
                            continue
                        # create persistent notification
                        try:
                            Notification.objects.create(user=p.user, payload=payload)
                        except Exception:
                            pass
                        group_name = f'chat_user-{p.user.id}'
                        try:
                            async_to_sync(channel_layer.group_send)(group_name, payload)
                        except Exception:
                            # ignore delivery errors; notifier will send pending notifications on connect
                            pass
            except Exception:
                pass
            return obj.criado_em.isoformat()
        except Exception:
            return None

    @sync_to_async
    def set_presence(self, active=True):
        try:
            user = self.scope.get('user') if self.scope.get('user') and self.scope['user'].is_authenticated else None
            # create or update presence
            if user:
                obj, _ = ChatPresence.objects.update_or_create(atendimento_id=self.room_name, user=user, defaults={'active': bool(active)})
            else:
                # anonymous connections are ignored for presence tracking
                pass
        except Exception:
            pass

    @sync_to_async
    def get_active_presences(self):
        try:
            qs = ChatPresence.objects.filter(atendimento_id=self.room_name, active=True)
            return [{'id': p.user.id, 'username': p.user.get_username()} for p in qs if p.user]
        except Exception:
            return []

    async def send_presence_list(self):
        pres = await self.get_active_presences()
        await self.send(text_data=json.dumps({'type': 'presence', 'users': pres}))

    async def chat_message(self, event):
        payload = {'type': 'message', 'message': event['message'], 'user': event['user']}
        if 'created' in event:
            payload['created'] = event['created']
        if 'conversation_id' in event:
            payload['conversation_id'] = event['conversation_id']
        if 'cid' in event:
            payload['cid'] = event['cid']
        if 'attachments' in event:
            payload['attachments'] = event['attachments']
        await self.send(text_data=json.dumps(payload))

    async def call_signal(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call',
            'action': event.get('action'),
            'from': event.get('from_user'),
            'data': event.get('data') or {},
        }))

    async def typing_event(self, event):
        await self.send(text_data=json.dumps({'type': 'typing', 'user': event.get('user'), 'typing': event.get('typing', False)}))

    async def presence_update(self, event):
        # broadcast updated presence list to connected client
        await self.send_presence_list()
