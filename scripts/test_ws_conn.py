import asyncio
import websockets

async def main():
    uri = 'ws://127.0.0.1:8765/ws/chat/user-1/'
    try:
        async with websockets.connect(uri) as ws:
            print('connected')
    except Exception as e:
        print('err', type(e).__name__, e)

asyncio.run(main())
