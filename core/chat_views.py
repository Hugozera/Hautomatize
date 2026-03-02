from django.shortcuts import render, get_object_or_404
from django.views import View
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Count
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import os
import json
from PIL import Image
import magic

from core.models import (
    Pessoa, Atendimento, Conversa, Mensagem, 
    AnexoMensagem, Departamento, Analista
)


class ChatPainelView(LoginRequiredMixin, View):
    """
    View principal do chat - exibe a interface com lista de conversas
    """
    template_name = 'core/chat/chat_panel.html'
    
    def get(self, request):
        pessoa = getattr(request.user, 'pessoa', None)
        analista = getattr(request.user, 'analista', None)
        
        if not pessoa:
            return HttpResponseForbidden('Acesso negado')
        
        # Atendimentos (conversas com empresas)
        atendimentos = Atendimento.objects.filter(
            Q(analista=analista) | 
            Q(empresa_obj__usuarios=pessoa)
        ).distinct().order_by('-criado_em')
        
        # Pessoas (funcionários ativos)
        pessoas = Pessoa.objects.filter(
            ativo=True,
            usuario__isnull=False
        ).exclude(
            id=pessoa.id
        ).select_related(
            'departamento'
        ).order_by('nome')
        
        # Últimas conversas (para sidebar)
        ultimas_conversas = []
        
        # Adiciona atendimentos
        for at in atendimentos[:10]:
            ultimas_conversas.append({
                'id': f'at-{at.id}',
                'tipo': 'atendimento',
                'titulo': at.empresa or f'Atendimento #{at.id}',
                'subtitulo': at.motivo or '...',
                'data': at.criado_em,
                'status': at.status,
                'avatar': None
            })
        
        # Adiciona conversas com pessoas
        for pes in pessoas[:10]:
            ultimas_conversas.append({
                'id': f'pessoa-{pes.id}',
                'tipo': 'pessoa',
                'titulo': pes.nome,
                'subtitulo': pes.cargo or 'Funcionário',
                'data': None,
                'status': 'online' if pes.usuario and pes.usuario.is_active else 'offline',
                'avatar': pes.foto.url if pes.foto else None,
                'departamento': pes.departamento.sigla if pes.departamento else ''
            })
        
        # Ordena por data (mais recentes primeiro)
        ultimas_conversas.sort(key=lambda x: x['data'] or timezone.datetime.min, reverse=True)
        
        context = {
            'atendimentos': atendimentos,
            'pessoas': pessoas,
            'ultimas_conversas': ultimas_conversas,
            'titulo_pagina': 'Chat'
        }
        
        return render(request, self.template_name, context)


class BuscarPessoasView(LoginRequiredMixin, View):
    """
    API para buscar pessoas (funcionários)
    """
    def get(self, request):
        termo = request.GET.get('q', '').strip()
        
        if len(termo) < 2:
            return JsonResponse({'results': []})
        
        pessoas = Pessoa.objects.filter(
            ativo=True,
            usuario__isnull=False
        ).filter(
            Q(nome__icontains=termo) |
            Q(email__icontains=termo) |
            Q(departamento__nome__icontains=termo) |
            Q(cargo__icontains=termo)
        ).select_related('departamento')[:20]
        
        results = []
        for p in pessoas:
            results.append({
                'id': p.id,
                'nome': p.nome,
                'email': p.email,
                'cargo': p.cargo,
                'departamento': p.departamento.nome if p.departamento else '',
                'avatar': p.foto.url if p.foto else None,
                'online': p.usuario and p.usuario.is_active
            })
        
        return JsonResponse({'results': results})


class CriarConversaView(LoginRequiredMixin, View):
    """
    Cria uma nova conversa com uma pessoa ou atendimento
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            tipo = data.get('tipo')
            destinatario_id = data.get('destinatario_id')
            
            pessoa_origem = getattr(request.user, 'pessoa', None)
            
            if not pessoa_origem:
                return JsonResponse({'erro': 'Usuário não é uma pessoa'}, status=400)
            
            if tipo == 'pessoa':
                # Conversa entre pessoas
                pessoa_destino = get_object_or_404(Pessoa, id=destinatario_id)
                
                # Verifica se já existe conversa
                conversa = Conversa.objects.filter(
                    participantes=pessoa_origem
                ).filter(
                    participantes=pessoa_destino
                ).first()
                
                if not conversa:
                    conversa = Conversa.objects.create()
                    conversa.participantes.add(pessoa_origem, pessoa_destino)
                
                return JsonResponse({
                    'id': conversa.id,
                    'tipo': 'pessoa',
                    'titulo': pessoa_destino.nome,
                    'avatar': pessoa_destino.foto.url if pessoa_destino.foto else None
                })
                
            elif tipo == 'atendimento':
                # Conversa de atendimento
                atendimento = get_object_or_404(Atendimento, id=destinatario_id)
                
                # Verifica permissão
                analista = getattr(request.user, 'analista', None)
                if not (analista == atendimento.analista or 
                       atendimento.empresa_obj and pessoa_origem in atendimento.empresa_obj.usuarios.all()):
                    return HttpResponseForbidden('Sem permissão para acessar este atendimento')
                
                return JsonResponse({
                    'id': f'at-{atendimento.id}',
                    'tipo': 'atendimento',
                    'titulo': atendimento.empresa,
                    'status': atendimento.status
                })
            
        except json.JSONDecodeError:
            return HttpResponseBadRequest('JSON inválido')
        except Exception as e:
            return JsonResponse({'erro': str(e)}, status=500)


class HistoricoMensagensView(LoginRequiredMixin, View):
    """
    Retorna o histórico de mensagens de uma conversa
    """
    def get(self, request, conversa_id):
        pessoa = getattr(request.user, 'pessoa', None)
        
        if not pessoa:
            return HttpResponseForbidden('Acesso negado')
        
        # Verifica se é atendimento ou conversa normal
        if conversa_id.startswith('at-'):
            # É um atendimento
            atendimento_id = conversa_id.replace('at-', '')
            atendimento = get_object_or_404(Atendimento, id=atendimento_id)
            
            # Verifica permissão
            analista = getattr(request.user, 'analista', None)
            if not (analista == atendimento.analista or 
                   atendimento.empresa_obj and pessoa in atendimento.empresa_obj.usuarios.all()):
                return HttpResponseForbidden('Sem permissão')
            
            # Busca mensagens do atendimento
            mensagens = Mensagem.objects.filter(
                atendimento=atendimento
            ).select_related('remetente').order_by('criado_em')
            
        else:
            # Conversa normal entre pessoas
            conversa = get_object_or_404(Conversa, id=conversa_id)
            
            # Verifica se a pessoa participa da conversa
            if pessoa not in conversa.participantes.all():
                return HttpResponseForbidden('Sem permissão')
            
            mensagens = Mensagem.objects.filter(
                conversa=conversa
            ).select_related('remetente').order_by('criado_em')
        
        messages_list = []
        for msg in mensagens:
            message_data = {
                'id': msg.id,
                'user': msg.remetente.nome if msg.remetente else 'Sistema',
                'user_id': msg.remetente.id if msg.remetente else None,
                'message': msg.conteudo,
                'time': msg.criado_em.strftime('%H:%M'),
                'timestamp': msg.criado_em.isoformat(),
                'own': msg.remetente == pessoa,
                'attachments': []
            }
            
            # Anexos
            for anexo in msg.anexos.all():
                attachment = {
                    'id': anexo.id,
                    'name': anexo.nome_original,
                    'url': anexo.arquivo.url,
                    'size': anexo.tamanho,
                    'type': anexo.tipo
                }
                message_data['attachments'].append(attachment)
            
            messages_list.append(message_data)
        
        return JsonResponse(messages_list, safe=False)


class UploadAnexoView(LoginRequiredMixin, View):
    """
    Upload de arquivos para mensagens
    """
    def post(self, request):
        pessoa = getattr(request.user, 'pessoa', None)
        
        if not pessoa:
            return JsonResponse({'erro': 'Acesso negado'}, status=403)
        
        files = request.FILES.getlist('files')
        conversa_id = request.POST.get('conversa_id')
        
        if not files:
            return JsonResponse({'erro': 'Nenhum arquivo enviado'}, status=400)
        
        uploaded_files = []
        
        for file in files:
            # Validações
            if file.size > 10 * 1024 * 1024:  # 10MB
                return JsonResponse({'erro': f'Arquivo {file.name} muito grande (máx 10MB)'}, status=400)
            
            # Valida tipo de arquivo
            allowed_types = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain',
                'application/zip',
                'application/x-rar-compressed'
            ]
            
            # Detecta MIME type
            mime = magic.from_buffer(file.read(2048), mime=True)
            file.seek(0)  # Volta ao início
            
            if mime not in allowed_types and not mime.startswith('image/'):
                return JsonResponse({'erro': f'Tipo de arquivo não permitido: {file.name}'}, status=400)
            
            # Salva arquivo
            caminho = f'chat_anexos/{timezone.now().strftime("%Y/%m/%d")}/{file.name}'
            caminho_salvo = default_storage.save(caminho, ContentFile(file.read()))
            url = default_storage.url(caminho_salvo)
            
            # Cria registro de anexo
            anexo = AnexoMensagem.objects.create(
                arquivo=caminho_salvo,
                nome_original=file.name,
                tamanho=file.size,
                tipo=mime
            )
            
            uploaded_files.append({
                'id': anexo.id,
                'name': file.name,
                'url': url,
                'size': file.size,
                'type': mime
            })
        
        return JsonResponse({'files': uploaded_files})


class EnviarMensagemView(LoginRequiredMixin, View):
    """
    Endpoint para enviar mensagem (fallback caso WebSocket não esteja disponível)
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            conversa_id = data.get('conversa_id')
            conteudo = data.get('mensagem', '').strip()
            anexos_ids = data.get('anexos', [])
            
            pessoa = getattr(request.user, 'pessoa', None)
            
            if not pessoa:
                return JsonResponse({'erro': 'Acesso negado'}, status=403)
            
            if not conteudo and not anexos_ids:
                return JsonResponse({'erro': 'Mensagem vazia'}, status=400)
            
            # Determina tipo de conversa
            if conversa_id.startswith('at-'):
                # Atendimento
                atendimento_id = conversa_id.replace('at-', '')
                atendimento = get_object_or_404(Atendimento, id=atendimento_id)
                
                mensagem = Mensagem.objects.create(
                    atendimento=atendimento,
                    remetente=pessoa,
                    conteudo=conteudo
                )
            else:
                # Conversa normal
                conversa = get_object_or_404(Conversa, id=conversa_id)
                
                # Verifica permissão
                if pessoa not in conversa.participantes.all():
                    return HttpResponseForbidden('Sem permissão')
                
                mensagem = Mensagem.objects.create(
                    conversa=conversa,
                    remetente=pessoa,
                    conteudo=conteudo
                )
            
            # Adiciona anexos
            if anexos_ids:
                anexos = AnexoMensagem.objects.filter(id__in=anexos_ids)
                mensagem.anexos.set(anexos)
            
            return JsonResponse({
                'id': mensagem.id,
                'status': 'ok',
                'timestamp': mensagem.criado_em.isoformat()
            })
            
        except json.JSONDecodeError:
            return HttpResponseBadRequest('JSON inválido')
        except Exception as e:
            return JsonResponse({'erro': str(e)}, status=500)


class InfoContatoView(LoginRequiredMixin, View):
    """
    Retorna informações de um contato (pessoa) para o painel lateral
    """
    def get(self, request, pessoa_id):
        pessoa = get_object_or_404(Pessoa, id=pessoa_id)
        
        # Informações básicas (sem dados sensíveis)
        data = {
            'id': pessoa.id,
            'nome': pessoa.nome,
            'email': pessoa.email,
            'telefone': pessoa.telefone,
            'celular': pessoa.celular,
            'cargo': pessoa.cargo,
            'departamento': pessoa.departamento.nome if pessoa.departamento else None,
            'foto': pessoa.foto.url if pessoa.foto else None,
            'online': pessoa.usuario and pessoa.usuario.is_active,
            'ultimo_acesso': pessoa.usuario.last_login.isoformat() if pessoa.usuario and pessoa.usuario.last_login else None
        }
        
        return JsonResponse(data)


class InfoAtendimentoView(LoginRequiredMixin, View):
    """
    Retorna informações de um atendimento para o painel lateral
    """
    def get(self, request, atendimento_id):
        atendimento = get_object_or_404(Atendimento, id=atendimento_id)
        
        data = {
            'id': atendimento.id,
            'empresa': atendimento.empresa,
            'status': atendimento.status,
            'status_display': atendimento.get_status_display(),
            'motivo': atendimento.motivo,
            'criado_em': atendimento.criado_em.isoformat(),
            'iniciado_em': atendimento.iniciado_em.isoformat() if atendimento.iniciado_em else None,
            'finalizado_em': atendimento.finalizado_em.isoformat() if atendimento.finalizado_em else None,
            'analista': atendimento.analista.user.pessoa.nome if atendimento.analista else None,
            'departamento': atendimento.departamento.nome,
            'empresa_obj': {
                'id': atendimento.empresa_obj.id if atendimento.empresa_obj else None,
                'nome': atendimento.empresa_obj.nome_fantasia if atendimento.empresa_obj else None,
                'cnpj': atendimento.empresa_obj.cnpj if atendimento.empresa_obj else None,
                'telefone': atendimento.empresa_obj.telefone if atendimento.empresa_obj else None,
                'email': atendimento.empresa_obj.email if atendimento.empresa_obj else None
            } if atendimento.empresa_obj else None
        }
        
        return JsonResponse(data)


class MarcarComoLidaView(LoginRequiredMixin, View):
    """
    Marca mensagens como lidas
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            conversa_id = data.get('conversa_id')
            
            pessoa = getattr(request.user, 'pessoa', None)
            
            if not pessoa:
                return JsonResponse({'erro': 'Acesso negado'}, status=403)
            
            if conversa_id.startswith('at-'):
                atendimento_id = conversa_id.replace('at-', '')
                Mensagem.objects.filter(
                    atendimento_id=atendimento_id
                ).exclude(
                    remetente=pessoa
                ).update(lida=True, lida_em=timezone.now())
            else:
                Mensagem.objects.filter(
                    conversa_id=conversa_id
                ).exclude(
                    remetente=pessoa
                ).update(lida=True, lida_em=timezone.now())
            
            return JsonResponse({'status': 'ok'})
            
        except json.JSONDecodeError:
            return HttpResponseBadRequest('JSON inválido')
        except Exception as e:
            return JsonResponse({'erro': str(e)}, status=500)


class StatusDigitandoView(LoginRequiredMixin, View):
    """
    Notifica que o usuário está digitando
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            conversa_id = data.get('conversa_id')
            digitando = data.get('digitando', False)
            
            # Aqui você pode implementar WebSocket para notificar em tempo real
            # Por enquanto apenas retorna OK
            
            return JsonResponse({'status': 'ok'})
            
        except json.JSONDecodeError:
            return HttpResponseBadRequest('JSON inválido')