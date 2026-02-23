from django.urls import path
from django.contrib.auth import views as auth_views
from . import upload_router
from . import upload_router
from . import views
from . import views_conversor

urlpatterns = [
    # Home / inicial
    path('', views.home, name='home'),
    # Dashboard statistics
    path('dashboard/', views.dashboard, name='dashboard'),
    
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
    path('upload/', upload_router.upload_router, name='upload_router'),    path('conversor/processar/<int:conversao_id>/', views_conversor.processar_conversao, name='processar_conversao'),
    path('conversor/status/<int:conversao_id>/', views_conversor.status_conversao, name='status_conversao'),
    path('conversor/historico/', views_conversor.historico_conversoes, name='historico_conversoes'),
    path('conversor/download/<int:conversao_id>/', views_conversor.download_arquivo, name='download_arquivo'),
    path('conversor/formatos/', views_conversor.info_formatos, name='info_formatos'),
   
    # Autenticação
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
]