# views.py - Completo e Organizado
# HDowloader - Sistema de Download Automático de NFSe
from django.http import JsonResponse
from django.http import RawPostDataException
from django.views import View
from core.models import Departamento, Analista, Atendimento, Empresa
from core.painel_utils import notificar_painel_departamento
from .tasks import iniciar_download_tarefa
from .models import TarefaDownload
from django.http import JsonResponse
from django.http import HttpResponseForbidden
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
# ========== IMPORTS PADRÃO ==========
import json
import os
import re
import hashlib
import time
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
from .sieg_service import SiegClient
from django.views.decorators.http import require_POST
from django.http import HttpResponseBadRequest
import json
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils.dateparse import parse_date

# ========== VIEWS DE DOWNLOAD ==========
@login_required
def download_manual(request):
    """Download manual de NFSe com tarefas em background"""
    import os
    from django.contrib import messages
    from .models import Empresa
    from .tasks import iniciar_download_tarefa
    
    # Qualquer usuário autenticado vê todas as empresas ativas
    empresas = Empresa.objects.filter(ativo=True)
    
    # inicializa flag antes de usá-la
    precisa_certificado = False

    # Tarefas recentes do usuário (não precisamos mostrar durante primeiro upload)
    if hasattr(request.user, 'pessoa') and not precisa_certificado:
        tarefas_recentes = TarefaDownload.objects.filter(
            usuario=request.user.pessoa
        ).order_by('-data_criacao')[:5]
    else:
        tarefas_recentes = []

    msg = None
    empresa_selecionada = None
    
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

def dados_departamento_api(request, departamento_id):
    departamento = get_object_or_404(Departamento, id=departamento_id)
    
    # Pendentes
    pendentes = Atendimento.objects.filter(
        departamento=departamento, 
        status='pendente'
    ).order_by('criado_em').values('id', 'empresa', 'criado_em')
    
    # Em andamento - CORRIGIDO!
    andamento = Atendimento.objects.filter(
        departamento=departamento, 
        status='atendendo'
    ).order_by('iniciado_em').select_related('analista__user').values(
        'id', 
        'empresa', 
        'iniciado_em'
    )
    
    # Formata as datas e pega o nome do analista separadamente
    pendentes_list = []
    for at in pendentes:
        pendentes_list.append({
            'id': at['id'],
            'empresa': at['empresa'],
            'criado_em': at['criado_em'].isoformat() if at['criado_em'] else None
        })
    
    andamento_list = []
    for at in andamento:
        # Busca o atendimento completo para pegar o analista
        atendimento = Atendimento.objects.get(id=at['id'])
        nome_analista = "Analista"
        if atendimento.analista:
            if hasattr(atendimento.analista, 'user') and atendimento.analista.user:
                nome_analista = atendimento.analista.user.get_full_name() or atendimento.analista.user.username
            elif hasattr(atendimento.analista, 'nome'):
                nome_analista = atendimento.analista.nome
        
        andamento_list.append({
            'id': at['id'],
            'analista': nome_analista,
            'empresa': at['empresa'],
            'iniciado_em': at['iniciado_em'].isoformat() if at['iniciado_em'] else None
        })
    
    return JsonResponse({
        'atendimentos_pendentes': pendentes_list,
        'atendimentos_andamento': andamento_list,
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

    if not request.user.is_superuser:
        if not hasattr(request.user, 'pessoa') or tarefa.usuario != request.user.pessoa:
            return JsonResponse({'error': 'Permissão negada'}, status=403)

    return JsonResponse(_serializar_progresso_tarefa(tarefa))


def _serializar_progresso_tarefa(tarefa):
    return {
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


def _extrair_token_api(request):
    auth = request.headers.get('Authorization') or request.headers.get('authorization')
    if auth:
        if auth.startswith('Token '):
            return auth.split(' ', 1)[1].strip()
        if auth.startswith('Bearer '):
            return auth.split(' ', 1)[1].strip()
    return request.headers.get('X-Api-Key') or request.POST.get('api_key') or request.GET.get('api_key')


def _autenticar_pessoa_por_token(request):
    token = _extrair_token_api(request)
    if not token:
        return None, JsonResponse({'status': 'ERRO', 'msg': 'Token obrigatório.'}, status=401)

    pessoa = Pessoa.objects.filter(client_api_token=token, ativo=True).select_related('user').first()
    if not pessoa:
        return None, JsonResponse({'status': 'ERRO', 'msg': 'Token inválido.'}, status=403)
    if not pessoa.user or not pessoa.user.is_active:
        return None, JsonResponse({'status': 'ERRO', 'msg': 'Usuário do token está inativo.'}, status=403)

    return pessoa, None


def _iniciar_download_por_parametros(request, user, pessoa_for_tarefa=None, aguardar_padrao=False):
    from django.urls import reverse
    from .permissions import can_edit_empresa

    def normalizar_cnpj(valor):
        return re.sub(r'\D', '', (valor or ''))

    payload = request.POST
    if not request.POST:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}

    cnpj = (payload.get('cnpj') or '').strip()
    tipo_input = (payload.get('tipo') or '').strip().lower()
    data_inicio_str = (payload.get('data_inicio') or '').strip()
    data_fim_str = (payload.get('data_fim') or '').strip()
    senha = (payload.get('senha') or '').strip()
    certificado_file = request.FILES.get('certificado')

    aguardar_raw = payload.get('aguardar_zip', payload.get('aguardar_conclusao', None))
    if aguardar_raw is None:
        aguardar_zip = bool(aguardar_padrao)
    else:
        aguardar_zip = str(aguardar_raw).strip().lower() in ('1', 'true', 'sim', 'yes')

    timeout_raw = payload.get('timeout_segundos', 900)
    try:
        timeout_segundos = int(timeout_raw)
    except Exception:
        timeout_segundos = 900
    timeout_segundos = max(10, min(timeout_segundos, 3600))

    if not cnpj or not tipo_input or not data_inicio_str or not data_fim_str:
        return JsonResponse({
            'status': 'ERRO',
            'msg': 'Parâmetros obrigatórios: cnpj, tipo, data_inicio, data_fim.'
        }, status=400)

    tipo_map = {
        'emitida': 'emitidas',
        'emitidas': 'emitidas',
        'recebida': 'recebidas',
        'recebidas': 'recebidas',
    }
    tipo = tipo_map.get(tipo_input)
    if not tipo:
        return JsonResponse({
            'status': 'ERRO',
            'msg': "Tipo inválido. Use: emitida/emitidas/recebida/recebidas."
        }, status=400)

    data_inicio = parse_date(data_inicio_str)
    data_fim = parse_date(data_fim_str)
    if not data_inicio or not data_fim:
        return JsonResponse({
            'status': 'ERRO',
            'msg': 'Datas inválidas. Use formato YYYY-MM-DD.'
        }, status=400)

    if data_inicio > data_fim:
        return JsonResponse({
            'status': 'ERRO',
            'msg': 'data_inicio não pode ser maior que data_fim.'
        }, status=400)

    cnpj_limpo = normalizar_cnpj(cnpj)
    empresa = None
    for item in Empresa.objects.filter(ativo=True):
        if normalizar_cnpj(item.cnpj) == cnpj_limpo:
            empresa = item
            break

    if not empresa:
        return JsonResponse({
            'status': 'ERRO',
            'msg': 'Empresa não encontrada para o CNPJ informado.'
        }, status=404)

    if not can_edit_empresa(user, empresa):
        return JsonResponse({
            'status': 'ERRO',
            'msg': 'Permissão negada para iniciar download desta empresa.'
        }, status=403)

    certificado_origem = 'stored'

    if certificado_file:
        if not senha:
            return JsonResponse({
                'status': 'ERRO',
                'msg': 'Senha é obrigatória ao enviar certificado.'
            }, status=400)
        empresa.certificado_arquivo.save(certificado_file.name, certificado_file, save=False)
        empresa.certificado_senha = senha
        empresa.save()
        certificado_origem = 'request'
    elif not empresa.certificado_arquivo or not empresa.certificado_senha:
        return JsonResponse({
            'status': 'ERRO',
            'msg': 'Primeiro acesso requer envio de certificado e senha para esta empresa.'
        }, status=400)

    pasta_destino = os.path.join(
        'media', 'nfse', tipo,
        data_inicio_str[:4], data_inicio_str[5:7]
    )
    pasta_destino = os.path.abspath(pasta_destino)
    os.makedirs(pasta_destino, exist_ok=True)

    tarefa_id = iniciar_download_tarefa(
        empresa=empresa,
        tipo=tipo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        pasta_destino=pasta_destino,
        usuario=pessoa_for_tarefa
    )

    response_data = {
        'status': 'OK',
        'msg': 'Download iniciado com sucesso.',
        'tarefa_id': tarefa_id,
        'empresa_id': empresa.pk,
        'empresa_cnpj': empresa.cnpj,
        'tipo': tipo,
        'data_inicio': data_inicio_str,
        'data_fim': data_fim_str,
        'certificado_origem': certificado_origem,
        'progresso_url': reverse('api_progresso_download', args=[tarefa_id]),
        'progresso_token_url': reverse('api_progresso_download_token', args=[tarefa_id]),
        'detalhe_url': reverse('progresso_download', args=[tarefa_id]),
    }

    if aguardar_zip:
        inicio_espera = time.time()
        tarefa = TarefaDownload.objects.get(pk=tarefa_id)

        while tarefa.status not in ['concluido', 'erro'] and (time.time() - inicio_espera) < timeout_segundos:
            time.sleep(2)
            tarefa.refresh_from_db()

        response_data['status_tarefa'] = tarefa.status
        response_data['progresso'] = tarefa.progresso
        response_data['mensagem_tarefa'] = tarefa.mensagem

        if tarefa.arquivo_zip:
            zip_url = tarefa.arquivo_zip.url
            response_data['zip_url'] = zip_url
            try:
                response_data['zip_url_absoluta'] = request.build_absolute_uri(zip_url)
            except Exception:
                pass
        else:
            response_data['zip_url'] = None
            response_data['aguardando_zip_timeout'] = tarefa.status not in ['concluido', 'erro']

    return JsonResponse(response_data)


@login_required
@csrf_exempt
@require_POST
def api_iniciar_download_parametros(request):
    """
    Inicia download por parâmetros de API:
    - cnpj
    - tipo (emitida/emitidas/recebida/recebidas)
    - data_inicio (YYYY-MM-DD)
    - data_fim (YYYY-MM-DD)
    - certificado (arquivo .pfx/.p12) e senha (opcional se já existir certificado salvo)
    """
    return _iniciar_download_por_parametros(
        request,
        user=request.user,
        pessoa_for_tarefa=request.user.pessoa if hasattr(request.user, 'pessoa') else None,
        aguardar_padrao=False
    )


@csrf_exempt
@require_POST
def api_iniciar_download_parametros_token(request):
    """
    Versão token da API de download.
    Auth: Authorization: Token <token> | Authorization: Bearer <token> | X-Api-Key
    """
    pessoa, erro = _autenticar_pessoa_por_token(request)
    if erro:
        return erro

    return _iniciar_download_por_parametros(
        request,
        user=pessoa.user,
        pessoa_for_tarefa=pessoa,
        aguardar_padrao=True
    )


@csrf_exempt
def api_progresso_download_token(request, tarefa_id):
    """Consulta progresso de tarefa usando token."""
    pessoa, erro = _autenticar_pessoa_por_token(request)
    if erro:
        return erro

    tarefa = get_object_or_404(TarefaDownload, pk=tarefa_id)
    if not pessoa.user.is_superuser and tarefa.usuario != pessoa:
        return JsonResponse({'status': 'ERRO', 'msg': 'Permissão negada.'}, status=403)

    return JsonResponse(_serializar_progresso_tarefa(tarefa))

@login_required
def listar_downloads(request):
    """Lista todos os downloads do usuário"""
    if request.user.is_superuser:
        tarefas = TarefaDownload.objects.all().select_related('empresa', 'usuario')
    elif hasattr(request.user, 'pessoa') and request.user.pessoa.empresas.exists():
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
    if request.method != 'POST':
        return JsonResponse({'status': 'ERRO', 'msg': 'Método inválido'})

    from core.models import Empresa
    from django.core.files import File
    import os

    # Debug dump of request internals to find uploaded file location
    try:
        print('DEBUG request dict keys:', list(request.__dict__.keys()))
        print('DEBUG has _files:', hasattr(request, '_files'))
        if hasattr(request, '_files'):
            print('DEBUG _files:', request._files)
        print('DEBUG has _post:', hasattr(request, '_post'))
        if hasattr(request, '_post'):
            print('DEBUG _post keys:', list(request._post.keys()))
        # dump content type and beginning of stream for diagnostics
        try:
            print('DEBUG CONTENT_TYPE:', request.META.get('CONTENT_TYPE'))
            stream = getattr(request, '_stream', None)
            if stream:
                try:
                    pos = None
                    if hasattr(stream, 'tell'):
                        pos = stream.tell()
                        stream.seek(0)
                    sample = stream.read(200)
                    print('DEBUG stream sample:', sample[:200])
                    if pos is not None:
                        stream.seek(pos)
                except Exception as se:
                    print('DEBUG stream read failed', repr(se))
        except Exception:
            pass
    except Exception as e:
        print('DEBUG request introspect failed:', repr(e))

    # Prefer Django's standard parsing (works with test client and real requests).
    empresa_id = request.POST.get('empresa_id') or request.POST.get('empresa')
    senha = request.POST.get('senha', '')
    certificado_file = request.FILES.get('certificado')

    # If Django didn't populate request.FILES (some test client cases), try
    # parsing from the raw request body safely (catch RawPostDataException).
    try:
        raw_body = request.body
    except RawPostDataException:
        raw_body = None
    try:
        print('DEBUG raw_body_len:', None if raw_body is None else len(raw_body))
    except Exception:
        pass

    if not certificado_file:
        try:
            # try to force Django to populate POST/FILES
            if hasattr(request, '_load_post_and_files'):
                try:
                    request._load_post_and_files()
                except Exception:
                    pass
            certificado_file = request.FILES.get('certificado')
            empresa_id = empresa_id or request.POST.get('empresa_id') or request.POST.get('empresa')
            senha = senha or request.POST.get('senha', senha)
            # fallback to manual parse if still missing
            if not certificado_file:
                import io
                from django.http.multipartparser import MultiPartParser
                stream = getattr(request, '_stream', None)
                # prefer raw_body BytesIO when available (test client provides body)
                if raw_body:
                    parser = MultiPartParser(request.META, io.BytesIO(raw_body), request.upload_handlers)
                elif stream:
                    try:
                        stream.seek(0)
                    except Exception:
                        pass
                    parser = MultiPartParser(request.META, stream, request.upload_handlers)
                else:
                    parser = None
                if parser:
                    post_data, files_data = parser.parse()
                    empresa_id = empresa_id or post_data.get('empresa_id') or post_data.get('empresa')
                    senha = senha or post_data.get('senha', '')
                    if files_data and files_data.get('certificado'):
                        up = files_data.get('certificado')
                        try:
                            certificado_file = up
                        except Exception:
                            certificado_file = up[0]
                # if parser didn't run and there's a non-seekable stream, try reading it fully and parsing
                elif stream:
                    try:
                        body_bytes = stream.read()
                        if body_bytes:
                            parser = MultiPartParser(request.META, io.BytesIO(body_bytes), request.upload_handlers)
                            post_data, files_data = parser.parse()
                            empresa_id = empresa_id or post_data.get('empresa_id') or post_data.get('empresa')
                            senha = senha or post_data.get('senha', '')
                            if files_data and files_data.get('certificado'):
                                up = files_data.get('certificado')
                                try:
                                    certificado_file = up
                                except Exception:
                                    certificado_file = up[0]
                    except Exception:
                        pass
        except Exception as e:
            print('DEBUG upload_certificado_temporario body parse failed:', repr(e))

    if not empresa_id or not certificado_file or not senha:
        print('DEBUG upload_certificado_temporario missing:', {'empresa_id': empresa_id, 'certificado_file': type(certificado_file), 'senha': senha})
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
        except Exception as inner_e:
            print('DEBUG upload_certificado_temporario thumbprint extraction failed:', repr(inner_e))
            pass  # Se não conseguir extrair, continua sem thumbprint

        empresa.save()

        return JsonResponse({
            'status': 'OK',
            'msg': 'Certificado salvo com sucesso!',
            'thumbprint': empresa.certificado_thumbprint
        })

    except Exception as e:
        print('DEBUG upload_certificado_temporario exception:', repr(e))
        return JsonResponse({'status': 'ERRO', 'msg': str(e)})

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

# cache apenas resultados bem sucedidos para evitar memorizar falhas temporárias
_cnpj_cache: dict[str, dict] = {}

def consultar_cnpj_receita(cnpj):
    """Consulta CNPJ usando várias APIs públicas como fallback.

    A primeira resposta válida (status OK) é retornada já convertida para o
    formato interno utilizado pelo resto da aplicação. Se nenhuma API conseguir
    localizar a empresa, retorna um dicionário com status 'ERRO'.

    Resultados com status 'OK' são guardados em um cache simples; erros nunca são
    armazenados, garantindo que tentativas futuras voltem a consultar as APIs.
    """
    # retorno cached
    if cnpj in _cnpj_cache:
        return _cnpj_cache[cnpj]

    # definimos uma lista de tuplas (descrição, url_template, parser_fn)
    apis = []

    def _parse_receitaws(j):
        if not isinstance(j, dict):
            return None
        if j.get('status') == 'OK':
            return {
                'status': 'OK',
                'nome': j.get('nome', ''),
                'fantasia': j.get('fantasia', ''),
                'ie': j.get('ie', ''),
                'im': j.get('im', ''),
                'cep': j.get('cep', ''),
                'logradouro': j.get('logradouro', ''),
                'numero': j.get('numero', ''),
                'bairro': j.get('bairro', ''),
                'municipio': j.get('municipio', ''),
                'uf': j.get('uf', ''),
            }
        return None

    def _parse_brasilapi(j):
        # BrasilAPI às vezes retorna uma string de erro em vez de JSON
        if not isinstance(j, dict):
            return None
        if j.get('cnpj'):
            # ensure logradouro is a dict before calling .get on it
            log = j.get('logradouro')
            if not isinstance(log, dict):
                log = {}
            return {
                'status': 'OK',
                'nome': j.get('razao_social', ''),
                'fantasia': j.get('nome_fantasia', ''),
                'ie': j.get('inscricao_estadual', ''),
                'im': '',
                'cep': log.get('cep', '') or j.get('cep', ''),
                'logradouro': log.get('logradouro', '') or j.get('logradouro', ''),
                'numero': log.get('numero', ''),
                'bairro': log.get('bairro', ''),
                'municipio': j.get('municipio', ''),
                'uf': j.get('uf', ''),
            }
        return None

    def _parse_publica(j):
        if not isinstance(j, dict):
            return None
        if j.get('status') in (200, 'OK'):
            return {
                'status': 'OK',
                'nome': j.get('razao_social', ''),
                'fantasia': j.get('nome_fantasia', ''),
                'ie': j.get('inscricao_estadual', ''),
                'im': j.get('inscricao_municipal', ''),
                'cep': j.get('cep', ''),
                'logradouro': j.get('logradouro', ''),
                'numero': j.get('numero', ''),
                'bairro': j.get('bairro', ''),
                'municipio': j.get('municipio', ''),
                'uf': j.get('uf', ''),
            }
        return None

    apis.append(('ReceitaWS', 'https://www.receitaws.com.br/v1/cnpj/{cnpj}', _parse_receitaws))
    apis.append(('BrasilAPI', 'https://brasilapi.com.br/api/cnpj/v1/{cnpj}', _parse_brasilapi))
    apis.append(('Publica', 'https://publica.cnpj.ws/cnpj/{cnpj}', _parse_publica))

    last_error = None
    for name, tmpl, parser in apis:
        try:
            url = tmpl.format(cnpj=cnpj)
            resp = pyrequests.get(url, timeout=10)
            if resp.status_code == 200:
                try:
                    dados = resp.json()
                except Exception as e:
                    # fallback if JSON decoding fails (sometimes returns plain text)
                    last_error = f"{name} invalid json: {e}"
                    continue
                # coerce to dict so downstream code can't call .get on a string
                if not isinstance(dados, dict):
                    last_error = f"{name} returned non-dict JSON"
                    dados = {}
                try:
                    parsed = parser(dados)
                except Exception as e:
                    last_error = f"{name} parser error: {e}"
                    continue
                if parsed:
                    # cache only successful lookups
                    _cnpj_cache[cnpj] = parsed
                    return parsed
        except Exception as e:
            last_error = f"{name} error: {e}"
            continue

    msg = last_error or 'CNPJ não encontrado'
    return {'status': 'ERRO', 'msg': msg}

# ========== VIEWS DE PESSOAS (USUÁRIOS) ==========

@login_required
@user_passes_test(lambda u: bool(u and not u.is_anonymous))
def pessoa_list(request):
    """Lista todas as pessoas (apenas admin)"""
    from core.permissions import check_perm
    
    # Verificar permissão
    if not check_perm(request.user, 'pessoa.edit'):
        return redirect('home')
    
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

def _can_manage_people(u):
    """Any authenticated user may manage people."""
    return bool(u and not u.is_anonymous)


@login_required
@user_passes_test(lambda u: bool(u and not u.is_anonymous))
def pessoa_create(request):
    """Cria uma nova pessoa (admin)"""
    from core.permissions import check_perm
    
    # Verificar permissão
    if not check_perm(request.user, 'pessoa.create'):
        return redirect('home')
    
    if request.method == 'POST':
        form = PessoaForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                # form.save will create the underlying User and Pessoa
                pessoa = form.save()
            except IntegrityError:
                # usually means username already exists
                form.add_error('username', 'Nome de usuário já existe.')
            else:
                return redirect('pessoa_list')
    else:
        form = PessoaForm()
    
    return render(request, 'core/pessoa_form.html', {'form': form})

@login_required
@user_passes_test(lambda u: bool(u and not u.is_anonymous))
def pessoa_edit(request, pk):
    """Edita uma pessoa existente (admin)"""
    from core.permissions import check_perm
    
    # Verificar permissão
    if not check_perm(request.user, 'pessoa.edit'):
        return redirect('home')
    
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


# ===== SIEG INTEGRAÇÃO =====
@login_required
def sieg_index(request):
    """Dashboard wrapper for SIEG integration. Aggregates key numbers when available.
    Uses the server-configured SIEG API key; no per-user keys or session keys are accepted.
    """
    # This integration uses a global API key from settings or environment.
    # No per-user credential storage is used.

    # Client will read API key from settings or environment automatically
    client = SiegClient()
    tags = client.list_tags_and_paths() or {}

    # Try to fetch certificates count
    certificados_count = 'N/A'
    method, path, meta = client.find_path_for_keyword('Certificado')
    if path and method:
        status, hdrs, body = client.fetch_list(method, path, operation_meta=meta)
        try:
            if status == 200 and isinstance(body, list):
                certificados_count = len(body)
            elif isinstance(body, dict):
                certificados_count = body.get('count') or body.get('total') or 'N/A'
        except Exception:
            pass

    # Try to fetch companies count
    empresas_count = 'N/A'
    empresas_active = 'N/A'
    m2, p2, meta2 = client.find_path_for_keyword('empresa')
    if p2 and m2:
        status, hdrs, body = client.fetch_list(m2, p2, operation_meta=meta2)
        try:
            if status == 200 and isinstance(body, list):
                empresas_count = len(body)
                empresas_active = sum(1 for e in body if (e.get('ativo') or e.get('ativo', True)))
            elif isinstance(body, dict):
                items = body.get('items') or body.get('data') or body.get('result')
                if isinstance(items, list):
                    empresas_count = len(items)
                    empresas_active = sum(1 for e in items if e.get('ativo'))
        except Exception:
            pass

    # Notes / invoices: we list available download endpoints instead of count
    download_endpoints = []
    for tag, eps in tags.items():
        if 'download' in tag.lower() or 'nota' in tag.lower() or 'xml' in tag.lower():
            for method, path, summary in eps:
                download_endpoints.append((method, path, summary))

    openapi_error = False
    if not tags:
        openapi_error = True

    last_checked = timezone.now()

    # also supply a small OpenAPI summary for debugging/inspection in the UI
    openapi = client.get_openapi() or {}
    paths = openapi.get('paths', {})
    openapi_summary = {
        'paths_count': len(paths),
        'sample_paths': list(paths.keys())[:12]
    }

    return render(request, 'core/sieg/index.html', {
        'tags': tags,
        'certificados_count': certificados_count,
        'empresas_count': empresas_count,
        'empresas_active': empresas_active,
        'download_endpoints': download_endpoints,
        'openapi_error': openapi_error,
        'sieg_last_checked': last_checked,
        'openapi_summary': openapi_summary,
    })


@login_required
@require_POST
def sieg_call(request):
    """Proxy a SIEG API call. Expects JSON body with { method, path, params?, json? }.

    Returns JSON with status, headers and body (body may be string or JSON).
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    method = payload.get('method')
    path = payload.get('path')
    params = payload.get('params')
    json_body = payload.get('json')

    if not method or not path:
        return HttpResponseBadRequest('method and path required')

    # build client using session or persisted user key
    client = SiegClient()
    status_code, headers, body = client.request_generic(method, path, params=params, json_body=json_body)

    return JsonResponse({'status_code': status_code, 'headers': headers, 'body': body})


@login_required
def sieg_certificados(request):
    client = SiegClient()

    method, path, meta = client.find_path_for_keyword('Certificado')
    items = []
    error = None
    if path and method:
        status, hdrs, body = client.fetch_list(method, path)
        if status == 200 and isinstance(body, list):
            items = body
        else:
            error = body

    return render(request, 'core/sieg/certificados.html', {'items': items, 'method': method, 'path': path, 'error': error})


@login_required
def sieg_empresas(request):
    client = SiegClient()
    method, path, meta = client.find_path_for_keyword('empresa')
    items = []
    error = None
    if path and method:
        status, hdrs, body = client.fetch_list(method, path)
        if status == 200 and isinstance(body, list):
            items = body
        else:
            error = body

    return render(request, 'core/sieg/empresas.html', {'items': items, 'method': method, 'path': path, 'error': error})


@login_required
def sieg_downloads(request):
    # Use global server-configured key
    client = SiegClient()
    tags = client.list_tags_and_paths() or {}
    download_endpoints = []
    for tag, eps in tags.items():
        if 'download' in tag.lower() or 'nota' in tag.lower() or 'xml' in tag.lower():
            for method, path, summary in eps:
                download_endpoints.append((method, path, summary))

    return render(request, 'core/sieg/downloads.html', {'download_endpoints': download_endpoints})


@login_required
@require_POST
def sieg_execute_download(request):
    """Execute a download endpoint and stream/save the result to media/sieg_downloads/.

    Expects JSON body: { method, path, params?, json? }
    Returns JSON with status and `file_url` when a file was saved, or the API response.
    """
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    method = payload.get('method')
    path = payload.get('path')
    params = payload.get('params')
    json_body = payload.get('json')
    if not method or not path:
        return HttpResponseBadRequest('method and path required')

    client = SiegClient()

    status, headers, resp = client.request_generic(method, path, params=params, json_body=json_body, stream=True)
    if status in (401, 403):
        return JsonResponse({'status': status, 'error': 'Unauthorized / invalid API key'}, status=401)
    if status == 429:
        return JsonResponse({'status': status, 'error': 'Rate limited'}, status=429)
    if status == 0:
        return JsonResponse({'status': status, 'error': resp}, status=500)

    # if resp is a requests.Response (streaming), save content
    try:
        if hasattr(resp, 'iter_content'):
            from django.core.files.base import ContentFile
            from django.core.files.storage import default_storage
            import time
            # determine filename
            cd = headers.get('Content-Disposition') or ''
            filename = None
            if 'filename=' in cd:
                filename = cd.split('filename=')[-1].strip('" ')
            if not filename:
                filename = f'sieg_{int(time.time())}.bin'
            folder = 'sieg_downloads'
            path_on_disk = default_storage.path(folder) if hasattr(default_storage, 'path') else None
            # ensure media folder exists
            dest_path = os.path.join('media', folder, filename)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, 'wb') as w:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        w.write(chunk)
            file_url = '/' + dest_path.replace('\\', '/')
            return JsonResponse({'status': status, 'file_url': file_url})
    except Exception as e:
        logger.exception('Failed to stream/save download: %s', e)
        return JsonResponse({'status': 500, 'error': str(e)}, status=500)

    # fallback: if not streaming, return what we have
    return JsonResponse({'status': status, 'headers': headers, 'body': resp})


@login_required
def sieg_endpoints(request):
    """Show all discovered endpoints and allow executing them via proxy modal."""
    # Use global server-configured key
    client = SiegClient()
    tags = client.list_tags_and_paths() or {}
    return render(request, 'core/sieg/endpoints.html', {'tags': tags})


@login_required
def sieg_tag(request, tag_slug):
    """Render a generic page for a given API tag, showing list-like data when possible."""
    client = SiegClient()

    tags = client.list_tags_and_paths() or {}
    # tag_slug is slugified; try to match by slug or by raw key
    from django.template.defaultfilters import slugify
    match_key = None
    for k in tags.keys():
        if slugify(k) == tag_slug or k.lower() == tag_slug.lower():
            match_key = k
            break

    if not match_key:
        return render(request, 'core/sieg/tag.html', {'tag': tag_slug, 'items': [], 'error': 'Tag não encontrada'})

    endpoints = tags.get(match_key, [])
    # choose a GET endpoint if present
    method = None
    path = None
    for m, p, s in endpoints:
        if m.upper() == 'GET':
            method = m; path = p; break
    if not path and endpoints:
        method, path, _ = endpoints[0]

    items = []
    error = None
    if path and method:
        status, hdrs, body = client.fetch_list(method, path)
        if status == 200 and isinstance(body, list):
            items = body
        else:
            error = body

    return render(request, 'core/sieg/tag.html', {'tag': match_key, 'items': items, 'method': method, 'path': path, 'error': error})

# ========== VIEWS DE EMPRESAS ==========

@login_required
def empresa_list(request):
    """Lista empresas com filtros"""
    q = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '')
    status = request.GET.get('status', '')
    
    # Qualquer usuário autenticado vê todas as empresas
    empresas = Empresa.objects.all()
    
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

    # se veio show_upload na URL, requer upload; por padrão o certificado é opcional
    require_pfx = bool(request.GET.get('show_upload') == '1')

    if request.method == 'POST':
        # Lê valores básicos do POST (usados para processar certificado e API)
        cnpj = request.POST.get('cnpj', '').replace('.', '').replace('/', '').replace('-', '')
        certificado_file = request.FILES.get('certificado')
        certificado_senha = request.POST.get('certificado_senha', '')

        # Se o fluxo exige PFX por show_upload, valide a presença do arquivo
        if require_pfx and not certificado_file:
            msg = 'Upload do arquivo .pfx é obrigatório para este certificado.'
        # Validações básicas
        elif not cnpj:
            msg = 'CNPJ é obrigatório.'
        # se enviou certificado sem senha, avise
        elif certificado_file and not certificado_senha:
            msg = 'Senha do certificado é obrigatória quando um arquivo for enviado.'
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
                        'certificado_antigo': False,
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

    # filtros de intervalo
    start = request.GET.get('start')
    end = request.GET.get('end')
    notas = empresa.notas.all()
    if start:
        notas = notas.filter(data_emissao__gte=start)
    if end:
        notas = notas.filter(data_emissao__lte=end)
    total_notas = notas.count()
    total_valor = float(notas.aggregate(models.Sum('valor'))['valor__sum'] or 0)
    recentes = notas.order_by('-data_emissao')[:10]

    # impostos agregados
    impostos_totais = {}
    for n in notas:
        if n.impostos:
            for key, val in n.impostos.items():
                impostos_totais[key] = impostos_totais.get(key, 0) + (val or 0)

    # Top fornecedores (tomador_nome)
    top_fornecedores = (
        notas.values('tomador_nome')
             .annotate(total=models.Count('id'), soma=models.Sum('valor'))
             .order_by('-total')[:10]
    )

    # consumo por fornecedor completo (utilizado para ABC curve)
    fornecedores_consumo = (
        notas.values('tomador_nome')
             .annotate(qtd=models.Count('id'), soma=models.Sum('valor'))
             .order_by('-soma')
    )

    # distribuição por tipo (entrada/saida)
    tipo_dist = (
        notas.values('tipo')
             .annotate(qtd=models.Count('id'), soma=models.Sum('valor'))
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
        'fornecedores_consumo': fornecedores_consumo,
        'tipo_dist': tipo_dist,
        'meses': meses,
        'impostos_totais': impostos_totais,
        'filter_start': start,
        'filter_end': end,
    })

@login_required
def empresa_certificado(request):
    """Cadastro de empresa usando certificado da loja do Windows"""
    msg = None
    certificados = listar_certificados_windows()

    # Qualquer usuário autenticado vê todas as empresas ativas
    empresas = Empresa.objects.filter(ativo=True)
    
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
                # Se a empresa não tem PFX salvo, tente exportar e salvar o .pfx automaticamente
                try:
                    if not empresa.certificado_arquivo:
                        from .certificado_service import exportar_certificado_pfx
                        pfx_path, senha_export = exportar_certificado_pfx(thumbprint)
                        from django.core.files import File as DjangoFile
                        with open(pfx_path, 'rb') as pf:
                            empresa.certificado_arquivo.save(os.path.basename(pfx_path), DjangoFile(pf), save=False)
                        empresa.certificado_senha = senha_export or ''
                        empresa.save()
                        try:
                            os.remove(pfx_path)
                        except Exception:
                            pass
                except Exception as e:
                    # não interrompe o fluxo principal se export falhar
                    print('DEBUG auto-save pfx failed:', repr(e))
                
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
    elif hasattr(request.user, 'pessoa') and request.user.pessoa.empresas.exists():
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
    
    # Qualquer usuário autenticado vê todas as empresas ativas
    form.fields['empresa'].queryset = Empresa.objects.filter(ativo=True)
    
    return render(request, 'core/agendamento_form.html', {'form': form})

@login_required
def agendamento_edit(request, pk):
    """Edita agendamento existente"""
    agendamento = get_object_or_404(Agendamento, pk=pk)
    
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
    def _build_unique_placeholder_cpf(user_id):
        # CPF técnico para perfis criados automaticamente (11 dígitos)
        # Ex.: id=7 -> 90000000007
        base = f"9{int(user_id or 0):010d}"
        cpf = base[:11]
        while Pessoa.objects.filter(cpf=cpf).exists():
            cpf = ''.join(secrets.choice('0123456789') for _ in range(11))
        return cpf

    pessoa = getattr(request.user, 'pessoa', None)

    if not pessoa:
        try:
            pessoa = Pessoa.objects.create(
                user=request.user,
                cpf=_build_unique_placeholder_cpf(request.user.id),
                ativo=bool(request.user.is_active),
            )
        except Exception as e:
            return JsonResponse({'status': 'ERRO', 'msg': f'Falha ao criar perfil da pessoa: {str(e)}'}, status=500)

    try:
        token = secrets.token_hex(32)
        pessoa.client_api_token = token
        pessoa.save(update_fields=['client_api_token'])
        return JsonResponse({'status': 'OK', 'token': token})
    except Exception as e:
        return JsonResponse({'status': 'ERRO', 'msg': f'Falha ao gerar token: {str(e)}'}, status=500)


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
def home(request):
    """Página inicial (home) com atalhos e informações gerais."""
    now = timezone.now()
    return render(request, 'core/home.html', {
        'now': now,
    })


@login_required
def dashboard(request):
    """BI/dashboard estatístico de downloads, empresas, etc (acesso via link 'Dashboard')."""
    now = timezone.now()
    total_mes = HistoricoDownload.objects.filter(
        data_inicio__year=now.year,
        data_inicio__month=now.month
    ).aggregate(total=models.Sum('quantidade_sucesso'))['total'] or 0
    # Últimos 10 downloads
    historico = HistoricoDownload.objects.select_related('empresa').order_by('-data_inicio')[:10]
    # Empresas do usuário
    if request.user.is_superuser:
        empresas = Empresa.objects.filter(ativo=True)
    elif hasattr(request.user, 'pessoa') and request.user.pessoa.empresas.exists():
        empresas = request.user.pessoa.empresas.filter(ativo=True)
    else:
        empresas = Empresa.objects.filter(ativo=True)
    return render(request, 'core/dashboard.html', {
        'total_mes': total_mes,
        'historico': historico,
        'empresas': empresas,
        'now': now,
    })

@login_required
def historico(request):
    """Histórico completo de downloads"""
    if request.user.is_superuser:
        historico = HistoricoDownload.objects.select_related('empresa').order_by('-data_inicio')
    elif hasattr(request.user, 'pessoa') and request.user.pessoa.empresas.exists():
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
    # Qualquer usuário autenticado vê todas as empresas ativas
    empresas = Empresa.objects.filter(ativo=True)

    return render(request, 'core/certificado_list.html', {'certificados': certificados, 'empresas': empresas})


@login_required
def empresa_search(request):
    """AJAX endpoint: search empresas by q (cnpj, nome, razao_social)."""
    q = request.GET.get('q', '').strip()
    results = []
    if q:
        qs = Empresa.objects.filter(
            models.Q(nome_fantasia__icontains=q) | models.Q(razao_social__icontains=q) | models.Q(cnpj__icontains=q)
        )[:200]
        for e in qs:
            results.append({
                'id': e.pk,
                'nome': e.nome_fantasia,
                'razao': e.razao_social,
                'cnpj': e.cnpj,
                'inscricao_municipal': e.inscricao_municipal,
                'inscricao_estadual': e.inscricao_estadual,
                'tipo': e.tipo,
                'cep': e.cep,
                'logradouro': e.logradouro,
                'numero': e.numero,
                'complemento': e.complemento,
                'bairro': e.bairro,
                'municipio': e.municipio,
                'uf': e.uf,
            })
    else:
        # provide a small mock example to help UX when no companies exist
        results = [
            {'id': 0, 'nome': 'ACME Ltda', 'razao': 'ACME Indústria', 'cnpj': '00000000000000', 'inscricao_municipal': '', 'inscricao_estadual': '', 'tipo': 'matriz', 'cep': '', 'logradouro': '', 'numero': '', 'complemento': '', 'bairro': '', 'municipio': '', 'uf': ''},
            {'id': 0, 'nome': 'Exemplo SA', 'razao': 'Empresa Exemplo', 'cnpj': '11111111000111', 'inscricao_municipal': '', 'inscricao_estadual': '', 'tipo': 'matriz', 'cep': '', 'logradouro': '', 'numero': '', 'complemento': '', 'bairro': '', 'municipio': '', 'uf': ''},
        ]
    return JsonResponse({'results': results})


def can_manage_departamento(user):
    """Permission helper: who can manage departments.

    Superusers or users with explicit painel.manage_departamento permission.
    """
    if not user or getattr(user, 'is_anonymous', True):
        return False
    if user.is_superuser or getattr(user, 'is_staff', False):
        return True
    pessoa = getattr(user, 'pessoa', None)
    if pessoa and pessoa.has_perm_code('painel.manage_departamento'):
        return True
    return False


@login_required
def departamento_list(request):
    if not can_manage_departamento(request.user):
        return HttpResponseForbidden('Permissão negada')
    from .models import Departamento
    departamentos = Departamento.objects.all()
    return render(request, 'core/painel/departamento_list.html', {'departamentos': departamentos})


@login_required
def departamento_create(request):
    if not can_manage_departamento(request.user):
        return HttpResponseForbidden('Permissão negada')
    from .models import Departamento, Analista
    from django.contrib.auth.models import User
    users = User.objects.all()
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        if not nome:
            messages.error(request, 'Nome do departamento é obrigatório.')
            return render(request, 'core/painel/departamento_form.html', {'departamento': None, 'users': users})
        d = Departamento.objects.create(nome=nome)
        ids = request.POST.getlist('analistas')
        # assign selected users as Analista for this department
        selected = set(int(x) for x in ids if x.isdigit())
        for uid in selected:
            try:
                u = User.objects.get(pk=uid)
            except User.DoesNotExist:
                continue
            analista, created = Analista.objects.get_or_create(user=u, defaults={'departamento': d})
            if not created and analista.departamento_id != d.id:
                analista.departamento = d
                analista.save()
        messages.success(request, 'Departamento criado com sucesso.')
        return redirect('painel:departamento_list')
    return render(request, 'core/painel/departamento_form.html', {'departamento': None, 'users': users})


@login_required
def departamento_edit(request, pk):
    if not can_manage_departamento(request.user):
        return HttpResponseForbidden('Permissão negada')
    from .models import Departamento, Analista
    from django.contrib.auth.models import User
    departamento = get_object_or_404(Departamento, pk=pk)
    users = User.objects.all()
    if request.method == 'POST':
        nome = (request.POST.get('nome') or '').strip()
        if not nome:
            messages.error(request, 'Nome do departamento é obrigatório.')
            return render(request, 'core/painel/departamento_form.html', {'departamento': departamento, 'users': users})
        departamento.nome = nome
        departamento.save()
        ids = request.POST.getlist('analistas')
        selected = set(int(x) for x in ids if x.isdigit())
        # assign selected users as analistas for this department
        for uid in selected:
            try:
                u = User.objects.get(pk=uid)
            except User.DoesNotExist:
                continue
            analista, created = Analista.objects.get_or_create(user=u, defaults={'departamento': departamento})
            if not created and analista.departamento_id != departamento.id:
                analista.departamento = departamento
                analista.save()
        # remove Analista rows for users that were unselected (department field is non-nullable)
        Analista.objects.filter(departamento=departamento).exclude(user__pk__in=selected).delete()
        messages.success(request, 'Departamento atualizado.')
        return redirect('painel:departamento_list')
    return render(request, 'core/painel/departamento_form.html', {'departamento': departamento, 'users': users})


@login_required
def painel_department_api(request, departamento_id):
    """Return JSON payload with analistas and atendimentos for a department."""
    from .models import Departamento, Analista, Atendimento
    departamento = get_object_or_404(Departamento, pk=departamento_id)
    analistas_qs = Analista.objects.filter(departamento=departamento)
    atendimentos_qs = Atendimento.objects.filter(departamento=departamento).order_by('criado_em')[:200]
    analistas = []
    for a in analistas_qs:
        analistas.append({'id': a.pk, 'name': a.user.get_full_name() or a.user.username, 'disponivel': bool(a.disponivel)})
    atendimentos = []
    for at in atendimentos_qs:
        # Do not expose company name for pure pending items (only show after claimed)
        empresa_field = at.empresa if getattr(at, 'status', None) and at.status != 'pendente' else None
        atendimentos.append({
            'id': at.pk,
            'empresa': empresa_field,
            'motivo': at.motivo,
            'status': at.status,
            'criado_em': at.criado_em.isoformat() if at.criado_em else None,
            'iniciado_em': at.iniciado_em.isoformat() if at.iniciado_em else None,
            'finalizado_em': at.finalizado_em.isoformat() if at.finalizado_em else None,
            'analista': {'id': at.analista.pk, 'name': at.analista.user.get_full_name()} if getattr(at, 'analista', None) else None,
        })
    return JsonResponse({'departamento': {'id': departamento.pk, 'nome': departamento.nome}, 'analistas': analistas, 'atendimentos': atendimentos}, encoder=DjangoJSONEncoder)


@login_required
def api_state_counts(request):
    """Return JSON counts of atendimentos grouped by empresa.uf (state).
    Optional GET params: departamento, status, start_date (YYYY-MM-DD), end_date (YYYY-MM-DD)
    """
    qs = Atendimento.objects.all()
    departamento = request.GET.get('departamento')
    status = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if departamento and departamento.isdigit():
        qs = qs.filter(departamento_id=int(departamento))
    if status:
        qs = qs.filter(status=status)
    if start_date:
        sd = parse_date(start_date)
        if sd:
            qs = qs.filter(criado_em__date__gte=sd)
    if end_date:
        ed = parse_date(end_date)
        if ed:
            qs = qs.filter(criado_em__date__lte=ed)

    agg = qs.values(state= models.F('empresa__uf')).annotate(count=Count('pk')).order_by('-count')
    labels = []
    data = []
    for row in agg:
        state = row.get('state') or '—'
        labels.append(state)
        data.append(row.get('count') or 0)
    return JsonResponse({'labels': labels, 'data': data})


@login_required
def api_monthly_counts(request):
    """Return JSON monthly counts of atendimentos (YYYY-MM) optionally filtered.
    Optional GET params: departamento, status, months (int), start_date, end_date
    """
    qs = Atendimento.objects.all()
    departamento = request.GET.get('departamento')
    status = request.GET.get('status')
    months = request.GET.get('months')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    if departamento and departamento.isdigit():
        qs = qs.filter(departamento_id=int(departamento))
    if status:
        qs = qs.filter(status=status)
    if start_date:
        sd = parse_date(start_date)
        if sd:
            qs = qs.filter(criado_em__date__gte=sd)
    if end_date:
        ed = parse_date(end_date)
        if ed:
            qs = qs.filter(criado_em__date__lte=ed)

    qs = qs.annotate(month=TruncMonth('criado_em')).values('month').annotate(count=Count('pk')).order_by('month')
    labels = []
    data = []
    for row in qs:
        m = row.get('month')
        if m:
            labels.append(m.strftime('%Y-%m'))
        else:
            labels.append('—')
        data.append(row.get('count') or 0)
    return JsonResponse({'labels': labels, 'data': data})


@login_required
def api_users(request):
    """Return small JSON list of users for chat selector."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    # Support simple query filter used by the chat modal (param: q)
    q = (request.GET.get('q') or '').strip()
    from django.db.models import Q

    if q:
        # Try to match against user name/username/email or linked Pessoa (cpf)
        users = User.objects.filter(is_active=True).filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(username__icontains=q) |
            Q(email__icontains=q) |
            Q(pessoa__cpf__icontains=q)
        ).distinct().order_by('first_name', 'username')[:100]
    else:
        # Default: return active users linked to a Pessoa (historic behaviour)
        users = User.objects.filter(is_active=True, pessoa__isnull=False).order_by('first_name', 'username')[:500]

    out = [{'id': u.pk, 'name': (u.get_full_name() or u.username)} for u in users]
    # enrich with Pessoa info when available so frontend can show employee details
    enriched = []
    for u in users:
        entry = {'id': u.pk, 'name': (u.get_full_name() or u.username)}
        try:
            p = getattr(u, 'pessoa', None)
            if p:
                entry['pessoa'] = {'id': p.pk, 'nome': p.nome}
        except Exception:
            pass
        enriched.append(entry)
    return JsonResponse({'users': enriched})


@login_required
def api_pessoas(request):
    """Search `Pessoa` records for chat modal (returns employees)."""
    q = (request.GET.get('q') or '').strip()
    from .models import Pessoa
    results = []
    if q:
        qs = Pessoa.objects.filter(
            models.Q(user__first_name__icontains=q)
            | models.Q(user__last_name__icontains=q)
            | models.Q(user__username__icontains=q)
            | models.Q(cpf__icontains=q)
        ).select_related('user')[:50]
    else:
        qs = Pessoa.objects.select_related('user').all()[:50]
    for p in qs:
        results.append({
            'id': p.pk,
            'nome': p.nome,
            'usuario_id': p.user.id if getattr(p, 'user', None) else None,
        })
    return JsonResponse({'results': results})


@csrf_exempt
def create_user_conversation(request):
    """Create or return an existing conversation between current user and another user.

    Expects JSON body: { user_id: <id> }
    Returns: { conversation_id: <id> }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'auth'}, status=401)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        other_id = int(payload.get('user_id'))
    except Exception:
        return JsonResponse({'error': 'invalid'}, status=400)

    from .models import Conversation, ConversationParticipant
    from django.contrib.auth import get_user_model
    User = get_user_model()

    # Validate target user exists
    try:
        other = User.objects.get(pk=other_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'user_not_found'}, status=404)

    # Try to find existing direct conversation between the two users (no empresa)
    qs = Conversation.objects.filter(empresa__isnull=True, participants__user=request.user).filter(participants__user__id=other_id)
    if qs.exists():
        conv = qs.first()
    else:
        conv = Conversation.objects.create(title='')
        ConversationParticipant.objects.create(conversation=conv, user=request.user)
        ConversationParticipant.objects.create(conversation=conv, user=other)

    return JsonResponse({'conversation_id': conv.id})


@csrf_exempt
def create_empresa_conversation(request):
    """Create a conversation linked to a company (empresa).

    Expects JSON body: { empresa_id: <id> }
    Returns: { conversation_id: <id> }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'auth'}, status=401)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        empresa_id = int(payload.get('empresa_id'))
    except Exception:
        return JsonResponse({'error': 'invalid'}, status=400)

    from .models import Conversation, ConversationParticipant, Empresa
    emp = get_object_or_404(Empresa, pk=empresa_id)
    # Try to find existing conversation for this empresa where the user participates
    qs = Conversation.objects.filter(empresa=emp, participants__user=request.user).distinct()
    if qs.exists():
        conv = qs.first()
    else:
        conv = Conversation.objects.create(empresa=emp, title='')
        ConversationParticipant.objects.create(conversation=conv, user=request.user)
    return JsonResponse({'conversation_id': conv.id})


@login_required
def mark_conversation_read(request):
    """Mark a conversation as read for current user. Expects JSON body { conversation_id: <id> }.
    Returns { marked: <n> } number of messages marked as read.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
        conv_id = int(payload.get('conversation_id'))
    except Exception:
        return JsonResponse({'error': 'invalid'}, status=400)

    from .models import ConversationParticipant, ConversationMessage, Conversation
    try:
        conv = Conversation.objects.get(pk=conv_id)
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'notfound'}, status=404)

    try:
        part = ConversationParticipant.objects.get(conversation=conv, user=request.user)
    except ConversationParticipant.DoesNotExist:
        return JsonResponse({'error': 'noparticipant'}, status=403)

    from django.utils import timezone
    old = part.last_read
    now = timezone.now()
    # count messages newer than previous last_read
    if old:
        marked = ConversationMessage.objects.filter(conversation=conv, criado_em__gt=old).count()
    else:
        marked = ConversationMessage.objects.filter(conversation=conv).count()
    part.last_read = now
    part.save(update_fields=['last_read'])
    return JsonResponse({'marked': marked})


@login_required
def user_conversations(request):
    """Return recent conversations for the current user."""
    from .models import Conversation, ConversationMessage, ConversationParticipant
    user = request.user
    # Only show direct user-to-user conversations in the floating panel (no empresa-linked conversations)
    # order by last activity if available
    if hasattr(Conversation, 'atualizado_em'):
        qs = Conversation.objects.filter(empresa__isnull=True, participants__user=user).distinct().order_by('-atualizado_em')
    else:
        qs = Conversation.objects.filter(empresa__isnull=True, participants__user=user).distinct().order_by('-id')
    out = []
    for c in qs[:50]:
        last = ConversationMessage.objects.filter(conversation=c).order_by('-criado_em').first()
        parts = [p.user.get_full_name() or p.user.username for p in c.participants.all()]
        out.append({
            'id': c.id,
            'title': c.title or (c.empresa.nome_fantasia if getattr(c, 'empresa', None) else None) or ', '.join(parts[:3]),
            'empresa_id': c.empresa.id if getattr(c, 'empresa', None) else None,
            'last_message': last.message if last else None,
            'last_time': last.criado_em.isoformat() if last else None,
            'participants': parts,
        })
    return JsonResponse({'conversations': out})


@login_required
def api_messages(request, room_id):
    """Return message history for a room.

    - `room_id` can be `conv-<id>` (direct/company conversation) or `at-<id>` (atendimento).
    """
    from .models import Conversation, ConversationMessage, ConversationParticipant, ChatMessage, Atendimento

    room = str(room_id or '').strip()
    if not room:
        return JsonResponse([], safe=False)

    # Conversation history
    if room.startswith('conv-'):
        try:
            conv_id = int(room.split('-')[1])
        except Exception:
            return JsonResponse({'error': 'invalid_room'}, status=400)

        is_participant = ConversationParticipant.objects.filter(conversation_id=conv_id, user=request.user).exists()
        if not is_participant:
            return JsonResponse({'error': 'forbidden'}, status=403)

        msgs = ConversationMessage.objects.filter(conversation_id=conv_id).select_related('user').order_by('criado_em')
        data = [{
            'user': ((m.user.get_full_name() or m.user.username) if m.user else 'Anônimo'),
            'message': m.message,
            'time': m.criado_em.strftime('%H:%M'),
            'created': m.criado_em.isoformat(),
            'own': bool(m.user_id == request.user.id),
            'attachments': (m.attachments if hasattr(m, 'attachments') else []),
        } for m in msgs]
        return JsonResponse(data, safe=False)

    # Atendimento history
    if room.startswith('at-'):
        at_id = room.split('-', 1)[1]
    else:
        at_id = room

    atendimento = Atendimento.objects.filter(pk=at_id).first()
    if not atendimento:
        return JsonResponse({'error': 'not_found'}, status=404)

    # basic access guard: owner company user, assigned analyst, or superuser
    pessoa = getattr(request.user, 'pessoa', None)
    analista = getattr(request.user, 'analista', None)
    can_access = bool(request.user.is_superuser)
    if not can_access and analista and atendimento.analista_id and analista.id == atendimento.analista_id:
        can_access = True
    if not can_access and pessoa and atendimento.empresa_obj_id:
        can_access = atendimento.empresa_obj.usuarios.filter(pk=pessoa.pk).exists()
    if not can_access:
        return JsonResponse({'error': 'forbidden'}, status=403)

    msgs = ChatMessage.objects.filter(atendimento_id=str(at_id)).select_related('user').order_by('criado_em')
    data = [{
        'user': ((m.user.get_full_name() or m.user.username) if m.user else 'Anônimo'),
        'message': m.message,
        'time': m.criado_em.strftime('%H:%M'),
        'created': m.criado_em.isoformat(),
        'own': bool(m.user_id == request.user.id),
        'attachments': [],
    } for m in msgs]
    return JsonResponse(data, safe=False)


@login_required
@csrf_exempt
def upload_attachments(request):
    """Upload files for chat and return metadata for websocket payload."""
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)

    files = request.FILES.getlist('files')
    if not files:
        return JsonResponse({'files': []})

    uploaded = []
    for f in files[:15]:
        try:
            path = default_storage.save(f'chat_anexos/{timezone.now().strftime("%Y/%m/%d")}/{f.name}', f)
            uploaded.append({
                'name': f.name,
                'size': f.size,
                'type': (getattr(f, 'content_type', '') or 'application/octet-stream'),
                'url': default_storage.url(path),
            })
        except Exception:
            continue

    return JsonResponse({'files': uploaded})


@login_required
@csrf_exempt
def create_group_conversation(request):
    """Create a group conversation.

    Body: { title: str, user_ids: [int, ...] }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'method'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        payload = {}

    title = (payload.get('title') or '').strip()[:200]
    user_ids = payload.get('user_ids') or []
    if not isinstance(user_ids, list):
        return JsonResponse({'error': 'invalid_user_ids'}, status=400)

    from .models import Conversation, ConversationParticipant
    from django.contrib.auth import get_user_model
    User = get_user_model()

    unique_ids = set()
    for uid in user_ids:
        try:
            unique_ids.add(int(uid))
        except Exception:
            pass

    conv = Conversation.objects.create(title=title or 'Grupo')
    ConversationParticipant.objects.get_or_create(conversation=conv, user=request.user)
    for uid in unique_ids:
        if uid == request.user.id:
            continue
        u = User.objects.filter(pk=uid, is_active=True).first()
        if u:
            ConversationParticipant.objects.get_or_create(conversation=conv, user=u)

    return JsonResponse({'conversation_id': conv.id})


@login_required
def push_test_notification(request, user_id):
    """Debug endpoint: send a test push to a given user via the user-notifier group."""
    from channels.layers import get_channel_layer
    try:
        uid = int(user_id)
    except Exception:
        return JsonResponse({'error': 'invalid_user'}, status=400)
    channel_layer = get_channel_layer()
    payload = {
        'type': 'chat_message',
        'message': 'Teste de notificação',
        'user': request.user.get_username(),
        'created': timezone.now().isoformat(),
        'conversation_id': None
    }
    try:
        from asgiref.sync import async_to_sync
        async_to_sync(channel_layer.group_send)(f'chat_user-{uid}', payload)
    except Exception:
        # best-effort: ignore errors
        pass
    return JsonResponse({'sent': True})


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

        if not thumbprint:
            return JsonResponse({'status': 'ERRO', 'msg': 'Parâmetros insuficientes.'})

        empresa = None
        if empresa_id:
            empresa = get_object_or_404(Empresa, pk=empresa_id)
        else:
            # se não informou empresa, tenta usar a empresa única do usuário
            if hasattr(request.user, 'pessoa'):
                empresas_user = list(request.user.pessoa.empresas.all())
                if len(empresas_user) == 1:
                    empresa = empresas_user[0]
        if not empresa:
            return JsonResponse({'status': 'ERRO', 'msg': 'Empresa não informada e não foi possível determinar uma empresa destino.'})

        # Permissão
        from .permissions import can_manage_certificado
        if not can_manage_certificado(request.user, empresa):
            return JsonResponse({'status': 'ERRO', 'msg': 'Permissão negada.'})

        try:
            from .certificado_service import exportar_certificado_pfx
            pfx_path, senha_export = exportar_certificado_pfx(thumbprint)

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

            empresa.certificado_senha = senha_export or ''
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

    msg = None
    if request.method == 'POST':
        certificado_file = None
        certificado_senha = None

        # Prefer standard Django parsing first.
        certificado_senha = request.POST.get('certificado_senha', '')
        certificado_file = request.FILES.get('certificado')

        # If Django didn't populate request.FILES (test client edge cases),
        # try parsing from the raw request body safely (catch RawPostDataException).
        try:
            raw_body = request.body
        except RawPostDataException:
            raw_body = None

        if not certificado_file:
            try:
                # try to force Django to populate POST/FILES
                if hasattr(request, '_load_post_and_files'):
                    try:
                        request._load_post_and_files()
                    except Exception:
                        pass
                certificado_file = request.FILES.get('certificado')
                certificado_senha = certificado_senha or request.POST.get('certificado_senha', certificado_senha)
                # fallback to manual parse if still not present
                if not certificado_file:
                    import io
                    from django.http.multipartparser import MultiPartParser
                    stream = getattr(request, '_stream', None)
                    if stream:
                        try:
                            stream.seek(0)
                        except Exception:
                            pass
                        parser = MultiPartParser(request.META, stream, request.upload_handlers)
                    elif raw_body:
                        parser = MultiPartParser(request.META, io.BytesIO(raw_body), request.upload_handlers)
                    else:
                        parser = None
                    if parser:
                        post_data, files_data = parser.parse()
                        certificado_senha = certificado_senha or post_data.get('certificado_senha', '')
                        if files_data and files_data.get('certificado'):
                            up = files_data.get('certificado')
                            try:
                                certificado_file = up
                                filename = up.name
                            except Exception:
                                certificado_file = up[0]
                                filename = up[0].name
            except Exception as e:
                print('DEBUG certificado_edit body parse failed:', repr(e))

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