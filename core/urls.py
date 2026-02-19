from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Pessoas (Usuários)
    path('pessoas/', views.pessoa_list, name='pessoa_list'),
    path('pessoas/nova/', views.pessoa_create, name='pessoa_create'),
    path('pessoas/<int:pk>/editar/', views.pessoa_edit, name='pessoa_edit'),
    
    # Empresas
    path('empresas/', views.empresa_list, name='empresa_list'),
    path('empresas/nova/', views.empresa_create, name='empresa_create'),
    path('empresas/novo-custom/', views.empresa_create_custom, name='empresa_create_custom'),
    path('empresas/<int:pk>/editar/', views.empresa_edit, name='empresa_edit'),
    path('empresas/buscar-cnpj/', views.buscar_cnpj, name='buscar_cnpj'),
    path('empresas/buscar-certificado/', views.buscar_certificado, name='buscar_certificado'),
    # 👇 ADICIONADO - URL para importar via certificado da loja Windows
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
    
    # Certificados
    path('certificados/', views.certificado_list, name='certificado_list'),
    path('certificados/testar/', views.certificado_test, name='certificado_test'),
    path('certificados/salvar/', views.salvar_certificado, name='salvar_certificado'),

    # API para agente local
    path('api/agent/upload/', views.api_agent_upload, name='api_agent_upload'),
    
    # Progresso
    path('progresso/<int:tarefa_id>/', views.progresso, name='progresso'),
    
    # Histórico
    path('historico/', views.historico, name='historico'),
    path('download/progresso/<int:tarefa_id>/', views.progresso_download, name='progresso_download'),
path('download/api/progresso/<int:tarefa_id>/', views.api_progresso_download, name='api_progresso_download'),
path('download/lista/', views.listar_downloads, name='lista_downloads'),
    
path('empresas/upload-certificado/', views.upload_certificado_temporario, name='upload_certificado'),
    path('empresas/upload-certificado/', views.upload_certificado_temporario, name='upload_certificado'),
    # Autenticação
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]