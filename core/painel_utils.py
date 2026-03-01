from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def notificar_painel_departamento(departamento_id):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'panel_{departamento_id}',
        {'type': 'painel_update'}
    )
