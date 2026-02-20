"""
Views para o Conversor Universal de Arquivos
Integrado ao HDowloader
"""
import os
import json
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages

from .models import ArquivoConversao, Pessoa
from .conversor_service import converter_arquivo, get_formatos_destino


@login_required
def conversor_index(request):
    """Página principal do conversor"""
    # Buscar conversões recentes do usuário
    if hasattr(request.user, 'pessoa'):
        conversoes = ArquivoConversao.objects.filter(
            usuario=request.user.pessoa
        ).order_by('-data_criacao')[:10]
    else:
        conversoes = []
    
    return render(request, 'core/conversor/index.html', {
        'conversoes': conversoes
    })


@login_required
@csrf_exempt
def upload_arquivo(request):
    """Upload de arquivo para conversão"""
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    arquivo = request.FILES.get('arquivo')
    formato_destino = request.POST.get('formato_destino')

    if not arquivo or not formato_destino:
        return JsonResponse({'erro': 'Arquivo e formato destino são obrigatórios'}, status=400)

    # Validar tamanho (limite de 50MB)
    if arquivo.size > 50 * 1024 * 1024:
        return JsonResponse({'erro': 'Arquivo muito grande. Limite: 50MB'}, status=400)

    # Determinar formato de origem
    nome_arquivo = arquivo.name
    formato_origem = os.path.splitext(nome_arquivo)[1].lower().replace('.', '')

    # Validar se o formato_destino é aceito para o formato de origem
    formatos_validos = get_formatos_destino(formato_origem)
    if formato_destino not in formatos_validos:
        return JsonResponse({'erro': f'Formato destino inválido para {formato_origem}'}, status=400)

    try:
        # Criar registro no banco (salva primeiro para garantir PK antes de gravar arquivo)
        conversao = ArquivoConversao(
            usuario=request.user.pessoa if hasattr(request.user, 'pessoa') else None,
            nome_original=nome_arquivo,
            formato_origem=formato_origem,
            formato_destino=formato_destino,
            tamanho_original=arquivo.size,
            status='pendente'
        )
        conversao.save()

        # Salvar arquivo original
        conversao.arquivo_original.save(arquivo.name, arquivo, save=True)

        return JsonResponse({
            'id': conversao.id,
            'status': 'pendente',
            'mensagem': 'Arquivo recebido com sucesso'
        })

    except Exception as e:
        # Tentativa de cleanup em caso de falha parcial
        try:
            if 'conversao' in locals() and conversao.pk:
                conversao.arquivo_original.delete(save=False)
                conversao.delete()
        except:
            pass
        return JsonResponse({'erro': str(e)}, status=500)


@login_required
def processar_conversao(request, conversao_id):
    """Processa a conversão de um arquivo"""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)
    
    # Verificar permissão (centralizada)
    from .permissions import can_use_conversor
    if not can_use_conversor(request.user, conversao):
        return JsonResponse({'erro': 'Permissão negada'}, status=403)
    
    # Se já foi convertido, retornar sucesso
    if conversao.status == 'concluido' and conversao.arquivo_convertido:
        return JsonResponse({
            'id': conversao.id,
            'status': 'concluido',
            'url': conversao.arquivo_convertido.url,
            'tamanho': conversao.tamanho_convertido
        })
    
    # Atualizar status
    conversao.status = 'convertendo'
    conversao.save()
    
    # Caminho do arquivo original
    caminho_original = conversao.arquivo_original.path
    
    # Criar diretório temporário para conversão
    import tempfile
    import shutil
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Converter o arquivo
            arquivo_convertido, erro = converter_arquivo(
                caminho_original,
                conversao.formato_destino,
                temp_dir
            )
            
            if arquivo_convertido and os.path.exists(arquivo_convertido):
                # Salvar arquivo convertido
                from django.core.files.base import ContentFile
                
                with open(arquivo_convertido, 'rb') as f:
                    nome_convertido = f"{os.path.splitext(conversao.nome_original)[0]}.{conversao.formato_destino}"
                    conversao.arquivo_convertido.save(nome_convertido, ContentFile(f.read()), save=True)
                
                conversao.status = 'concluido'
                conversao.tamanho_convertido = os.path.getsize(arquivo_convertido)
                conversao.data_conversao = datetime.now()
                conversao.save()
                
                return JsonResponse({
                    'id': conversao.id,
                    'status': 'concluido',
                    'url': conversao.arquivo_convertido.url,
                    'tamanho': conversao.tamanho_convertido
                })
            else:
                conversao.status = 'erro'
                conversao.mensagem_erro = erro or 'Erro desconhecido na conversão'
                conversao.save()
                
                return JsonResponse({
                    'id': conversao.id,
                    'status': 'erro',
                    'erro': conversao.mensagem_erro
                })
                
        except Exception as e:
            conversao.status = 'erro'
            conversao.mensagem_erro = str(e)
            conversao.save()
            
            return JsonResponse({
                'id': conversao.id,
                'status': 'erro',
                'erro': str(e)
            })


@login_required
def status_conversao(request, conversao_id):
    """Retorna o status de uma conversão"""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)
    
    # Verificar permissão (centralizada)
    from .permissions import can_use_conversor
    if not can_use_conversor(request.user, conversao):
        return JsonResponse({'erro': 'Permissão negada'}, status=403)
    
    data = {
        'id': conversao.id,
        'status': conversao.status,
        'nome_original': conversao.nome_original,
        'formato_origem': conversao.formato_origem,
        'formato_destino': conversao.formato_destino,
        'tamanho_original': conversao.tamanho_original,
        'tamanho_convertido': conversao.tamanho_convertido,
        'data_criacao': conversao.data_criacao.strftime('%d/%m/%Y %H:%M'),
        'data_conversao': conversao.data_conversao.strftime('%d/%m/%Y %H:%M') if conversao.data_conversao else None,
        'mensagem_erro': conversao.mensagem_erro,
    }
    
    if conversao.arquivo_convertido:
        data['url_download'] = conversao.arquivo_convertido.url
    
    return JsonResponse(data)


@login_required
def historico_conversoes(request):
    """Lista o histórico de conversões do usuário"""
    if request.user.is_superuser:
        conversoes = ArquivoConversao.objects.all().order_by('-data_criacao')
    elif hasattr(request.user, 'pessoa'):
        conversoes = ArquivoConversao.objects.filter(
            usuario=request.user.pessoa
        ).order_by('-data_criacao')
    else:
        conversoes = ArquivoConversao.objects.none()
    
    return render(request, 'core/conversor/historico.html', {
        'conversoes': conversoes
    })


@login_required
def download_arquivo(request, conversao_id):
    """Download do arquivo convertido"""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)
    
    # Verificar permissão (centralizada)
    from .permissions import can_use_conversor
    if not can_use_conversor(request.user, conversao):
        messages.error(request, 'Permissão negada')
        return redirect('conversor_index')
    
    if not conversao.arquivo_convertido:
        messages.error(request, 'Arquivo convertido não encontrado')
        return redirect('conversor_index')
    
    # Verificar se o arquivo existe no sistema de arquivos
    if not os.path.exists(conversao.arquivo_convertido.path):
        messages.error(request, 'Arquivo não encontrado no servidor')
        return redirect('conversor_index')
    
    response = FileResponse(
        conversao.arquivo_convertido.open('rb'),
        as_attachment=True,
        filename=os.path.basename(conversao.arquivo_convertido.name)
    )
    
    return response


@login_required
def info_formatos(request):
    """Retorna informações sobre formatos suportados"""
    from .conversor_service import ConversorService
    
    # Obter extensão do arquivo da query string
    ext = request.GET.get('ext', '').lower()
    
    if ext:
        formatos = ConversorService.get_formatos_destino(ext)
        return JsonResponse({'formatos': formatos})
    
    return JsonResponse({
        'formatos': ConversorService.FORMATOS,
        'categorias': ConversorService.CATEGORIA_POR_EXT
    })