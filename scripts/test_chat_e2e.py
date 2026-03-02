#!/usr/bin/env python3
import os
import sys
import django
import asyncio

# ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from channels.testing import WebsocketCommunicator
from core.consumers.chat_consumer import ChatConsumer
from channels.routing import URLRouter
from django.urls import re_path
from django.contrib.auth import get_user_model
from core.models import Conversation, ConversationParticipant, ConversationMessage, Notification

User = get_user_model()
from asgiref.sync import sync_to_async

async def run_test():
    # create test users
    u1, _ = await sync_to_async(User.objects.get_or_create)(username='test_user_1')
    u2, _ = await sync_to_async(User.objects.get_or_create)(username='test_user_2')
    # ensure passwords saved via sync
    await sync_to_async(u1.set_password)('pass'); await sync_to_async(u1.save)()
    await sync_to_async(u2.set_password)('pass'); await sync_to_async(u2.save)()

    # create conversation
    conv = await sync_to_async(Conversation.objects.create)(title='E2E Test')
    await sync_to_async(ConversationParticipant.objects.get_or_create)(conversation=conv, user=u1)
    await sync_to_async(ConversationParticipant.objects.get_or_create)(conversation=conv, user=u2)

    app = URLRouter([
        re_path(r'ws/chat/(?P<room_name>[^/]+)/$', ChatConsumer.as_asgi()),
    ])

    comm1 = WebsocketCommunicator(app, f"/ws/chat/conv-{conv.id}/")
    comm1.scope['user'] = u1

    comm2 = WebsocketCommunicator(app, f"/ws/chat/conv-{conv.id}/")
    comm2.scope['user'] = u2

    connected1, _ = await comm1.connect()
    connected2, _ = await comm2.connect()
    print('connected1', connected1, 'connected2', connected2)

    async def drain(name, comm, seconds=1.5):
        out = []
        end = asyncio.get_event_loop().time() + seconds
        while asyncio.get_event_loop().time() < end:
            try:
                item = await comm.receive_json_from(timeout=0.3)
                out.append(item)
            except BaseException:
                await asyncio.sleep(0.05)
        print(name, 'events:', out)
        return out

    await drain('comm1 initial', comm1, 1.0)
    await drain('comm2 initial', comm2, 1.0)

    # send a message from comm1
    payload = { 'type': 'message', 'message': 'Hello from u1', 'cid': 'testcid1' }
    await comm1.send_json_to(payload)

    ev2 = await drain('comm2 post-send', comm2, 2.0)
    ev1 = await drain('comm1 post-send', comm1, 2.0)
    got2 = any((e.get('type') == 'message' and e.get('message') == 'Hello from u1') for e in ev2)
    got1 = any((e.get('type') == 'message' and e.get('message') == 'Hello from u1') for e in ev1)
    print('comm2 got message?', got2)
    print('comm1 got echo?', got1)

    # check DB persisted
    all_msgs = await sync_to_async(list)(ConversationMessage.objects.all())
    print('DB total messages count:', len(all_msgs))
    msgs = await sync_to_async(list)(ConversationMessage.objects.filter(conversation_id=conv.id))
    print('DB messages for conv id', conv.id, 'count:', len(msgs))
    for mm in msgs:
        print('DB:', mm.user_id, mm.message, mm.criado_em)

    # check notifications for u2
    notes = await sync_to_async(list)(Notification.objects.filter(user=u2))
    print('Notifications for u2:', len(notes))

    # cleanup communicators
    await comm1.disconnect()
    await comm2.disconnect()

if __name__ == '__main__':
    asyncio.run(run_test())
