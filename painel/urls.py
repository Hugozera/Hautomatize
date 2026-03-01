from django.urls import path
from core.painel_views import (
    PainelDepartamentoView,
    AtendimentoAnalistaView,
    RelatorioGestorView,
    ChatAtendimentoView,
    ClienteAtendimentosView,
    ToggleDisponibilidadeView,
    MeuPainelView,
    PuxarProximoView,
    PainelTVView,
    PainelTVIndexView,
    SecretariaPainelView,
    TransferAtendimentoView,
    AtendimentoAnexoUploadView,
)
from core import views as core_views
from core.views import painel_department_api

app_name = 'painel'

urlpatterns = [
    path('', MeuPainelView.as_view(), name='index'),
    path('puxar_proximo/', PuxarProximoView.as_view(), name='puxar_proximo'),
    path('painel/<int:departamento_id>/', PainelDepartamentoView.as_view(), name='painel_departamento'),
    path('atendimento/<int:atendimento_id>/', AtendimentoAnalistaView.as_view(), name='atendimento_analista'),
    path('relatorio/', RelatorioGestorView.as_view(), name='relatorio_gestor'),
    path('chat/<int:atendimento_id>/', ChatAtendimentoView.as_view(), name='chat_atendimento'),
    path('cliente/', ClienteAtendimentosView.as_view(), name='cliente_atendimentos'),
    path('analista/toggle_disponibilidade/', ToggleDisponibilidadeView.as_view(), name='toggle_disponibilidade'),
    path('departamentos/', core_views.departamento_list, name='departamento_list'),
    path('departamentos/novo/', core_views.departamento_create, name='departamento_create'),
    path('departamentos/<int:pk>/editar/', core_views.departamento_edit, name='departamento_edit'),
    path('tv/<int:departamento_id>/', PainelTVView.as_view(), name='painel_tv'),
    path('tv/', PainelTVIndexView.as_view(), name='tv_index'),
    path('secretaria/', SecretariaPainelView.as_view(), name='secretaria_painel'),
    path('atendimento/transfer/', TransferAtendimentoView.as_view(), name='transfer_atendimento'),
    path('api/department/<int:departamento_id>/', painel_department_api, name='painel_api_department'),
    path('anexo/upload/', AtendimentoAnexoUploadView.as_view(), name='atendimento_anexo_upload'),
]
