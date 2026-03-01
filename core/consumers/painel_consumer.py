import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from core.models import Departamento, Analista, Atendimento

class PainelDepartamentoConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.departamento_id = self.scope['url_route']['kwargs']['departamento_id']
        self.group_name = f'panel_{self.departamento_id}'
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_panel_data()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    async def painel_update(self, event):
        await self.send_panel_data()

    async def send_panel_data(self):
        analistas_qs = await sync_to_async(list)(Analista.objects.filter(departamento_id=self.departamento_id))
        atendimentos_pendentes_qs = await sync_to_async(list)(Atendimento.objects.filter(departamento_id=self.departamento_id, status='pendente').order_by('criado_em'))
        atendimentos_andamento_qs = await sync_to_async(list)(Atendimento.objects.filter(departamento_id=self.departamento_id, status='atendendo').order_by('iniciado_em'))
        data = {
            'analistas': [
                {
                    'id': a.id,
                    'name': str(a),
                    'disponivel': bool(a.disponivel),
                    'disponivel_em': a.disponivel_em.isoformat() if getattr(a, 'disponivel_em', None) else None,
                } for a in analistas_qs
            ],
            'atendimentos_pendentes': [
                {
                    'id': at.id,
                    'empresa': at.empresa,
                    'criado_em': at.criado_em.isoformat() if at.criado_em else None,
                } for at in atendimentos_pendentes_qs
            ],
            'atendimentos_andamento': [
                {
                    'id': at.id,
                    'analista': str(at.analista) if at.analista else None,
                    'empresa': at.empresa,
                    'iniciado_em': at.iniciado_em.isoformat() if at.iniciado_em else None,
                } for at in atendimentos_andamento_qs
            ],
        }
        await self.send(text_data=json.dumps(data))
