import os
import django
import asyncio
import json
import sys

# Ensure project root is on sys.path so Django settings module can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from channels.testing import ApplicationCommunicator
from core.consumers.user_notifier_consumer import UserNotifierConsumer
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
User = get_user_model()
# create a test user (will persist in DB)
user, created = User.objects.get_or_create(username='ws_test_user', defaults={'email':'ws@test.local'})
if created:
    user.set_password('testpass')
    user.save()
uid = user.id


async def main():

    app = UserNotifierConsumer.as_asgi()
    scope = {
        'type': 'websocket',
        'path': f'/ws/chat/user-{uid}/',
        'user': user,
        'url_route': {'kwargs': {'user_id': str(uid)}},
        'headers': []
    }

    comm = ApplicationCommunicator(app, scope)
    # initiate connection
    await comm.send_input({'type': 'websocket.connect'})
    # allow a tick for group_add
    await asyncio.sleep(0.1)

    channel_layer = get_channel_layer()
    # send a group message that should be forwarded to the consumer
    await channel_layer.group_send(f'chat_user-{uid}', {
        'type': 'chat_message',
        'message': 'hello from test',
        'user': 'sender',
        'created': 'now',
        'conversation_id': 123,
    })

    try:
        # read up to a few outputs and look for the send containing our message
        for _ in range(5):
            out = await comm.receive_output(timeout=5)
            print('RECEIVED:', out)
            if out.get('type') == 'websocket.send':
                txt = out.get('text') or out.get('bytes')
                print('TEXT:', txt)
                break
    except Exception as e:
        print('No message received:', e)

    # disconnect
    await comm.send_input({'type': 'websocket.disconnect', 'code': 1000})
    await comm.wait()

if __name__ == '__main__':
    asyncio.run(main())
