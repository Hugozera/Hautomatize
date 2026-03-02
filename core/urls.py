from django.urls import path
from django.contrib.auth import views as auth_views

from .painel_views import RelatorioGestorView
from .painel_views import ChatIndexView
from core import views as core_views
from . import upload_router
from . import views
from . import views_conversor
from . import views as core_views
from django.urls import path
# legacy: chat_views import removed; use `ChatIndexView` and handlers from `views` / `core_views`

urlpatterns = [
    # Home / inicial
    path('', views.home, name='home'),
    # Dashboard statistics
    path('dashboard/', views.dashboard, name='dashboard'),
    # Chat module (standalone index)
    path('chat/', ChatIndexView.as_view(), name='chat_index'),
    path('chat/mark_read/', core_views.mark_conversation_read, name='chat_mark_read'),
    path('chat/my_conversations/', core_views.user_conversations, name='chat_my_conversations'),
    path('chat/create_user_conversation/', core_views.create_user_conversation, name='create_user_conversation'),
    path('chat/create_empresa_conversation/', core_views.create_empresa_conversation, name='create_empresa_conversation'),
    path('chat/create_group_conversation/', core_views.create_group_conversation, name='create_group_conversation'),
    path('chat/push_test/<int:user_id>/', core_views.push_test_notification, name='chat_push_test'),
    path('api/upload-attachments/', core_views.upload_attachments, name='upload_attachments'),
    path('api/messages/<str:room_id>/', core_views.api_messages, name='api_messages'),
    path('api/users/', core_views.api_users, name='api_users'),
    path('api/pessoas/', core_views.api_pessoas, name='api_pessoas'),
    
    # Pessoas (Usuários)
    path('pessoas/', views.pessoa_list, name='pessoa_list'),
    path('pessoas/nova/', views.pessoa_create, name='pessoa_create'),
    path('pessoas/<int:pk>/editar/', views.pessoa_edit, name='pessoa_edit'),
    
    # Empresas
    path('empresas/', views.empresa_list, name='empresa_list'),
    path('empresas/nova/', views.empresa_create, name='empresa_create'),
    path('empresas/novo-custom/', views.empresa_create_custom, name='empresa_create_custom'),
    path('empresas/<int:pk>/editar/', views.empresa_edit, name='empresa_edit'),
    path('empresas/<int:pk>/remover-certificado/', views.remover_certificado, name='remover_certificado'),
    path('empresas/<int:pk>/dashboard/', views.empresa_dashboard, name='empresa_dashboard'),
    path('empresas/buscar-cnpj/', views.buscar_cnpj, name='buscar_cnpj'),
    path('api/cep/', views.api_cep, name='api_cep'),
    path('empresas/buscar-certificado/', views.buscar_certificado, name='buscar_certificado'),
    path('empresas/certificado/', views.empresa_certificado, name='empresa_certificado'),
    
    # Agendamentos
    path('agendamentos/', views.agendamento_list, name='agendamento_list'),
    path('agendamentos/novo/', views.agendamento_create, name='agendamento_create'),
    path('agendamentos/<int:pk>/editar/', views.agendamento_edit, name='agendamento_edit'),
    
    # Download
    path('download/', views.download_manual, name='download_manual'),
    path('download/<int:historico_id>/', views.download_progress, name='download_progress'),
    
    # Configurações
    path('configuracao/', views.configuracao, name='configuracao'),
    path('perfil/', views.perfil, name='perfil'),
    path('perfil/generate-token/', views.generate_client_token, name='generate_client_token'),

    # Roles (somente superuser)
    path('roles/', views.role_list, name='role_list'),
    path('roles/nova/', views.role_create, name='role_create'),
    path('roles/<int:pk>/editar/', views.role_edit, name='role_edit'),
    path('roles/<int:pk>/excluir/', views.role_delete, name='role_delete'),
    
    
    # Certificados
    path('certificados/', views.certificado_list, name='certificado_list'),
    path('certificados/testar/', views.certificado_test, name='certificado_test'),
    path('certificados/salvar/', views.salvar_certificado, name='salvar_certificado'),
    path('certificados/info/', views.certificado_info, name='certificado_info'),
    path('certificados/<int:pk>/editar/', views.certificado_edit, name='certificado_edit'),
    path('certificados/<int:pk>/baixar/', views.certificado_download, name='certificado_download'),
    path('certificados/upload/', views.upload_certificado_temporario, name='upload_certificado'),
    path('empresas/api/search/', views.empresa_search, name='empresa_search'),

    # API para agente local
    path('api/agent/upload/', views.api_agent_upload, name='api_agent_upload'),
    
    # Progresso
    path('progresso/<int:tarefa_id>/', views.progresso, name='progresso'),
    
    # Histórico
    path('historico/', views.historico, name='historico'),
    path('download/progresso/<int:tarefa_id>/', views.progresso_download, name='progresso_download'),
    path('download/api/progresso/<int:tarefa_id>/', views.api_progresso_download, name='api_progresso_download'),
    path('download/lista/', views.listar_downloads, name='lista_downloads'),
    
 
    

    # Conversor de Arquivos
    path('conversor/', views_conversor.conversor_index, name='conversor_index'),
    path('sieg/', core_views.sieg_index, name='sieg_index'),
    path('sieg/call/', core_views.sieg_call, name='sieg_call'),
    path('sieg/certificados/', core_views.sieg_certificados, name='sieg_certificados'),
    path('sieg/empresas/', core_views.sieg_empresas, name='sieg_empresas'),
    path('sieg/downloads/', core_views.sieg_downloads, name='sieg_downloads'),
    path('sieg/endpoints/', core_views.sieg_endpoints, name='sieg_endpoints'),
    path('sieg/download/execute/', core_views.sieg_execute_download, name='sieg_execute_download'),
    path('sieg/tag/<slug:tag_slug>/', core_views.sieg_tag, name='sieg_tag'),
    path('upload/', upload_router.upload_router, name='upload_router'),    path('conversor/processar/<int:conversao_id>/', views_conversor.processar_conversao, name='processar_conversao'),
    path('conversor/status/<int:conversao_id>/', views_conversor.status_conversao, name='status_conversao'),
    path('conversor/progresso/<int:conversao_id>/', views_conversor.progresso_conversao, name='progresso_conversao'),
    path('conversor/historico/', views_conversor.historico_conversoes, name='historico_conversoes'),
    path('conversor/download/<int:conversao_id>/', views_conversor.download_arquivo, name='download_arquivo'),
    path('conversor/ver_ofx/<int:conversao_id>/', views_conversor.ver_ofx, name='ver_ofx'),
    path('conversor/original/<int:conversao_id>/', views_conversor.download_original, name='download_original'),
    path('conversor/salvar_ofx/<int:conversao_id>/', views_conversor.salvar_ofx_editado, name='salvar_ofx_editado'),
    path('conversor/salvar_transacoes/<int:conversao_id>/', views_conversor.salvar_transacoes_editadas, name='salvar_transacoes_editadas'),
    path('conversor/formatos/', views_conversor.info_formatos, name='info_formatos'),
    path('conversor/create_from_text/', views_conversor.create_ofx_from_text, name='create_ofx_from_text'),
    path('conversor/api/preview_from_text/', views_conversor.api_preview_from_text, name='api_preview_from_text'),
    path('conversor/api/generate_ofx/', views_conversor.api_generate_ofx, name='api_generate_ofx'),
   
    # Autenticação
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
]