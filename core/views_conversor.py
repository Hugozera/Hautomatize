"""
Views para o Conversor Universal de Arquivos
Integrado ao HDowloader
"""
import os
import json
from datetime import datetime
import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages

from .models import ArquivoConversao, Pessoa
from .conversor_service import converter_arquivo, get_formatos_destino
from django.utils.safestring import mark_safe
import mimetypes
from django.urls import reverse
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import inspect


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
            # se o front-end enviou o banco selecionado, armazena
            banco_selecionado = request.POST.get('banco')
            if banco_selecionado:
                conversao.banco = banco_selecionado
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
    
    # Permitir forçar reprocessamento via flags POST/GET (force_quality, overwrite_learning, parser)
    force_quality = bool(request.POST.get('force_quality') or request.GET.get('force_quality'))
    overwrite_learning = bool(request.POST.get('overwrite_learning') or request.GET.get('overwrite_learning'))
    parser_post_check = request.POST.get('parser') or request.GET.get('parser')

    # Se já foi convertido e não foi solicitado reprocessamento, retornar sucesso
    if conversao.status == 'concluido' and conversao.arquivo_convertido and not (force_quality or overwrite_learning or parser_post_check):
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
    
    # Criar diretório de processamento persistente por conversão para expor progresso
    processamento_dir = os.path.join(settings.MEDIA_ROOT or os.getcwd(), 'conversor', 'processing', str(conversao.id))
    os.makedirs(processamento_dir, exist_ok=True)
    print(f"📁 Diretório de processamento: {processamento_dir}")

    try:
        # Converter o arquivo
        print(f"🔄 Iniciando conversão para {conversao.formato_destino}...")
        # Permitir reprocessar com parser/banco forçado via POST (param 'parser')
        banco_forcado = None
        try:
            parser_post = request.POST.get('parser') or (conversao.banco if conversao.banco else None)
            banco_forcado = None
            if parser_post:
                # Tentar mapear parser_post (pode ser banco_id ou banco_nome) para banco_nome
                try:
                    import pkgutil, importlib
                    from .parsers.base_parser import BaseParser
                    parsers_pkg = __import__('core.parsers', fromlist=['']).parsers
                    for finder, name, ispkg in pkgutil.iter_modules(parsers_pkg.__path__):
                        try:
                            mod = importlib.import_module(f"{parsers_pkg.__name__}.{name}")
                        except Exception:
                            continue
                        for attr in dir(mod):
                            try:
                                obj = getattr(mod, attr)
                                if inspect.isclass(obj) and issubclass(obj, BaseParser) and obj is not BaseParser:
                                    inst = obj()
                                    if str(getattr(inst, 'banco_id', '')).upper() == str(parser_post).upper() or getattr(inst, 'banco_nome', '').upper() == str(parser_post).upper():
                                        banco_forcado = inst.banco_nome
                                        break
                            except Exception:
                                continue
                        if banco_forcado:
                            break
                except Exception:
                    banco_forcado = parser_post
        except Exception:
            banco_forcado = (conversao.banco or None)

        arquivo_convertido, erro = converter_arquivo(
            caminho_original,
            conversao.formato_destino,
            processamento_dir,
            banco_override=banco_forcado,
            force_quality=force_quality,
            overwrite_learning=overwrite_learning
        )

        if arquivo_convertido and os.path.exists(arquivo_convertido):
            tamanho = os.path.getsize(arquivo_convertido)
            print(f"✅ Conversão concluída! Tamanho: {tamanho} bytes")

            # Salvar arquivo convertido
            from django.core.files.base import ContentFile

            with open(arquivo_convertido, 'rb') as f:
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

            # Tentar carregar o texto universal extraído para exibir no front-end
            texto_completo = None
            try:
                nome_base = os.path.splitext(conversao.nome_original)[0]
                candidato_txt = os.path.join(processamento_dir, f"{nome_base}_texto_universal.txt")
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
            # include meta if present
            try:
                nome_base = os.path.splitext(conversao.nome_original)[0]
                meta_file = os.path.join(processamento_dir, f"{nome_base}.meta.json")
                if os.path.exists(meta_file):
                    with open(meta_file, 'r', encoding='utf-8') as mf:
                        m = json.load(mf)
                    resp['meta'] = m
            except Exception:
                pass

            return JsonResponse(resp)

        # Se não gerou arquivo convertido, tratar o erro retornado por converter_arquivo
        print(f"❌ Erro na conversão: {erro}")
        # special support flow
        if isinstance(erro, str) and erro.startswith('SUPPORT:'):
            support_path = erro.split(':', 1)[1]
            conversao.status = 'enviado_suporte'
            conversao.mensagem_erro = 'Arquivo enviado ao suporte para desenvolvimento de parser'
            conversao.save()
            return JsonResponse({
                'id': conversao.id,
                'status': 'enviado_suporte',
                'support_path': support_path,
                'mensagem': conversao.mensagem_erro
            })

        # Se há parsers disponíveis, oferecer lista para o front-end tentar reprocessar
        try:
            import pkgutil, importlib
            from .parsers.base_parser import BaseParser
            parsers_list = []
            parsers_pkg = __import__('core.parsers', fromlist=['']).parsers
            for finder, name, ispkg in pkgutil.iter_modules(parsers_pkg.__path__):
                try:
                    mod = importlib.import_module(f"{parsers_pkg.__name__}.{name}")
                except Exception:
                    continue
                for attr in dir(mod):
                    try:
                        obj = getattr(mod, attr)
                        if inspect.isclass(obj) and issubclass(obj, BaseParser) and obj is not BaseParser:
                            inst = obj()
                            parsers_list.append({'id': inst.banco_id, 'nome': inst.banco_nome})
                    except Exception:
                        continue
            if parsers_list:
                # Voltar conversão para 'pendente' para permitir reprocessamento sem criar novo registro
                conversao.status = 'pendente'
                conversao.save()
                return JsonResponse({'id': conversao.id, 'status': 'banco_nao_detectado', 'parsers': parsers_list})
        except Exception:
            pass

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
def progresso_conversao(request, conversao_id):
    """Retorna o progresso em tempo real (conteúdo do arquivo .progress.json) para uma conversão."""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)
    nome_base = os.path.splitext(conversao.nome_original)[0]
    processamento_dir = os.path.join(settings.MEDIA_ROOT or os.getcwd(), 'conversor', 'processing', str(conversao.id))
    progress_file = os.path.join(processamento_dir, f"{nome_base}.progress.json")
    if not os.path.exists(progress_file):
        return JsonResponse({'status': 'no_progress'}, status=200)
    try:
        with open(progress_file, 'r', encoding='utf-8') as pf:
            data = json.load(pf)
        return JsonResponse({'status': 'ok', 'progress': data})
    except Exception as e:
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)


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
def ver_ofx(request, conversao_id):
    """Mostra o OFX gerado e permite enviar um OFX para comparação lado-a-lado com o PDF original."""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)

    # Permissão
    if conversao.usuario and conversao.usuario != getattr(request.user, 'pessoa', None):
        if not request.user.is_superuser:
            messages.error(request, 'Permissão negada')
            return redirect('conversor_index')

    pdf_url = conversao.arquivo_original.url if conversao.arquivo_original else None
    # URL that serves the original file inline (forces Content-Disposition: inline)
    try:
        pdf_view_url = reverse('download_original', args=[conversao.id])
    except Exception:
        pdf_view_url = pdf_url
    generated_ofx = None
    uploaded_ofx = None

    # Ler OFX gerado, se existir
    try:
        if conversao.arquivo_convertido and conversao.arquivo_convertido.path and os.path.exists(conversao.arquivo_convertido.path):
            ext = os.path.splitext(conversao.arquivo_convertido.path)[1].lower()
            if ext == '.ofx' or conversao.arquivo_convertido.name.lower().endswith('.ofx'):
                with open(conversao.arquivo_convertido.path, 'r', encoding='utf-8', errors='replace') as f:
                    generated_ofx = f.read()
    except Exception:
        generated_ofx = None

    # POST: usuário enviou um OFX para comparar
    if request.method == 'POST':
        ofx_file = request.FILES.get('ofx_file')
        if ofx_file:
            try:
                uploaded_ofx = ofx_file.read().decode('utf-8', errors='replace')
            except Exception:
                try:
                    # fallback binary read
                    uploaded_ofx = ofx_file.read().decode('latin1', errors='replace')
                except Exception:
                    uploaded_ofx = None

    # Parse OFX into transactions for nicer HTML rendering
    def parse_ofx_transactions(ofx_text):
        if not ofx_text:
            return []
        import re
        trans = []
        blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', ofx_text, flags=re.S | re.I)
        for b in blocks:
            dt = re.search(r'<DTPOSTED>([^\r\n<]+)', b, flags=re.I)
            amt = re.search(r'<TRNAMT>([^\r\n<]+)', b, flags=re.I)
            trntype = re.search(r'<TRNTYPE>([^\r\n<]+)', b, flags=re.I)
            name = re.search(r'<NAME>([^\r\n<]+)', b, flags=re.I)
            memo = re.search(r'<MEMO>([^\r\n<]+)', b, flags=re.I)
            fitid = re.search(r'<FITID>([^\r\n<]+)', b, flags=re.I)
            dstr = dt.group(1).strip() if dt else ''
            date_display = dstr
            try:
                import datetime as _dt
                m = re.match(r'^(\d{4})(\d{2})(\d{2})', dstr)
                if m:
                    date_display = f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
            except Exception:
                pass
            # determine tipo from TRNTYPE if present, else from sign of TRNAMT
            tipo_val = ''
            if trntype and trntype.group(1):
                tt = trntype.group(1).strip().upper()
                # prefer single-letter codes for UI: B = débito, C = crédito
                if 'DEBIT' in tt or 'DEBITO' in tt or tt == 'D' or tt == 'B':
                    tipo_val = 'B'
                else:
                    tipo_val = 'C'
            else:
                amt_str = (amt.group(1).strip() if amt else '')
                try:
                    if amt_str.startswith('-') or float(amt_str.replace(',', '.')) < 0:
                        tipo_val = 'DEBIT'
                    else:
                        tipo_val = 'CREDIT'
                except Exception:
                    tipo_val = ''

            trans.append({
                'date': date_display,
                'amount': amt.group(1).strip() if amt else '',
                'tipo': tipo_val,
                'name': (name.group(1).strip() if name else '') or (memo.group(1).strip() if memo else ''),
                'fitid': fitid.group(1).strip() if fitid else ''
            })
        return trans

    generated_transacoes = parse_ofx_transactions(generated_ofx)
    uploaded_transacoes = parse_ofx_transactions(uploaded_ofx)

    return render(request, 'core/conversor/ver_ofx.html', {
        'conversao': conversao,
        'pdf_url': pdf_url,
        'pdf_view_url': pdf_view_url,
        'generated_ofx': generated_ofx,
        'uploaded_ofx': uploaded_ofx,
        'generated_transacoes': generated_transacoes,
        'uploaded_transacoes': uploaded_transacoes,
    })


@login_required
@csrf_exempt
def salvar_ofx_editado(request, conversao_id):
    """Recebe OFX editado via POST e salva como arquivo corrigido, atualizando o registro."""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)
    # Permissão
    if conversao.usuario and conversao.usuario != getattr(request.user, 'pessoa', None):
        if not request.user.is_superuser:
            return JsonResponse({'erro': 'Permissão negada'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    edited = request.POST.get('edited_ofx')
    if edited is None:
        return JsonResponse({'erro': 'Campo edited_ofx não encontrado'}, status=400)

    try:
        nome_base = os.path.splitext(conversao.nome_original)[0]
        novo_nome = f"{nome_base}_corrigido.ofx"
        # Salvar conteúdo como novo arquivo no storage e atualizar conversao
        content = ContentFile(edited.encode('utf-8'))
        # Salva no campo arquivo_convertido (substitui o anterior)
        conversao.arquivo_convertido.save(novo_nome, content, save=True)
        conversao.tamanho_convertido = conversao.arquivo_convertido.size
        conversao.data_conversao = datetime.now()
        conversao.status = 'concluido'
        conversao.save()

        return JsonResponse({'status': 'ok', 'url': conversao.arquivo_convertido.url})
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)


@login_required
@csrf_exempt
def salvar_transacoes_editadas(request, conversao_id):
    """Recebe transações editadas (JSON) e gera um OFX corrigido para download (não substitui o arquivo original)."""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)
    # Permissão
    if conversao.usuario and conversao.usuario != getattr(request.user, 'pessoa', None):
        if not request.user.is_superuser:
            return JsonResponse({'erro': 'Permissão negada'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'erro': 'Método não permitido'}, status=405)

    try:
        body = request.body.decode('utf-8')
        payload = json.loads(body)
        transacoes_in = payload.get('transacoes')
        if not isinstance(transacoes_in, list):
            return JsonResponse({'erro': 'Campo transacoes deve ser uma lista'}, status=400)
    except Exception as e:
        return JsonResponse({'erro': f'Payload inválido: {e}'}, status=400)

    def parse_date(s):
        # Accept formats: YYYYMMDDHHMMSS, YYYYMMDD, DD/MM/YYYY[ HH:MM:SS]
        s = (s or '').strip()
        if not s:
            return None
        # already YYYYMMDDHHMMSS
        if re.match(r'^\d{14}$', s):
            return s
        if re.match(r'^\d{8}$', s):
            return s + '000000'
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4})(?:\s+(\d{2}:\d{2}(?::\d{2})?))?$', s)
        if m:
            d, mo, y, timepart = m.groups()
            if not timepart:
                timepart = '00:00:00'
            parts = timepart.split(':')
            if len(parts) == 2:
                parts.append('00')
            hh, mm, ss = [p.zfill(2) for p in parts[:3]]
            return f"{y}{mo}{d}{hh}{mm}{ss}"
        # fallback: digits only
        digits = re.sub(r'\D', '', s)
        if len(digits) >= 8:
            digits = digits[:8]
            return digits + '000000'
        return None

    def parse_amount(s):
        try:
            s = s.strip().replace('.', '').replace(',', '.')
            return float(s)
        except Exception:
            return 0.0

    transacoes_for_ofx = []
    for t in transacoes_in:
        date_raw = t.get('date') or t.get('data') or ''
        parsed_date = parse_date(date_raw) or datetime.now().strftime('%Y%m%d%H%M%S')
        amt_raw = str(t.get('amount') or t.get('valor') or '0')
        valor = parse_amount(amt_raw)
        # Respect provided 'tipo' if present (accept single-letter 'B' (débito) or 'C' (crédito)), otherwise infer from amount sign
        tipo_raw = (t.get('tipo') or '').strip()
        if tipo_raw:
            tr = tipo_raw.upper()
            if tr in ('B', 'D') or 'DEBIT' in tr or 'DEBITO' in tr:
                tipo = 'DEBIT'
            else:
                tipo = 'CREDIT'
        else:
            if float(valor) < 0:
                tipo = 'DEBIT'
            else:
                tipo = 'CREDIT'
        # normalize value to absolute for OFX (tipo carries sign)
        if float(valor) < 0:
            valor = abs(float(valor))

        # Build description: prefer 'name' or 'descricao'. Do NOT append FITID here.
        descricao_raw = (t.get('name') or t.get('descricao') or t.get('description') or '').strip()
        destino_raw = (t.get('destino') or t.get('destination') or '').strip()
        descricao_full = descricao_raw
        if destino_raw:
            descricao_full = f"{descricao_full} / {destino_raw}" if descricao_full else destino_raw

        transacoes_for_ofx.append({
            'data': parsed_date,
            'valor': valor,
            'tipo': tipo,
            'descricao': descricao_full,
            'documento': t.get('documento', ''),
            'destino': destino_raw,
            'fitid': ''
        })

    # generate OFX into processing dir
    processamento_dir = os.path.join(settings.MEDIA_ROOT or os.getcwd(), 'conversor', 'processing', str(conversao.id))
    os.makedirs(processamento_dir, exist_ok=True)
    nome_base = os.path.splitext(conversao.nome_original)[0]
    novo_nome = f"{nome_base}_corrigido.ofx"
    destino_path = os.path.join(processamento_dir, novo_nome)

    try:
        from .conversor_service import gerar_ofx as gerar_ofx_func
    except Exception:
        from .conversor_service import ConversorService as gerar_ofx_func

    try:
        # gerar_ofx espera lista de dicts e caminho
        # our gerar_ofx is a classmethod — call via module function if available
        success = False
        try:
            # try module-level function
            success = gerar_ofx_func(transacoes_for_ofx, destino_path)
        except Exception:
            # fallback to classmethod
            from .conversor_service import ConversorService
            success = ConversorService.gerar_ofx(transacoes_for_ofx, destino_path)

        if not success or not os.path.exists(destino_path):
            return JsonResponse({'erro': 'Falha ao gerar OFX'}, status=500)

        # save to default storage under conversor/processed/<id>/
        with open(destino_path, 'rb') as fh:
            content = ContentFile(fh.read())
            storage_path = os.path.join('conversor', 'processed', str(conversao.id), novo_nome)
            # ensure dir
            # default_storage.save will create directories as needed
            saved = default_storage.save(storage_path, content)
            url = default_storage.url(saved)

        return JsonResponse({'status': 'ok', 'url': url})
    except Exception as e:
        return JsonResponse({'erro': str(e)}, status=500)


@login_required
def download_original(request, conversao_id):
    """Serve o arquivo original (PDF) inline para permitir visualização no navegador."""
    conversao = get_object_or_404(ArquivoConversao, id=conversao_id)

    # Permissão
    if conversao.usuario and conversao.usuario != getattr(request.user, 'pessoa', None):
        if not request.user.is_superuser:
            messages.error(request, 'Permissão negada')
            return redirect('conversor_index')

    if not conversao.arquivo_original:
        messages.error(request, 'Arquivo original não encontrado')
        return redirect('conversor_index')

    file_path = conversao.arquivo_original.path
    if not os.path.exists(file_path):
        messages.error(request, 'Arquivo não encontrado no servidor')
        return redirect('conversor_index')

    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'

    response = FileResponse(open(file_path, 'rb'), as_attachment=False, content_type=content_type)
    # Ensure inline rendering for PDFs
    if content_type == 'application/pdf':
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'

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