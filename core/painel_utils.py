from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.models import Atendimento

def notificar_painel_departamento(departamento_id):
    """Send a simple trigger to the painel WebSocket group for this department.

    Consumers will fetch fresh data from the DB when they receive this event.
    """
    channel_layer = get_channel_layer()
    group = f'panel_{departamento_id}'
    try:
        async_to_sync(channel_layer.group_send)(
            group,
            {
                'type': 'painel_update',
            }
        )
    except Exception:
        # Avoid raising in web request flow if channels isn't configured
        pass