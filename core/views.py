# views.py - Completo e Organizado
# HDowloader - Sistema de Download Automático de NFSe
from .tasks import iniciar_download_tarefa
from .models import TarefaDownload
from django.http import JsonResponse
# ========== IMPORTS PADRÃO ==========
import json
import os
import re
import hashlib
from datetime import datetime
from functools import lru_cache

# ========== IMPORTS DJANGO ==========
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.forms import modelform_factory
from django.db import models, IntegrityError
from django.core.files.storage import default_storage
from django.utils import timezone

# ========== IMPORTS DE BIBLIOTECAS EXTERNAS ==========
import requests as pyrequests
import win32com.client
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ========== IMPORTS DO PROJETO ==========
from .models import Pessoa, Empresa, Agendamento, HistoricoDownload, NotaFiscal
from .forms import PessoaForm, EmpresaForm, AgendamentoForm
from .download_service import download_em_massa
from .certificado_service import listar_certificados_windows
from django.contrib.auth import logout as django_logout
import secrets

# ========== VIEWS DE DOWNLOAD ==========
@login_required
def download_manual(request):
    """Download manual de NFSe com tarefas em background"""
    import os
    from django.contrib import messages
    from .models import Empresa
    from .tasks import iniciar_download_tarefa
    
    # Filtra empresas disponíveis
    if request.user.is_superuser:
        empresas = Empresa.objects.filter(ativo=True)
    elif hasattr(request.user, 'pessoa'):
        empresas = request.user.pessoa.empresas.filter(ativo=True)
    else:
        empresas = Empresa.objects.none()
    
    # Tarefas recentes do usuário
    if hasattr(request.user, 'pessoa'):
        tarefas_recentes = TarefaDownload.objects.filter(
            usuario=request.user.pessoa
        ).order_by('-data_criacao')[:5]
    else:
        tarefas_recentes = []
    
    msg = None
    empresa_selecionada = None
    precisa_certificado = False
    
    # Verifica se tem empresa na URL
    empresa_id = request.GET.get('empresa') or request.POST.get('empresa')
    
    if empresa_id and str(empresa_id).isdigit():
        try:
            empresa_selecionada = Empresa.objects.get(pk=empresa_id)
            if not empresa_selecionada.certificado_arquivo:
                precisa_certificado = True
        except Empresa.DoesNotExist:
            pass
    
    if request.method == 'POST':
        tipo = request.POST.get('tipo')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim')
        
        if not empresa_id:
            msg = 'Selecione uma empresa.'
        elif not tipo or not data_inicio or not data_fim:
            msg = 'Preencha todos os campos.'
        else:
            try:
                empresa = get_object_or_404(Empresa, pk=empresa_id)

                # Permissão para iniciar download desta empresa
                from .permissions import can_edit_empresa
                if not can_edit_empresa(request.user, empresa):
                    msg = 'Permissão negada para iniciar downloads desta empresa.'
                    return render(request, 'core/download_manual.html', {
                        'empresas': empresas,
                        'tarefas_recentes': tarefas_recentes,
                        'msg': msg,
                        'empresa_selecionada': empresa,
                        'precisa_certificado': not empresa.certificado_arquivo,
                        'tipo': tipo,
                        'data_inicio': data_inicio,
                        'data_fim': data_fim,
                    })

                if not empresa.certificado_arquivo:
                    return render(request, 'core/download_manual.html', {
                        'empresas': empresas,
                        'tarefas_recentes': tarefas_recentes,
                        'msg': 'Empresa não possui certificado. Faça o upload abaixo.',
                        'empresa_selecionada': empresa,
                        'precisa_certificado': True,
                        'tipo': tipo,
                        'data_inicio': data_inicio,
                        'data_fim': data_fim,
                    })
                
                # Prepara pasta de destino
                pasta_destino = os.path.join(
                    'media', 'nfse', tipo,
                    data_inicio[:4], data_inicio[5:7]
                )
                pasta_destino = os.path.abspath(pasta_destino)
                os.makedirs(pasta_destino, exist_ok=True)
                
                # Inicia tarefa em background
                tarefa_id = iniciar_download_tarefa(
                    empresa=empresa,
                    tipo=tipo,
                    data_inicio=data_inicio,
                    data_fim=data_fim,
                    pasta_destino=pasta_destino,
                    usuario=request.user.pessoa if hasattr(request.user, 'pessoa') else None
                )
                
                messages.success(request, f'Download iniciado! Acesse a página de progresso para acompanhar.')
                return redirect('progresso_download', tarefa_id=tarefa_id)
                    
            except Exception as e:
                msg = f'❌ Erro: {str(e)}'
    
    return render(request, 'core/download_manual.html', {
        'empresas': empresas,
        'tarefas_recentes': tarefas_recentes,
        'msg': msg,
        'empresa_selecionada': empresa_selecionada,
        'precisa_certificado': precisa_certificado,
    })

@login_required
def progresso_download(request, tarefa_id):
    """Página de progresso do download"""
    tarefa = get_object_or_404(TarefaDownload, pk=tarefa_id)
    
    # Verifica permissão
    if not request.user.is_superuser:
        if not hasattr(request.user, 'pessoa') or tarefa.usuario != request.user.pessoa:
            return redirect('dashboard')
    
    return render(request, 'core/progresso_download.html', {'tarefa': tarefa})

@login_required
def api_progresso_download(request, tarefa_id):
    """API para obter progresso via AJAX"""
    tarefa = get_object_or_404(TarefaDownload, pk=tarefa_id)
    
    # Verifica permissão
    if not request.user.is_superuser:
        if not hasattr(request.user, 'pessoa') or tarefa.usuario != request.user.pessoa:
            return JsonResponse({'error': 'Permissão negada'}, status=403)
    
    data = {
        'id': tarefa.pk,
        'status': tarefa.status,
        'progresso': tarefa.progresso,
        'mensagem': tarefa.mensagem,
        'total_notas': tarefa.total_notas,
        'notas_baixadas': tarefa.notas_baixadas,
        'notas_erro': tarefa.notas_erro,
        'data_criacao': tarefa.data_criacao.strftime('%d/%m/%Y %H:%M'),
        'data_inicio': tarefa.data_inicio_execucao.strftime('%d/%m/%Y %H:%M') if tarefa.data_inicio_execucao else None,
        'data_fim': tarefa.data_fim_execucao.strftime('%d/%m/%Y %H:%M') if tarefa.data_fim_execucao else None,
        'logs': tarefa.logs,
        'zip_url': tarefa.arquivo_zip.url if tarefa.arquivo_zip else None,
    }
    
    return JsonResponse(data)

@login_required
def listar_downloads(request):
    """Lista todos os downloads do usuário"""
    if request.user.is_superuser:
        tarefas = TarefaDownload.objects.all().select_related('empresa', 'usuario')
    elif hasattr(request.user, 'pessoa'):
        tarefas = TarefaDownload.objects.filter(usuario=request.user.pessoa).select_related('empresa')
    else:
        tarefas = TarefaDownload.objects.none()
    
    return render(request, 'core/lista_downloads.html', {'tarefas': tarefas})

@login_required
@csrf_exempt
def upload_certificado_temporario(request):
    """
    Endpoint para receber certificado via AJAX durante o download
    """
    if request.method == 'POST':
        from core.models import Empresa
        from django.core.files import File
        import tempfile
        import os
        
        empresa_id = request.POST.get('empresa_id')
        senha = request.POST.get('senha', '')
        certificado_file = request.FILES.get('certificado')
        
        if not empresa_id or not certificado_file or not senha:
            return JsonResponse({'status': 'ERRO', 'msg': 'Dados incompletos'})
        
        try:
            empresa = Empresa.objects.get(pk=empresa_id)

            # Salva o arquivo na empresa (upload temporário via AJAX durante o download manual)
            empresa.certificado_arquivo.save(certificado_file.name, certificado_file, save=True)
            empresa.certificado_senha = senha
            
            # Tenta extrair o thumbprint
            try:
                import hashlib
                from cryptography.hazmat.primitives.serialization import pkcs12
                from cryptography.hazmat.backends import default_backend
                
                with open(empresa.certificado_arquivo.path, 'rb') as f:
                    pfx_data = f.read()
                
                cert = pkcs12.load_key_and_certificates(pfx_data, senha.encode(), default_backend())
                if cert and cert[1]:
                    thumbprint = hashlib.sha1(cert[1].public_bytes()).hexdigest().upper()
                    empresa.certificado_thumbprint = thumbprint
            except:
                pass  # Se não conseguir extrair, continua sem thumbprint
            
            empresa.save()
            
            return JsonResponse({
                'status': 'OK', 
                'msg': 'Certificado salvo com sucesso!',
                'thumbprint': empresa.certificado_thumbprint
            })
            
        except Exception as e:
            return JsonResponse({'status': 'ERRO', 'msg': str(e)})
    
    return JsonResponse({'status': 'ERRO', 'msg': 'Método inválido'})

@login_required
def download_progress(request, historico_id):
    """Acompanha progresso do download"""
    historico = get_object_or_404(HistoricoDownload, pk=historico_id)
    return render(request, 'core/download_progress.html', {'historico': historico})

# ========== FUNÇÕES AUXILIARES ==========
            
            # ... resto do código
def extrair_cnpj_certificado(subject):
    """Extrai CNPJ do subject do certificado"""
    # Tenta múltiplos padrões conhecidos
    padroes = [
        r'CNPJ\s*=\s*([0-9]{14})',
        r'SERIALNUMBER\s*=\s*([0-9]{14})',
        r'SERIALNUMBER=([0-9]{14})',
        r'CNPJ:([0-9]{14})',
        r'O=([0-9]{14})',
        r'CN=[^:]+:([0-9]{14})',  # CN=Nome Fantasia:12345678000199
        r'OU=([0-9]{14})',
    ]
    
    for padrao in padroes:
        m = re.search(padrao, subject, re.IGNORECASE)
        if m:
            cnpj = m.group(1)
            # Valida se tem 14 dígitos
            if len(cnpj) == 14 and cnpj.isdigit():
                return cnpj
    
    # Tenta extrair qualquer sequência de 14 dígitos
    m = re.search(r'(\d{14})', subject)
    if m:
        return m.group(1)
    
    return None

@lru_cache(maxsize=256)
def consultar_cnpj_receita(cnpj):
    """Consulta CNPJ na API da ReceitaWS (com cache em memória).
    Retorna dicionário com os campos já normalizados.
    """
    try:
        api_url = f'https://www.receitaws.com.br/v1/cnpj/{cnpj}'
        resp = pyrequests.get(api_url, timeout=10)
        if resp.status_code == 200:
            dados = resp.json()
            if dados.get('status') == 'OK':
                return {
                    'status': 'OK',
                    'nome': dados.get('nome', ''),
                    'fantasia': dados.get('fantasia', ''),
                    'ie': dados.get('ie', ''),
                    'im': dados.get('im', ''),
                    'cep': dados.get('cep', ''),
                    'logradouro': dados.get('logradouro', ''),
                    'numero': dados.get('numero', ''),
                    'bairro': dados.get('bairro', ''),
                    'municipio': dados.get('municipio', ''),
                    'uf': dados.get('uf', ''),
                }
        return {'status': 'ERRO', 'msg': 'CNPJ não encontrado'}
    except Exception as e:
        return {'status': 'ERRO', 'msg': str(e)}

# ========== VIEWS DE PESSOAS (USUÁRIOS) ==========

@login_required
@user_passes_test(lambda u: u.is_superuser)
def pessoa_list(request):
    """Lista todas as pessoas (apenas admin)"""
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    
    pessoas = Pessoa.objects.select_related('user').all()
    
    if q:
        pessoas = pessoas.filter(
            models.Q(user__first_name__icontains=q) |
            models.Q(user__last_name__icontains=q) |
            models.Q(cpf__icontains=q) |
            models.Q(user__email__icontains=q)
        )
    
    if status == 'ativa':
        pessoas = pessoas.filter(ativo=True)
    elif status == 'inativa':
        pessoas = pessoas.filter(ativo=False)
    
    return render(request, 'core/pessoa_list.html', {
        'pessoas': pessoas,
        'q': q,
        'status': status
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def pessoa_create(request):
    """Cria uma nova pessoa (admin)"""
    if request.method == 'POST':
        form = PessoaForm(request.POST, request.FILES)
        if form.is_valid():
            # Cria usuário (protege contra conflito de username)
            try:
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    password=form.cleaned_data['password'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name']
                )
            except IntegrityError:
                form.add_error('username', 'Nome de usuário já existe.')
            else:
                # Cria pessoa
                pessoa = form.save(commit=False)
                pessoa.user = user
                pessoa.save()
                return redirect('pessoa_list')
    else:
        form = PessoaForm()
    
    return render(request, 'core/pessoa_form.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_superuser)
def pessoa_edit(request, pk):
    """Edita uma pessoa existente (admin)"""
    pessoa = get_object_or_404(Pessoa, pk=pk)
    
    if request.method == 'POST':
        form = PessoaForm(request.POST, request.FILES, instance=pessoa)
        if form.is_valid():
            pessoa = form.save()
            
            # Atualiza dados do user
            pessoa.user.first_name = form.cleaned_data['first_name']
            pessoa.user.last_name = form.cleaned_data['last_name']
            pessoa.user.email = form.cleaned_data['email']
            pessoa.user.username = form.cleaned_data['username']
            
            if form.cleaned_data.get('password'):
                pessoa.user.set_password(form.cleaned_data['password'])
            
            pessoa.user.save()
            
            return redirect('pessoa_list')
    else:
        form = PessoaForm(instance=pessoa)
    
    return render(request, 'core/pessoa_form.html', {'form': form})

# ========== VIEWS DE EMPRESAS ==========

@login_required
def empresa_list(request):
    """Lista empresas com filtros"""
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    status = request.GET.get('status', '')
    
    # Filtra por permissão
    if request.user.is_superuser:
        empresas = Empresa.objects.all()
    elif hasattr(request.user, 'pessoa'):
        empresas = request.user.pessoa.empresas.all()
    else:
        empresas = Empresa.objects.none()
    
    # Aplica filtros
    if q:
        empresas = empresas.filter(
            models.Q(nome_fantasia__icontains=q) |
            models.Q(razao_social__icontains=q) |
            models.Q(cnpj__icontains=q)
        )
    
    if tipo:
        empresas = empresas.filter(tipo=tipo)
    
    if status == 'ativa':
        empresas = empresas.filter(ativo=True)
    elif status == 'inativa':
        empresas = empresas.filter(ativo=False)
    
    return render(request, 'core/empresa_list.html', {
        'empresas': empresas,
        'q': q,
        'tipo': tipo,
        'status': status,
        'tipos': Empresa.TIPO_CHOICES
    })

@login_required
def empresa_create(request):
    """Redireciona para criação customizada"""
    return redirect('empresa_create_custom')

@login_required
def empresa_create_custom(request):
    """Cadastro de empresa com upload de certificado e busca automática"""
    msg = None
    # Usa o ModelForm para preencher/validar visualmente o formulário
    form = EmpresaForm(request.POST or None, request.FILES or None)

    # se veio show_upload na URL, requer upload (novo cadastro já exige upload por padrão)
    require_pfx = bool(request.GET.get('show_upload') == '1')

    if request.method == 'POST':
        # Lê valores básicos do POST (usados para processar certificado e API)
        cnpj = request.POST.get('cnpj', '').replace('.', '').replace('/', '').replace('-', '')
        certificado_file = request.FILES.get('certificado')
        certificado_senha = request.POST.get('certificado_senha', '')

        # Se o fluxo exige PFX por show_upload, valide a presença do arquivo
        if require_pfx and not certificado_file:
            msg = 'Upload do arquivo .pfx é obrigatório para este certificado.'
        # Validações básicas (mantém comportamento atual)
        elif not cnpj:
            msg = 'CNPJ é obrigatório.'
        elif not certificado_file and not certificado_senha:
            msg = 'Certificado e senha são obrigatórios.'
        else:
            try:
                certificado_thumbprint = ''
                certificado_emitente = ''

                # Processa certificado se foi enviado
                if certificado_file and certificado_senha:
                    cert_path = default_storage.save(f'tmp/{certificado_file.name}', certificado_file)
                    cert_full_path = default_storage.path(cert_path)

                    with open(cert_full_path, 'rb') as f:
                        pfx_data = f.read()

                    cert = pkcs12.load_key_and_certificates(
                        pfx_data,
                        certificado_senha.encode(),
                        default_backend()
                    )

                    if cert and cert[1]:
                        certificado_emitente = cert[1].subject.rfc4514_string()
                        thumbprint = hashlib.sha1(cert[1].public_bytes(serialization.Encoding.DER)).hexdigest().upper()
                        certificado_thumbprint = thumbprint

                        # Extrai CNPJ do certificado quando possível
                        cnpj_cert = extrair_cnpj_certificado(certificado_emitente)
                        if cnpj_cert and not cnpj:
                            cnpj = cnpj_cert

                    os.remove(cert_full_path)

                # Se necessário, preenche dados pela Receita
                # Não usar `form.cleaned_data` aqui — o form ainda pode não estar validado.
                razao_fornecida = request.POST.get('razao_social') or (form.initial or {}).get('razao_social')
                fantasia_fornecida = request.POST.get('nome_fantasia') or (form.initial or {}).get('nome_fantasia')
                if not razao_fornecida or not fantasia_fornecida:
                    dados_cnpj = consultar_cnpj_receita(cnpj)
                    if dados_cnpj.get('status') == 'OK':
                        # atualiza dados iniciais do form (não sobrescreve campos já preenchidos)
                        initial = form.initial or {}
                        initial.update({
                            'razao_social': initial.get('razao_social') or dados_cnpj.get('nome', ''),
                            'nome_fantasia': initial.get('nome_fantasia') or dados_cnpj.get('fantasia', ''),
                            'inscricao_estadual': initial.get('inscricao_estadual') or dados_cnpj.get('ie', ''),
                            'inscricao_municipal': initial.get('inscricao_municipal') or dados_cnpj.get('im', ''),
                            'cep': initial.get('cep') or dados_cnpj.get('cep', ''),
                            'logradouro': initial.get('logradouro') or dados_cnpj.get('logradouro', ''),
                            'numero': initial.get('numero') or dados_cnpj.get('numero', ''),
                            'bairro': initial.get('bairro') or dados_cnpj.get('bairro', ''),
                            'municipio': initial.get('municipio') or dados_cnpj.get('municipio', ''),
                            'uf': initial.get('uf') or dados_cnpj.get('uf', ''),
                        })
                        form.initial = initial

                # Se o form é válido (ou aceitável), cria/atualiza a empresa
                # Observação: mantemos a criação manual para garantir o tratamento do certificado
                empresa, created = Empresa.objects.update_or_create(
                    cnpj=cnpj,
                    defaults={
                        'razao_social': request.POST.get('razao_social', form.initial.get('razao_social', '')),
                        'nome_fantasia': request.POST.get('nome_fantasia', form.initial.get('nome_fantasia', '')),
                        'inscricao_municipal': request.POST.get('inscricao_municipal', form.initial.get('inscricao_municipal', '')),
                        'inscricao_estadual': request.POST.get('inscricao_estadual', form.initial.get('inscricao_estadual', '')),
                        'tipo': request.POST.get('tipo', 'matriz'),
                        'ativo': True,
                        'cep': request.POST.get('cep', form.initial.get('cep', '')),
                        'logradouro': request.POST.get('logradouro', form.initial.get('logradouro', '')),
                        'numero': request.POST.get('numero', form.initial.get('numero', '')),
                        'complemento': request.POST.get('complemento', form.initial.get('complemento', '')),
                        'bairro': request.POST.get('bairro', form.initial.get('bairro', '')),
                        'municipio': request.POST.get('municipio', form.initial.get('municipio', '')),
                        'uf': request.POST.get('uf', form.initial.get('uf', '')),
                        'certificado_thumbprint': certificado_thumbprint,
                        'certificado_senha': certificado_senha,
                        'certificado_emitente': certificado_emitente,
                    }
                )

                # Se existe um certificado temporário (vindo da extração via AJAX), movê-lo para o FileField
                cert_temp = request.POST.get('certificado_temp')
                if cert_temp:
                    try:
                        from django.core.files import File as DjangoFile
                        with default_storage.open(cert_temp, 'rb') as f:
                            empresa.certificado_arquivo.save(os.path.basename(cert_temp), DjangoFile(f), save=False)

                        # Tenta extrair metadados do PFX salvo
                        with empresa.certificado_arquivo.open('rb') as f:
                            pfx_data = f.read()

                        cert = pkcs12.load_key_and_certificates(pfx_data, certificado_senha.encode() if certificado_senha else None, default_backend())
                        if cert and cert[1]:
                            empresa.certificado_emitente = cert[1].subject.rfc4514_string()
                            empresa.certificado_validade = getattr(cert[1], 'not_valid_after', None)
                            empresa.certificado_thumbprint = hashlib.sha1(cert[1].public_bytes(serialization.Encoding.DER)).hexdigest().upper()

                        default_storage.delete(cert_temp)
                    except Exception as e:
                        msg = f'Erro ao processar certificado temporário: {str(e)}'

                if not request.user.is_superuser and hasattr(request.user, 'pessoa'):
                    empresa.usuarios.add(request.user.pessoa)

                msg = f"Empresa {'cadastrada' if created else 'atualizada'} com sucesso!"

                if 'continuar' not in request.POST:
                    return redirect('empresa_list')

            except Exception as e:
                msg = f'Erro ao processar: {str(e)}'

    # Garantir que o template receba um objeto form (bound ou não)
    if request.method == 'GET':
        form = EmpresaForm()

    return render(request, 'core/empresa_form_custom.html', {'msg': msg, 'form': form})

@login_required
def empresa_edit(request, pk):
    """Edita uma empresa existente usando EmpresaForm (preenchimento automático)."""
    empresa = get_object_or_404(Empresa, pk=pk)

    # Verifica permissão (centralizada)
    from .permissions import can_edit_empresa
    if not can_edit_empresa(request.user, empresa):
        return redirect('dashboard')

    msg = None

    # Se a página foi aberta com show_upload, exigir o .pfx
    require_pfx = bool(request.GET.get('show_upload') == '1' or request.POST.get('pfx_required') == '1')

    if request.method == 'POST':
        form = EmpresaForm(request.POST, request.FILES, instance=empresa)

        # Se for obrigatório enviar .pfx e nenhum arquivo foi enviado e não existe arquivo salvo, bloqueia
        certificado_file = request.FILES.get('certificado')
        if require_pfx and not certificado_file and not empresa.certificado_arquivo:
            msg = 'Upload do arquivo .pfx é obrigatório para concluir esta operação.'
        elif form.is_valid():
            empresa = form.save(commit=False)

            # Trata novo arquivo de certificado (campo de upload no template é 'certificado')
            certificado_senha = request.POST.get('certificado_senha', '')

            if certificado_file and certificado_senha:
                try:
                    cert_path = default_storage.save(f'tmp/{certificado_file.name}', certificado_file)
                    cert_full_path = default_storage.path(cert_path)

                    with open(cert_full_path, 'rb') as f:
                        pfx_data = f.read()

                    cert = pkcs12.load_key_and_certificates(
                        pfx_data,
                        certificado_senha.encode() if certificado_senha else None,
                        default_backend()
                    )

                    if cert and cert[1]:
                        empresa.certificado_emitente = cert[1].subject.rfc4514_string()
                        thumbprint = hashlib.sha1(cert[1].public_bytes(serialization.Encoding.DER)).hexdigest().upper()
                        empresa.certificado_thumbprint = thumbprint
                        empresa.certificado_senha = certificado_senha

                    # Salva arquivo do certificado no model se desejar
                    empresa.certificado_arquivo = certificado_file

                    os.remove(cert_full_path)

                except Exception as e:
                    msg = f'Erro ao processar certificado: {str(e)}'
            else:
                # Se veio um certificado temporário (extração via AJAX), move para o campo FileField e extrai metadados
                cert_temp = request.POST.get('certificado_temp')
                if cert_temp:
                    try:
                        from django.core.files import File as DjangoFile
                        with default_storage.open(cert_temp, 'rb') as f:
                            empresa.certificado_arquivo.save(os.path.basename(cert_temp), DjangoFile(f), save=False)

                        senha_temp = certificado_senha or request.POST.get('certificado_senha', '')
                        with empresa.certificado_arquivo.open('rb') as f:
                            pfx_data = f.read()

                        cert = pkcs12.load_key_and_certificates(pfx_data, senha_temp.encode() if senha_temp else None, default_backend())
                        if cert and cert[1]:
                            empresa.certificado_emitente = cert[1].subject.rfc4514_string()
                            empresa.certificado_validade = getattr(cert[1], 'not_valid_after', None)
                            empresa.certificado_thumbprint = hashlib.sha1(cert[1].public_bytes(serialization.Encoding.DER)).hexdigest().upper()
                            empresa.certificado_senha = senha_temp

                        default_storage.delete(cert_temp)
                    except Exception as e:
                        msg = f'Erro ao processar certificado temporário: {str(e)}'
                else:
                    # Se não veio arquivo, mas o formulário contém thumbprint (ex.: extração via JS), atualiza campos do certificado
                    thumb = form.cleaned_data.get('certificado_thumbprint')
                    if thumb:
                        empresa.certificado_thumbprint = thumb
                        empresa.certificado_emitente = form.cleaned_data.get('certificado_emitente')
                        empresa.certificado_validade = form.cleaned_data.get('certificado_validade')

            if not msg:
                empresa.save()
                form.save_m2m()
                # Se o submit foi apenas para salvar o certificado, permanece na página de edição
                if request.POST.get('salvar_certificado'):
                    return redirect('empresa_edit', pk=empresa.pk)
                return redirect('empresa_list')
    else:
        form = EmpresaForm(instance=empresa)

    return render(request, 'core/empresa_form.html', {'form': form, 'msg': msg, 'require_pfx': require_pfx})


@login_required
def empresa_dashboard(request, pk):
    """Dashboard específico por empresa — agrega dados de NotaFiscal para contabilidade."""
    empresa = get_object_or_404(Empresa, pk=pk)

    # Permissão: superuser ou usuário vinculado (centralizada)
    from .permissions import can_view_empresa
    if not can_view_empresa(request.user, empresa):
        return redirect('dashboard')

    # KPI principais
    notas = empresa.notas.all()
    total_notas = notas.count()
    total_valor = float(notas.aggregate(models.Sum('valor'))['valor__sum'] or 0)
    recentes = notas.order_by('-data_emissao')[:10]

    # Top fornecedores (tomador_nome)
    top_fornecedores = (
        notas.values('tomador_nome')
             .annotate(total=models.Count('id'), soma=models.Sum('valor'))
             .order_by('-total')[:10]
    )

    # Distribuição por mês (últimos 12 meses)
    from django.db.models.functions import TruncMonth
    meses = (
        notas.annotate(mes=TruncMonth('data_emissao'))
             .values('mes')
             .annotate(qtd=models.Count('id'), soma=models.Sum('valor'))
             .order_by('-mes')[:12]
    )

    return render(request, 'core/empresa_dashboard.html', {
        'empresa': empresa,
        'total_notas': total_notas,
        'total_valor': total_valor,
        'recentes': recentes,
        'top_fornecedores': top_fornecedores,
        'meses': meses,
    })

@login_required
def empresa_certificado(request):
    """Cadastro de empresa usando certificado da loja do Windows"""
    msg = None
    certificados = listar_certificados_windows()

    # Empresas do usuário (para permitir salvar .pfx em uma empresa existente)
    if request.user.is_superuser:
        empresas = Empresa.objects.filter(ativo=True)
    elif hasattr(request.user, 'pessoa'):
        empresas = request.user.pessoa.empresas.filter(ativo=True)
    else:
        empresas = Empresa.objects.none()
    
    if request.method == 'POST':
        thumbprint = request.POST.get('thumbprint')
        
        if not thumbprint:
            msg = 'Selecione um certificado.'
        else:
            try:
                # Busca certificado na loja
                store = win32com.client.Dispatch('CAPICOM.Store')
                store.Open(2, "My", 0)
                
                cert = None
                for c in store.Certificates:
                    if c.Thumbprint == thumbprint:
                        cert = c
                        break
                
                if not cert:
                    raise Exception('Certificado não encontrado.')
                
                subject = cert.SubjectName
                
                # Extrai CNPJ
                cnpj = extrair_cnpj_certificado(subject)
                if not cnpj:
                    raise Exception('CNPJ não encontrado no certificado.')
                
                # Consulta dados na Receita
                dados = consultar_cnpj_receita(cnpj)
                
                if dados.get('status') != 'OK':
                    raise Exception('Não foi possível obter dados do CNPJ.')
                
                # Cria empresa
                empresa, created = Empresa.objects.get_or_create(
                    cnpj=cnpj,
                    defaults={
                        'razao_social': dados['nome'],
                        'nome_fantasia': dados['fantasia'],
                        'inscricao_estadual': dados['ie'],
                        'inscricao_municipal': dados['im'],
                        'cep': dados['cep'],
                        'logradouro': dados['logradouro'],
                        'numero': dados['numero'],
                        'bairro': dados['bairro'],
                        'municipio': dados['municipio'],
                        'uf': dados['uf'],
                        'tipo': 'matriz',
                        'ativo': True,
                        'certificado_thumbprint': thumbprint,
                        'certificado_emitente': subject,
                    }
                )
                
                # Vincula ao usuário
                if not request.user.is_superuser and hasattr(request.user, 'pessoa'):
                    empresa.usuarios.add(request.user.pessoa)
                
                msg = f"Empresa {'cadastrada' if created else 'já existente'}: {empresa.nome_fantasia}"
                
            except Exception as e:
                msg = f'Erro: {str(e)}'
    
    return render(request, 'core/empresa_certificado.html', {
        'certificados': certificados,
        'empresas': empresas,
        'msg': msg
    })

# ========== VIEWS DE AGENDAMENTOS ==========

@login_required
def agendamento_list(request):
    """Lista agendamentos do usuário"""
    if request.user.is_superuser:
        agendamentos = Agendamento.objects.select_related('empresa').all()
    elif hasattr(request.user, 'pessoa'):
        empresas = request.user.pessoa.empresas.all()
        agendamentos = Agendamento.objects.filter(empresa__in=empresas).select_related('empresa')
    else:
        agendamentos = Agendamento.objects.none()
    
    return render(request, 'core/agendamento_list.html', {'agendamentos': agendamentos})

@login_required
def agendamento_create(request):
    """Cria novo agendamento"""
    AgendamentoForm = modelform_factory(Agendamento, exclude=[])
    
    if request.method == 'POST':
        form = AgendamentoForm(request.POST)
        if form.is_valid():
            agendamento = form.save()
            return redirect('agendamento_list')
    else:
        form = AgendamentoForm()
    
    # Filtra empresas para o usuário
    if request.user.is_superuser:
        form.fields['empresa'].queryset = Empresa.objects.filter(ativo=True)
    elif hasattr(request.user, 'pessoa'):
        form.fields['empresa'].queryset = request.user.pessoa.empresas.filter(ativo=True)
    
    return render(request, 'core/agendamento_form.html', {'form': form})

@login_required
def agendamento_edit(request, pk):
    """Edita agendamento existente"""
    agendamento = get_object_or_404(Agendamento, pk=pk)
    
    # Verifica permissão
    if not request.user.is_superuser:
        if not hasattr(request.user, 'pessoa') or agendamento.empresa not in request.user.pessoa.empresas.all():
            return redirect('dashboard')
    
    AgendamentoForm = modelform_factory(Agendamento, exclude=[])
    
    if request.method == 'POST':
        form = AgendamentoForm(request.POST, instance=agendamento)
        if form.is_valid():
            form.save()
            return redirect('agendamento_list')
    else:
        form = AgendamentoForm(instance=agendamento)
    
    return render(request, 'core/agendamento_form.html', {'form': form})

# ========== VIEWS DE DOWNLOAD ==========

@login_required
def download_progress(request, historico_id):
    """Acompanha progresso do download"""
    historico = get_object_or_404(HistoricoDownload, pk=historico_id)
    return render(request, 'core/download_progress.html', {'historico': historico})

# ========== VIEWS DE CONSULTA (APIs) ==========

@login_required
@csrf_exempt
def buscar_cnpj(request):
    """Endpoint AJAX para buscar dados de CNPJ"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cnpj = data.get('cnpj', '').replace('.', '').replace('/', '').replace('-', '')
            
            if not cnpj or len(cnpj) != 14:
                return JsonResponse({'status': 'ERRO', 'msg': 'CNPJ inválido.'})
            
            dados = consultar_cnpj_receita(cnpj)
            return JsonResponse(dados)
            
        except Exception as e:
            return JsonResponse({'status': 'ERRO', 'msg': str(e)})
    
    return JsonResponse({'status': 'ERRO', 'msg': 'Método inválido.'})


@login_required
def api_cep(request):
    """Proxy seguro para ViaCEP (retorna JSON de endereço)."""
    cep = (request.GET.get('cep') or '').replace('-', '').strip()
    if not cep or len(cep) != 8 or not cep.isdigit():
        return JsonResponse({'status': 'ERRO', 'msg': 'CEP inválido.'})
    try:
        resp = pyrequests.get(f'https://viacep.com.br/ws/{cep}/json/', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('erro'):
                return JsonResponse({'status': 'ERRO', 'msg': 'CEP não encontrado.'})
            return JsonResponse({'status': 'OK', 'cep': data})
        return JsonResponse({'status': 'ERRO', 'msg': 'Erro ao consultar CEP.'})
    except Exception as e:
        return JsonResponse({'status': 'ERRO', 'msg': str(e)})



@login_required
def generate_client_token(request):
    """Gera/Regenera token para agente local do usuário logado."""
    if not hasattr(request.user, 'pessoa'):
        return JsonResponse({'status': 'ERRO', 'msg': 'Sem perfil associado.'})
    pessoa = request.user.pessoa
    token = secrets.token_hex(24)
    pessoa.client_api_token = token
    pessoa.save()
    return JsonResponse({'status': 'OK', 'token': token})


@csrf_exempt
def api_agent_upload(request):
    """Endpoint que o agente local usa para enviar arquivos baixados.
    Autenticação por header 'Authorization: Token <token>' ou 'X-Api-Key'.
    Espera: empresa (id), tipo (emitidas|recebidas) e arquivos multipart.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'ERRO', 'msg': 'Método inválido.'}, status=405)

    # autenticação por token
    auth = request.headers.get('Authorization') or request.headers.get('authorization')
    token = None
    if auth and auth.startswith('Token '):
        token = auth.split(' ', 1)[1].strip()
    else:
        token = request.headers.get('X-Api-Key') or request.POST.get('api_key')

    if not token:
        return JsonResponse({'status': 'ERRO', 'msg': 'Token obrigatório.'}, status=401)

    pessoa = Pessoa.objects.filter(client_api_token=token).first()
    if not pessoa:
        return JsonResponse({'status': 'ERRO', 'msg': 'Token inválido.'}, status=403)

    empresa_id = request.POST.get('empresa') or request.GET.get('empresa')
    tipo = request.POST.get('tipo') or request.GET.get('tipo') or 'emitidas'

    empresa = None
    if empresa_id:
        try:
            empresa = Empresa.objects.get(pk=int(empresa_id))
        except Exception:
            return JsonResponse({'status': 'ERRO', 'msg': 'Empresa inválida.'}, status=400)

        # verifica vínculo
        if pessoa not in empresa.usuarios.all() and not pessoa.user.is_superuser:
            return JsonResponse({'status': 'ERRO', 'msg': 'Usuário sem permissão para essa empresa.'}, status=403)

    # Salva arquivos recebidos
    files = request.FILES.getlist('files') or []
    saved = 0
    pasta_destino = os.path.join('media', 'nfse', tipo, str(timezone.now().year), f"{timezone.now().month:02d}")
    os.makedirs(pasta_destino, exist_ok=True)

    for f in files:
        caminho = os.path.join(pasta_destino, f.name)
        with open(caminho, 'wb') as out:
            out.write(f.read())
        saved += 1

    # registra histórico mínimo
    historico = HistoricoDownload.objects.create(
        empresa=empresa,
        usuario=pessoa,
        tipo_nota=tipo,
        data_inicio=timezone.now(),
        periodo_busca_inicio=timezone.now().date(),
        periodo_busca_fim=timezone.now().date(),
        quantidade_notas=len(files),
        quantidade_sucesso=saved,
        status='sucesso' if saved == len(files) else 'parcial'
    )

    return JsonResponse({'status': 'OK', 'saved': saved, 'historico_id': historico.pk})

@login_required
@csrf_exempt
def buscar_certificado(request):
    """Endpoint AJAX para extrair dados de certificado enviado"""
    if request.method == 'POST':
        certificado_file = request.FILES.get('certificado')
        senha = request.POST.get('senha', '')
        
        if not certificado_file or not senha:
            return JsonResponse({'status': 'ERRO', 'msg': 'Arquivo e senha obrigatórios.'})
        
        try:
            # Salva certificado temporariamente
            cert_path = default_storage.save(f'tmp/{certificado_file.name}', certificado_file)
            cert_full_path = default_storage.path(cert_path)
            
            # Lê certificado
            with open(cert_full_path, 'rb') as f:
                pfx_data = f.read()
            
            cert = pkcs12.load_key_and_certificates(
                pfx_data, 
                senha.encode() if senha else None, 
                default_backend()
            )

            if not cert or not cert[1]:
                raise Exception('Certificado inválido.')

            subject = cert[1].subject.rfc4514_string()

            # Extrai CNPJ
            cnpj = extrair_cnpj_certificado(subject)

            if not cnpj:
                return JsonResponse({
                    'status': 'ERRO', 
                    'msg': f'CNPJ não encontrado no certificado. Subject: {subject}'
                })

            # Consulta dados do CNPJ
            dados = consultar_cnpj_receita(cnpj)

            if dados.get('status') != 'OK':
                return JsonResponse({'status': 'ERRO', 'msg': 'CNPJ não encontrado na Receita.'})

            # Adiciona CNPJ, thumbprint e caminho temporário ao retorno
            thumbprint = hashlib.sha1(cert[1].public_bytes(serialization.Encoding.DER)).hexdigest().upper()
            dados['cnpj'] = cnpj
            dados['thumbprint'] = thumbprint
            dados['emitente'] = subject
            dados['certificado_temp'] = cert_path  # mantém o .pfx temporário para salvar depois pelo form

            # NÃO remove o arquivo temporário aqui — será movido quando o usuário salvar o certificado
            return JsonResponse(dados)
            
        except Exception as e:
            return JsonResponse({'status': 'ERRO', 'msg': str(e)})
    
    return JsonResponse({'status': 'ERRO', 'msg': 'Método inválido.'})

# ========== VIEWS DE DASHBOARD E ESTATÍSTICAS ==========

@login_required
def dashboard(request):
    """Dashboard principal"""
    # Estatísticas do mês
    now = timezone.now()
    total_mes = HistoricoDownload.objects.filter(
        data_inicio__year=now.year,
        data_inicio__month=now.month
    ).aggregate(total=models.Sum('quantidade_sucesso'))['total'] or 0
    
    # Últimos 10 downloads
    historico = HistoricoDownload.objects.select_related('empresa').order_by('-data_inicio')[:10]
    
    # Empresas do usuário
    if request.user.is_superuser:
        empresas = Empresa.objects.filter(ativo=True)[:6]
    elif hasattr(request.user, 'pessoa'):
        empresas = request.user.pessoa.empresas.filter(ativo=True)
    else:
        empresas = Empresa.objects.none()
    
    return render(request, 'core/dashboard.html', {
        'total_mes': total_mes,
        'historico': historico,
        'empresas': empresas
    })

@login_required
def historico(request):
    """Histórico completo de downloads"""
    if request.user.is_superuser:
        historico = HistoricoDownload.objects.select_related('empresa').order_by('-data_inicio')
    elif hasattr(request.user, 'pessoa'):
        empresas = request.user.pessoa.empresas.all()
        historico = HistoricoDownload.objects.filter(empresa__in=empresas).order_by('-data_inicio')
    else:
        historico = HistoricoDownload.objects.none()
    
    return render(request, 'core/historico.html', {'historico': historico})

# ========== VIEWS DE CONFIGURAÇÃO E PERFIL ==========

@login_required
def configuracao(request):
    """Página de configurações do sistema"""
    return render(request, 'core/configuracao.html')


# ===== Roles UI (apenas superuser) =====
from django.contrib.auth.decorators import user_passes_test


@user_passes_test(lambda u: u.is_superuser)
def role_list(request):
    from .models import Role
    # Cria roles padrão se não existirem (ajuda no primeiro uso)
    if Role.objects.count() == 0:
        defaults = [
            {'name': 'Full Access', 'codename': 'full.access', 'descricao': 'Acesso total', 'permissions': 'empresa.edit,certificado.manage,conversor.use,download.manage', 'ativo': True},
            {'name': 'Download Manager', 'codename': 'download.manage', 'descricao': 'Gerenciar downloads', 'permissions': 'download.manage,empresa.edit', 'ativo': True},
            {'name': 'Conversor User', 'codename': 'conversor.use', 'descricao': 'Acessar conversor', 'permissions': 'conversor.use', 'ativo': True},
        ]
        for d in defaults:
            Role.objects.get_or_create(codename=d['codename'], defaults=d)

    roles = Role.objects.all().order_by('name')
    return render(request, 'core/role_list.html', {'roles': roles})


@user_passes_test(lambda u: u.is_superuser)
def role_create(request):
    from .forms import RoleForm
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('role_list')
    else:
        form = RoleForm()
    return render(request, 'core/role_form.html', {'form': form, 'creating': True})


@user_passes_test(lambda u: u.is_superuser)
def role_edit(request, pk):
    from .models import Role
    from .forms import RoleForm
    role = get_object_or_404(Role, pk=pk)
    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            return redirect('role_list')
    else:
        form = RoleForm(instance=role)
    return render(request, 'core/role_form.html', {'form': form, 'creating': False, 'role': role})


@user_passes_test(lambda u: u.is_superuser)
def role_delete(request, pk):
    from .models import Role
    role = get_object_or_404(Role, pk=pk)
    if request.method == 'POST':
        role.delete()
        return redirect('role_list')
    return render(request, 'core/role_confirm_delete.html', {'role': role})

@login_required
def perfil(request):
    """Perfil do usuário logado.

    Se o usuário ainda não tiver um objeto Pessoa associado, renderizamos a
    página de perfil com uma call-to-action para completar o cadastro em vez
    de redirecionar automaticamente para `pessoa_create`.
    """
    # Alguns usuários podem não ter o objeto Pessoa associado.
    if not hasattr(request.user, 'pessoa'):
        from django.contrib import messages
        messages.info(request, 'Complete seu perfil — cadastre os seus dados.')
        # Renderiza a mesma template, mas sem o objeto `pessoa` — o template
        # irá mostrar um botão para criar o perfil.
        return render(request, 'core/perfil.html', {'pessoa': None})

    pessoa = request.user.pessoa

    if request.method == 'POST':
        # Atualiza dados básicos
        pessoa.user.first_name = request.POST.get('first_name', pessoa.user.first_name)
        pessoa.user.last_name = request.POST.get('last_name', pessoa.user.last_name)
        pessoa.user.email = request.POST.get('email', pessoa.user.email)

        # Atualiza senha se fornecida
        senha = request.POST.get('password')
        if senha:
            pessoa.user.set_password(senha)

        pessoa.user.save()

        # Atualiza dados da pessoa
        pessoa.telefone = request.POST.get('telefone', pessoa.telefone)

        # Foto
        if request.FILES.get('foto'):
            pessoa.foto = request.FILES['foto']

        pessoa.save()

        return redirect('perfil')

    return render(request, 'core/perfil.html', {'pessoa': pessoa})


@login_required
def logout_view(request):
    """Encerra a sessão do usuário e redireciona para a página de login."""
    from django.contrib import messages
    django_logout(request)
    messages.success(request, 'Você foi desconectado com sucesso.')
    return redirect('login')

# ========== VIEWS DE CERTIFICADOS ==========

@login_required
def certificado_list(request):
    """Lista certificados instalados no Windows"""
    certificados = listar_certificados_windows()
    # Empresas disponíveis para o usuário (usadas ao salvar o .pfx)
    if request.user.is_superuser:
        empresas = Empresa.objects.filter(ativo=True)
    elif hasattr(request.user, 'pessoa'):
        empresas = request.user.pessoa.empresas.filter(ativo=True)
    else:
        empresas = Empresa.objects.none()

    return render(request, 'core/certificado_list.html', {'certificados': certificados, 'empresas': empresas})


@login_required
@csrf_exempt
def remover_certificado(request, pk):
    """Remove o certificado (FileField) da empresa informada."""
    empresa = get_object_or_404(Empresa, pk=pk)
    # Permissão centralizada
    from .permissions import can_manage_certificado
    if not can_manage_certificado(request.user, empresa):
        return JsonResponse({'status': 'ERRO', 'msg': 'Permissão negada.'}, status=403)
    try:
        if empresa.certificado_arquivo:
            empresa.certificado_arquivo.delete(save=False)
        empresa.certificado_thumbprint = ''
        empresa.certificado_emitente = ''
        empresa.certificado_validade = None
        empresa.certificado_senha = ''
        empresa.save()
        return JsonResponse({'status': 'OK'})
    except Exception as e:
        return JsonResponse({'status': 'ERRO', 'msg': str(e)}, status=500)


@login_required
def certificado_test(request):
    """Testa conexão com certificado"""
    msg = None
    
    if request.method == 'POST':
        thumbprint = request.POST.get('thumbprint')
        
        if thumbprint:
            try:
                # Testa conexão com o site
                from .certificado_service import criar_sessao_certificado
                session = criar_sessao_certificado(thumbprint)
                resp = session.get('https://www.nfse.gov.br/EmissorNacional', timeout=10)
                
                if resp.status_code == 200:
                    msg = '✅ Conexão com certificado realizada com sucesso!'
                else:
                    msg = f'⚠️ Conexão estabelecida mas retornou status {resp.status_code}'
                    
            except Exception as e:
                msg = f'❌ Erro na conexão: {str(e)}'
    
    certificados = listar_certificados_windows()
    return render(request, 'core/certificado_test.html', {
        'certificados': certificados,
        'msg': msg
    })


@login_required
def certificado_info(request):
    """AJAX: retorna empresas que possuem o certificado informado (thumbprint)."""
    thumb = request.GET.get('thumbprint')
    empresas = []
    if thumb:
        empresas_qs = Empresa.objects.filter(certificado_thumbprint__iexact=thumb)
        empresas = [{'id': e.pk, 'nome': e.nome_fantasia, 'cnpj': e.cnpj} for e in empresas_qs]
    return JsonResponse({'empresas': empresas})


@login_required
@csrf_exempt
def salvar_certificado(request):
    """Exporta o certificado pela thumbprint (loja Windows) e salva o .pfx no model da Empresa selecionada."""
    if request.method == 'POST':
        thumbprint = request.POST.get('thumbprint')
        empresa_id = request.POST.get('empresa_id')

        if not thumbprint or not empresa_id:
            return JsonResponse({'status': 'ERRO', 'msg': 'Parâmetros insuficientes.'})

        empresa = get_object_or_404(Empresa, pk=empresa_id)

        # Permissão
        from .permissions import can_manage_certificado
        if not can_manage_certificado(request.user, empresa):
            return JsonResponse({'status': 'ERRO', 'msg': 'Permissão negada.'})

        try:
            from .certificado_service import exportar_certificado_pfx
            pfx_path = exportar_certificado_pfx(thumbprint)

            # Salva arquivo no FileField da empresa
            from django.core.files import File as DjangoFile
            with open(pfx_path, 'rb') as f:
                empresa.certificado_arquivo.save(os.path.basename(pfx_path), DjangoFile(f), save=False)

            # Extrai metadados
            with empresa.certificado_arquivo.open('rb') as f:
                pfx_data = f.read()

            cert = pkcs12.load_key_and_certificates(pfx_data, None, default_backend())
            if cert and cert[1]:
                empresa.certificado_emitente = cert[1].subject.rfc4514_string()
                empresa.certificado_validade = getattr(cert[1], 'not_valid_after', None)
                empresa.certificado_thumbprint = hashlib.sha1(cert[1].public_bytes(serialization.Encoding.DER)).hexdigest().upper()

            empresa.certificado_senha = ''
            empresa.save()

            # remove temporário
            try:
                os.remove(pfx_path)
            except Exception:
                pass

            return JsonResponse({'status': 'OK', 'msg': 'Certificado salvo na empresa.'})

        except Exception as e:
            err = str(e)
            # Se a exportação falhou por CAPICOM/certutil -> indicar upload necessário
            if 'CAPICOM' in err or 'certutil' in err or 'Não foi possível obter PFX' in err or 'CAPICOM error' in err:
                return JsonResponse({
                    'status': 'NEEDS_PFX',
                    'msg': 'Não foi possível exportar o .pfx da loja. Faça upload do .pfx no cadastro da empresa (ou exporte manualmente e importe).',
                    'thumbprint': thumbprint,
                    'empresa_id': empresa_id
                })
            return JsonResponse({'status': 'ERRO', 'msg': err})

    return JsonResponse({'status': 'ERRO', 'msg': 'Método inválido.'})


# ========== VIEWS DE CERTIFICADO (CRUD) ==========
@login_required
def certificado_edit(request, pk):
    """Editar / substituir o .pfx associado a uma Empresa."""
    empresa = get_object_or_404(Empresa, pk=pk)
    # Permissão: superuser ou usuário vinculado à empresa
    if not request.user.is_superuser:
        if not hasattr(request.user, 'pessoa') or request.user.pessoa not in empresa.usuarios.all():
            from django.contrib import messages
            messages.error(request, 'Permissão negada.')
            return redirect('empresa_list')

    msg = None
    if request.method == 'POST':
        certificado_file = request.FILES.get('certificado')
        certificado_senha = request.POST.get('certificado_senha', '')

        if certificado_file:
            empresa.certificado_arquivo.save(certificado_file.name, certificado_file, save=False)
            empresa.certificado_senha = certificado_senha
            # Tenta extrair metadados (se falhar, salvamos o arquivo mesmo assim)
            try:
                with empresa.certificado_arquivo.open('rb') as f:
                    pfx_data = f.read()
                cert = pkcs12.load_key_and_certificates(
                    pfx_data,
                    certificado_senha.encode() if certificado_senha else None,
                    default_backend()
                )
                if cert and cert[1]:
                    empresa.certificado_emitente = cert[1].subject.rfc4514_string()
                    empresa.certificado_validade = getattr(cert[1], 'not_valid_after', None)
                    empresa.certificado_thumbprint = hashlib.sha1(cert[1].public_bytes(serialization.Encoding.DER)).hexdigest().upper()
            except Exception as e:
                msg = f'Erro ao processar certificado: {str(e)}'

            empresa.save()
            from django.contrib import messages
            if msg:
                messages.warning(request, msg)
            else:
                messages.success(request, 'Certificado atualizado com sucesso.')

            return redirect('empresa_edit', pk=pk)

    return render(request, 'core/certificado_edit.html', {'empresa': empresa, 'msg': msg})


@login_required
def certificado_download(request, pk):
    """Fazer download do .pfx armazenado para a Empresa (apenas usuários autorizados)."""
    empresa = get_object_or_404(Empresa, pk=pk)
    # Permissão
    from .permissions import can_manage_certificado
    if not can_manage_certificado(request.user, empresa):
        return JsonResponse({'status': 'ERRO', 'msg': 'Permissão negada.'}, status=403)

    if not empresa.certificado_arquivo:
        return JsonResponse({'status': 'ERRO', 'msg': 'Empresa não possui certificado.'}, status=404)

    try:
        from django.http import FileResponse
        fh = empresa.certificado_arquivo.open('rb')
        return FileResponse(fh, as_attachment=True, filename=os.path.basename(empresa.certificado_arquivo.name))
    except Exception as e:
        return JsonResponse({'status': 'ERRO', 'msg': str(e)}, status=500)


# ========== VIEWS DE PROGRESSO ==========

@login_required
def progresso(request, tarefa_id):
    """Acompanhamento de tarefa em background"""
    return render(request, 'core/progresso.html', {'tarefa_id': tarefa_id})

# ========== VIEWS PADRÃO ==========

def index(request):
    """Página inicial - redireciona para dashboard"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    return redirect('login')