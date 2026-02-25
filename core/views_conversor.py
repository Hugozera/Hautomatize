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
def upload_arquivo_conversor(request):
    """Upload de arquivo para conversão - VERSÃO COM DEBUG"""
    print("\n" + "="*60)
    print("📤 UPLOAD_ARQUIVO_CONVERSOR INICIADO")
    print("="*60)
    
    # 1. Verificar método HTTP
    if request.method != 'POST':
        print("❌ Método não é POST")
        return JsonResponse({'erro': 'Método não permitido'}, status=405)
    
    print(f"✅ Método: {request.method}")

    try:
        # 2. Log detalhado dos dados recebidos
        print("\n📦 DADOS RECEBIDOS:")
        print(f"POST keys: {list(request.POST.keys())}")
        print(f"FILES keys: {list(request.FILES.keys())}")
        print(f"POST data: {dict(request.POST)}")
        
        # 3. Obter arquivo e formato destino
        arquivo = request.FILES.get('arquivo')
        formato_destino = request.POST.get('formato_destino')
        
        print(f"\n📁 Arquivo: {arquivo.name if arquivo else 'NENHUM'}")
        print(f"🎯 Formato destino: {formato_destino}")
        
        # 4. Validar arquivo
        if not arquivo:
            print("❌ ERRO: Arquivo não enviado")
            return JsonResponse({'erro': 'Arquivo não enviado'}, status=400)
        
        # 5. Validar formato destino
        if not formato_destino:
            print("❌ ERRO: Formato destino não especificado")
            return JsonResponse({'erro': 'Formato destino não especificado'}, status=400)
        
        # 6. Validar tamanho (limite de 50MB)
        if arquivo.size > 50 * 1024 * 1024:
            print(f"❌ ERRO: Arquivo muito grande: {arquivo.size} bytes")
            return JsonResponse({'erro': 'Arquivo muito grande. Limite: 50MB'}, status=400)
        
        print(f"✅ Tamanho: {arquivo.size} bytes")

        # 7. Determinar formato de origem
        nome_arquivo = arquivo.name
        formato_origem = os.path.splitext(nome_arquivo)[1].lower().replace('.', '')
        
        print(f"📄 Nome arquivo: {nome_arquivo}")
        print(f"🔤 Formato origem: {formato_origem}")

        # 8. Validar se o formato_destino é aceito
        try:
            formatos_validos = get_formatos_destino(formato_origem)
            print(f"✅ Formatos válidos: {formatos_validos}")
            
            if formato_destino not in formatos_validos:
                print(f"❌ ERRO: Formato destino '{formato_destino}' não está em {formatos_validos}")
                return JsonResponse({
                    'erro': f'Formato destino inválido para {formato_origem}. Opções: {formatos_validos}'
                }, status=400)
        except Exception as e:
            print(f"❌ ERRO ao obter formatos: {str(e)}")
            return JsonResponse({'erro': f'Erro ao validar formatos: {str(e)}'}, status=500)

        # 9. Verificar usuário
        usuario = request.user.pessoa if hasattr(request.user, 'pessoa') else None
        print(f"👤 Usuário: {usuario}")

        # 10. Criar registro no banco
        try:
            conversao = ArquivoConversao(
                usuario=usuario,
                nome_original=nome_arquivo,
                formato_origem=formato_origem,
                formato_destino=formato_destino,
                tamanho_original=arquivo.size,
                status='pendente'
            )
            conversao.save()
            print(f"💾 Conversão ID: {conversao.id}")
        except Exception as e:
            print(f"❌ ERRO ao criar registro no banco: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'erro': f'Erro ao criar registro: {str(e)}'}, status=500)

        # 11. Salvar arquivo original
        try:
            conversao.arquivo_original.save(arquivo.name, arquivo, save=True)
            print(f"💾 Arquivo salvo em: {conversao.arquivo_original.path}")
            print(f"✅ Upload concluído com sucesso!")
        except Exception as e:
            print(f"❌ ERRO ao salvar arquivo: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'erro': f'Erro ao salvar arquivo: {str(e)}'}, status=500)

        # 12. Retornar sucesso
        return JsonResponse({
            'id': conversao.id,
            'status': 'pendente',
            'mensagem': 'Arquivo recebido com sucesso'
        })

    except Exception as e:
        print(f"❌ ERRO INESPERADO: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'erro': f'Erro inesperado: {str(e)}'}, status=500)


@login_required
def processar_conversao(request, conversao_id):
    """Processa a conversão de um arquivo"""
    print(f"\n🔄 PROCESSAR CONVERSÃO ID: {conversao_id}")
    
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)
    
    # Verificar permissão
    if conversao.usuario and conversao.usuario != getattr(request.user, 'pessoa', None):
        if not request.user.is_superuser:
            print(f"❌ Permissão negada para usuário {request.user}")
            return JsonResponse({'erro': 'Permissão negada'}, status=403)
    
    # Se já foi convertido, retornar sucesso
    if conversao.status == 'concluido' and conversao.arquivo_convertido:
        print(f"✅ Conversão já concluída anteriormente")
        return JsonResponse({
            'id': conversao.id,
            'status': 'concluido',
            'url': conversao.arquivo_convertido.url,
            'tamanho': conversao.tamanho_convertido
        })
    
    # Atualizar status
    conversao.status = 'convertendo'
    conversao.save()
    print(f"⏳ Status atualizado para: convertendo")
    
    # Caminho do arquivo original
    caminho_original = conversao.arquivo_original.path
    print(f"📁 Arquivo original: {caminho_original}")
    
    # Criar diretório temporário para conversão
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Diretório temporário: {temp_dir}")
        
        try:
            # Converter o arquivo
            print(f"🔄 Iniciando conversão para {conversao.formato_destino}...")
            arquivo_convertido, erro = converter_arquivo(
                caminho_original,
                conversao.formato_destino,
                temp_dir
            )
            
            if arquivo_convertido and os.path.exists(arquivo_convertido):
                tamanho = os.path.getsize(arquivo_convertido)
                print(f"✅ Conversão concluída! Tamanho: {tamanho} bytes")
                
                # Salvar arquivo convertido
                from django.core.files.base import ContentFile
                
                # Quando salva o arquivo convertido
                with open(arquivo_convertido, 'rb') as f:
                    # Se o formato destino for ZIP, mantém .zip, senão usa o formato destino
                    if conversao.formato_destino == 'zip' or arquivo_convertido.endswith('.zip'):
                        nome_convertido = f"{os.path.splitext(conversao.nome_original)[0]}.zip"
                    else:
                        nome_convertido = f"{os.path.splitext(conversao.nome_original)[0]}.{conversao.formato_destino}"
                    
                    conversao.arquivo_convertido.save(nome_convertido, ContentFile(f.read()), save=True)
                
                conversao.status = 'concluido'
                conversao.tamanho_convertido = tamanho
                conversao.data_conversao = datetime.now()
                conversao.save()
                
                print(f"✅ Arquivo salvo em: {conversao.arquivo_convertido.url}")

                # If available, try to include the extracted TXT universal for frontend display
                texto_completo = None
                try:
                    nome_base = os.path.splitext(conversao.nome_original)[0]
                    candidato_txt = os.path.join(temp_dir, f"{nome_base}_texto_universal.txt")
                    if os.path.exists(candidato_txt):
                        with open(candidato_txt, 'r', encoding='utf-8', errors='replace') as tf:
                            texto_completo = tf.read()
                except Exception:
                    texto_completo = None

                resp = {
                    'id': conversao.id,
                    'status': 'concluido',
                    'url': conversao.arquivo_convertido.url,
                    'tamanho': conversao.tamanho_convertido
                }
                if texto_completo is not None:
                    resp['texto_completo'] = texto_completo

                return JsonResponse(resp)
            else:
                print(f"❌ Erro na conversão: {erro}")
                conversao.status = 'erro'
                conversao.mensagem_erro = erro or 'Erro desconhecido na conversão'
                conversao.save()
                
                return JsonResponse({
                    'id': conversao.id,
                    'status': 'erro',
                    'erro': conversao.mensagem_erro
                })
                
        except Exception as e:
            print(f"❌ Exceção na conversão: {str(e)}")
            import traceback
            traceback.print_exc()
            
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
    
    # Verificar permissão
    if conversao.usuario and conversao.usuario != getattr(request.user, 'pessoa', None):
        if not request.user.is_superuser:
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
    
    # Verificar permissão
    if conversao.usuario and conversao.usuario != getattr(request.user, 'pessoa', None):
        if not request.user.is_superuser:
            messages.error(request, 'Permissão negada')
            return redirect('conversor_index')
    
    if not conversao.arquivo_convertido:
        messages.error(request, 'Arquivo convertido não encontrado')
        return redirect('conversor_index')
    
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
    
    ext = request.GET.get('ext', '').lower()
    
    if ext:
        formatos = ConversorService.get_formatos_destino(ext)
        return JsonResponse({'formatos': formatos})
    
    return JsonResponse({
        'formatos': ConversorService.FORMATOS_SUPORTADOS,
    })
@login_required
@csrf_exempt
def processar_zip_upload(request):
    """
    Processa upload de arquivo ZIP (quando múltiplos arquivos são selecionados)
    """
    print("\n" + "="*60)
    print("📦 PROCESSAR ZIP UPLOAD")
    print("="*60)
    
    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)
    
    try:
        arquivo = request.FILES.get('arquivo')
        formato_destino = request.POST.get('formato_destino')
        
        if not arquivo or not arquivo.name.endswith('.zip'):
            return JsonResponse({'erro': 'Arquivo ZIP não encontrado'}, status=400)
        
        if not formato_destino:
            return JsonResponse({'erro': 'Formato destino não especificado'}, status=400)
        
        print(f"📁 Arquivo ZIP: {arquivo.name}")
        print(f"🎯 Formato destino: {formato_destino}")
        print(f"📊 Tamanho: {arquivo.size} bytes")
        
        # Extrair a extensão original dos arquivos dentro do ZIP
        # Por padrão, usamos 'pdf' como fallback
        formato_origem = 'pdf'  # ou 'ofx' dependendo do contexto
        
        # Criar registro no banco
        usuario = request.user.pessoa if hasattr(request.user, 'pessoa') else None
        
        conversao = ArquivoConversao(
            usuario=usuario,
            nome_original=arquivo.name,
            formato_origem=formato_origem,
            formato_destino=formato_destino,
            tamanho_original=arquivo.size,
            status='pendente'
        )
        conversao.save()
        
        # Salvar arquivo ZIP original
        conversao.arquivo_original.save(arquivo.name, arquivo, save=True)
        
        print(f"✅ ZIP registrado com ID: {conversao.id}")
        
        return JsonResponse({
            'id': conversao.id,
            'status': 'pendente',
            'mensagem': 'Arquivo ZIP recebido com sucesso'
        })
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'erro': str(e)}, status=500)