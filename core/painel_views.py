from django.shortcuts import render, get_object_or_404
from django.views import View
from django.db.models import Q, Count, Avg, ExpressionWrapper, F, DurationField
from django.db.models.functions import TruncDate, TruncMonth
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseRedirect, JsonResponse, HttpResponseForbidden
from django.urls import reverse
from django.utils import timezone
from core.models import Departamento, Analista, Atendimento, Empresa
from core.painel_utils import notificar_painel_departamento
from django.db import DatabaseError

# Mixin para restringir acesso por permissão de módulo
class ModulePermissionRequiredMixin(LoginRequiredMixin):
    module = None
    action = 'view'

    def has_permission(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        pessoa = getattr(user, 'pessoa', None)
        if pessoa and self.module:
            return pessoa.has_perm_code(f"{self.module}.{self.action}")
        return False

    def dispatch(self, request, *args, **kwargs):
        if not self.has_permission():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied()
        return super().dispatch(request, *args, **kwargs)

class ClienteAtendimentosView(View):
    def get(self, request):
        empresa = request.GET.get('empresa')
        if not empresa:
            return render(request, 'core/painel/cliente_identificacao.html')
        departamentos = Departamento.objects.all()
        atendimentos = Atendimento.objects.filter(empresa=empresa).order_by('-criado_em')
        return render(request, 'core/painel/cliente_atendimentos.html', {'empresa': empresa, 'atendimentos': atendimentos, 'departamentos': departamentos})

    def post(self, request):
        empresa = request.POST.get('empresa')
        empresa_id = request.POST.get('empresa_id')
        departamento_id = request.POST.get('departamento')
        motivo = request.POST.get('motivo')
        # Resolve empresa: prefer empresa_id when provided
        empresa_obj = None
        if empresa_id and empresa_id.isdigit() and int(empresa_id) > 0:
            try:
                empresa_obj = Empresa.objects.get(pk=int(empresa_id))
            except Empresa.DoesNotExist:
                empresa_obj = None
        # if no empresa object, try to find by nome_fantasia
        if not empresa_obj and empresa:
            empresa_qs = Empresa.objects.filter(nome_fantasia__iexact=empresa)
            if empresa_qs.exists():
                empresa_obj = empresa_qs.first()

        # if still no empresa, create a lightweight record (will be linked to current user)
        if not empresa_obj and empresa:
            empresa_obj = Empresa.objects.create(cnpj='', razao_social=empresa, nome_fantasia=empresa, ativo=True)
            if hasattr(request.user, 'pessoa'):
                empresa_obj.usuarios.add(request.user.pessoa)

        if empresa_obj and departamento_id and motivo:
            at = Atendimento.objects.create(
                empresa_obj=empresa_obj,
                empresa=empresa_obj.nome_fantasia,
                departamento_id=departamento_id,
                motivo=motivo,
                status='pendente',
            )
            try:
                notificar_painel_departamento(int(departamento_id))
            except Exception:
                pass
        departamentos = Departamento.objects.all()
        atendimentos = Atendimento.objects.filter(empresa=empresa).order_by('-criado_em')
        return render(request, 'core/painel/cliente_atendimentos.html', {'empresa': empresa, 'atendimentos': atendimentos, 'departamentos': departamentos})

class ChatAtendimentoView(ModulePermissionRequiredMixin, View):
    module = 'painel'
    action = 'view'
    def get(self, request, atendimento_id):
        atendimento = get_object_or_404(Atendimento, id=atendimento_id)
        return render(request, 'core/painel/chat_atendimento.html', {'atendimento': atendimento})

class RelatorioGestorView(ModulePermissionRequiredMixin, View):
    module = 'painel'
    action = 'view'
    def get(self, request):
        departamentos = Departamento.objects.all()
        departamento_id = request.GET.get('departamento')
        status = request.GET.get('status')

        # Period selection (days) or explicit start/end dates
        periodo = request.GET.get('periodo') or request.GET.get('period') or '30'
        try:
            periodo_days = int(periodo)
        except Exception:
            periodo_days = 30
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=periodo_days - 1)

        atendimentos_qs = Atendimento.objects.filter(criado_em__date__gte=start_date, criado_em__date__lte=end_date).order_by('-criado_em')
        if departamento_id:
            atendimentos_qs = atendimentos_qs.filter(departamento_id=departamento_id)
        if status:
            atendimentos_qs = atendimentos_qs.filter(status=status)

        # Basic metrics
        metrics_qs = atendimentos_qs
        total_atendimentos = metrics_qs.count()
        pendentes_count = metrics_qs.filter(status='pendente').count()
        atendendo_count = metrics_qs.filter(status='atendendo').count()
        finalizado_count = metrics_qs.filter(status='finalizado').count()
        cancelados_count = metrics_qs.filter(status='cancelado').count() if hasattr(Atendimento._meta, 'get_field') else 0

        wait_expr = ExpressionWrapper(F('iniciado_em') - F('criado_em'), output_field=DurationField())
        handle_expr = ExpressionWrapper(F('finalizado_em') - F('iniciado_em'), output_field=DurationField())
        avg_wait = metrics_qs.filter(iniciado_em__isnull=False).annotate(wait=wait_expr).aggregate(avg_wait=Avg('wait'))['avg_wait']
        avg_handle = metrics_qs.filter(finalizado_em__isnull=False, iniciado_em__isnull=False).annotate(handle=handle_expr).aggregate(avg_handle=Avg('handle'))['avg_handle']

        def minutes_or_none(td):
            if not td:
                return None
            try:
                return round(td.total_seconds() / 60, 1)
            except Exception:
                return None

        # Variacao em relação ao período anterior
        prev_end = start_date - timezone.timedelta(days=1)
        prev_start = prev_end - timezone.timedelta(days=periodo_days - 1)
        prev_count = Atendimento.objects.filter(criado_em__date__gte=prev_start, criado_em__date__lte=prev_end)
        if departamento_id:
            prev_count = prev_count.filter(departamento_id=departamento_id)
        prev_total = prev_count.count()
        variacao_total = None
        try:
            if prev_total > 0:
                variacao_total = round(((total_atendimentos - prev_total) / prev_total) * 100, 1)
            else:
                variacao_total = None
        except Exception:
            variacao_total = None

        # Trend: atendimentos por dia
        series = metrics_qs.annotate(d=TruncDate('criado_em')).values('d').annotate(c=Count('id')).order_by('d')
        trend_labels = [s['d'].strftime('%Y-%m-%d') for s in series]
        trend_data = [s['c'] for s in series]

        # Monthly counts (last 12 months)
        months_qs = metrics_qs.annotate(m=TruncMonth('criado_em')).values('m').annotate(c=Count('id')).order_by('m')
        monthly_labels = [m['m'].strftime('%Y-%m') for m in months_qs]
        monthly_data = [m['c'] for m in months_qs]

        # Departments distribution
        dept_qs = metrics_qs.values('departamento__nome').annotate(total=Count('id')).order_by('-total')
        dept_labels = [d['departamento__nome'] or '—' for d in dept_qs]
        dept_data = [d['total'] for d in dept_qs]

        # Attendance by state (empresa.uf)
        state_qs = metrics_qs.filter(empresa_obj__isnull=False).values('empresa_obj__uf').annotate(total=Count('id')).order_by('-total')
        state_labels = [s['empresa_obj__uf'] or '—' for s in state_qs]
        state_data = [s['total'] for s in state_qs]

        # Ranking de analistas (por total de atendimentos no período)
        analista_qs = metrics_qs.filter(analista__isnull=False).values('analista').annotate(total_atendimentos=Count('id'), nome=F('analista__user__first_name'), sobrenome=F('analista__user__last_name'), departamento_nome=F('analista__departamento__nome')).order_by('-total_atendimentos')
        ranking_analistas = []
        from django.utils.text import Truncator
        for a in analista_qs:
            nome = (a.get('nome') or '') + (' ' + (a.get('sobrenome') or '') if a.get('sobrenome') else '')
            ranking_analistas.append({
                'nome': Truncator(nome.strip()).chars(30),
                'departamento': {'nome': a.get('departamento_nome')},
                'total_atendimentos': a.get('total_atendimentos')
            })

        # Tempo médio por analista (em minutos) - média, min, max
        tempo_analistas = []
        handle_dur_expr = ExpressionWrapper(F('finalizado_em') - F('iniciado_em'), output_field=DurationField())
        from django.db.models import Min, Max
        analistas_handle = metrics_qs.filter(finalizado_em__isnull=False, iniciado_em__isnull=False, analista__isnull=False).values('analista', 'analista__user__first_name', 'analista__user__last_name').annotate(avg_handle=Avg(handle_dur_expr), min_handle=Min(handle_dur_expr), max_handle=Max(handle_dur_expr))
        for a in analistas_handle:
            def dur_to_min(td):
                if not td:
                    return None
                try:
                    return int(td.total_seconds() / 60)
                except Exception:
                    return None
            nome = (a.get('analista__user__first_name') or '') + (' ' + (a.get('analista__user__last_name') or '') if a.get('analista__user__last_name') else '')
            tempo_analistas.append({
                'nome': nome.strip(),
                'tempo_medio': dur_to_min(a.get('avg_handle')),
                'tempo_min': dur_to_min(a.get('min_handle')),
                'tempo_max': dur_to_min(a.get('max_handle')),
            })

        # Prepare atendimentos list and annotate tempo_atendimento (minutes)
        atendimentos_list = list(metrics_qs)
        for a in atendimentos_list:
            if a.finalizado_em and a.iniciado_em:
                try:
                    delta = a.finalizado_em - a.iniciado_em
                    a.tempo_atendimento = int(delta.total_seconds() / 60)
                except Exception:
                    a.tempo_atendimento = None
            else:
                a.tempo_atendimento = None

        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(atendimentos_list, 25)
        try:
            atendimentos_page = paginator.page(page)
        except PageNotAnInteger:
            atendimentos_page = paginator.page(1)
        except EmptyPage:
            atendimentos_page = paginator.page(paginator.num_pages)

        metrics = {
            'total': total_atendimentos,
            'variacao_total': variacao_total,
            'pendentes': pendentes_count,
            'atendendo': atendendo_count,
            'finalizado': finalizado_count,
            'cancelados': cancelados_count,
            'pendentes_percentual': round((pendentes_count / total_atendimentos) * 100, 1) if total_atendimentos else 0,
            'atendendo_percentual': round((atendendo_count / total_atendimentos) * 100, 1) if total_atendimentos else 0,
            'finalizado_percentual': round((finalizado_count / total_atendimentos) * 100, 1) if total_atendimentos else 0,
            'cancelados_percentual': round((cancelados_count / total_atendimentos) * 100, 1) if total_atendimentos else 0,
            'avg_wait_min': minutes_or_none(avg_wait),
            'avg_handle_min': minutes_or_none(avg_handle),
            'tempo_medio_atendimento': minutes_or_none(avg_handle) or 0,
            'tempo_medio_formatado': f"{minutes_or_none(avg_handle) or 0} min",
            'sla': round((metrics_qs.filter(finalizado_em__isnull=False, iniciado_em__isnull=False).filter(**{"finalizado_em__lte": F('iniciado_em') + timezone.timedelta(minutes=20)}).count() / total_atendimentos) * 100, 1) if total_atendimentos else 0,
            'satisfacao_media': None,
            'stars_range': range(0),
            'stars_has_half': False,
        }

        context = {
            'departamentos': departamentos,
            'atendimentos': atendimentos_page,
            'departamento_id': departamento_id,
            'status': status,
            'metrics': metrics,
            'trend_labels': trend_labels,
            'trend_data': trend_data,
            'monthly_labels': monthly_labels,
            'monthly_data': monthly_data,
            'dept_labels': dept_labels,
            'dept_data': dept_data,
            'state_labels': state_labels,
            'state_data': state_data,
            'ranking_analistas': ranking_analistas,
            'tempo_medio_analistas': tempo_analistas,
            'request': request,
        }
        return render(request, 'core/painel/relatorio_gestor.html', context)

class AtendimentoAnalistaView(ModulePermissionRequiredMixin, View):
    module = 'painel'
    action = 'view'
    def get(self, request, atendimento_id):
        atendimento = get_object_or_404(Atendimento, id=atendimento_id)
        # defensive: some environments may not have the painel anexos table migrated
        anexos = []
        try:
            anexos = list(atendimento.anexos.all())
        except DatabaseError:
            anexos = []
        return render(request, 'core/painel/atendimento_analista.html', {'atendimento': atendimento, 'anexos': anexos})

    def post(self, request, atendimento_id):
        from django.core.exceptions import PermissionDenied
        # require edit permission for modifications
        if not request.user.pessoa.has_perm_code('painel.edit'):
            raise PermissionDenied()
        atendimento = get_object_or_404(Atendimento, id=atendimento_id)
        if 'claim' in request.POST:
            try:
                atendimento.analista = request.user.analista
            except Exception:
                atendimento.analista = None
            atendimento.status = 'atendendo'
            atendimento.iniciado_em = timezone.now()
        else:
            try:
                atendimento.analista = request.user.analista
            except Exception:
                pass
            if 'finalizar' in request.POST:
                atendimento.status = 'finalizado'
                atendimento.finalizado_em = timezone.now()
        atendimento.save()
        # handle file attachments (if any)
        try:
            arquivos = request.FILES.getlist('anexos')
            from core.models import AtendimentoAnexo
            for f in arquivos:
                try:
                    AtendimentoAnexo.objects.create(atendimento=atendimento, arquivo=f)
                except DatabaseError:
                    # skip storing attachment if DB not ready
                    continue
        except Exception:
            pass

        notificar_painel_departamento(atendimento.departamento.id)
        if 'claim' in request.POST:
            return HttpResponseRedirect(reverse('painel:atendimento_analista', args=[atendimento.id]))
        if 'finalizar' in request.POST:
            return HttpResponseRedirect(reverse('painel:index'))
        # default: go back to department painel
        return HttpResponseRedirect(reverse('painel:painel_departamento', args=[atendimento.departamento.id]))


class AtendimentoAnexoUploadView(LoginRequiredMixin, View):
    """AJAX endpoint to upload a single anexo for an atendimento."""
    def post(self, request):
        from django.core.exceptions import PermissionDenied
        from core.models import AtendimentoAnexo
        atendimento_id = request.POST.get('atendimento_id')
        if not atendimento_id:
            return JsonResponse({'status': 'error', 'msg': 'missing atendimento_id'}, status=400)
        atendimento = get_object_or_404(Atendimento, pk=atendimento_id)
        # simple permission: must be analista of dept or have painel.edit
        pessoa = getattr(request.user, 'pessoa', None)
        if not (getattr(request.user, 'analista', None) or (pessoa and pessoa.has_perm_code('painel.edit'))):
            raise PermissionDenied()
        arquivo = request.FILES.get('anexo')
        if not arquivo:
            return JsonResponse({'status': 'error', 'msg': 'no file'}, status=400)
        # server-side validation
        max_size = 10 * 1024 * 1024  # 10 MB
        allowed_prefixes = ('image/', 'text/')
        allowed_exact = ('application/pdf', 'application/zip', 'application/octet-stream')
        ct = getattr(arquivo, 'content_type', '')
        if arquivo.size > max_size:
            return JsonResponse({'status': 'error', 'msg': 'file too large'}, status=400)
        if not (ct.startswith(allowed_prefixes) or ct in allowed_exact):
            return JsonResponse({'status': 'error', 'msg': 'file type not allowed', 'content_type': ct}, status=400)

        anexo = AtendimentoAnexo.objects.create(atendimento=atendimento, arquivo=arquivo)
        return JsonResponse({'status': 'ok', 'id': anexo.pk, 'url': anexo.arquivo.url, 'name': anexo.arquivo.name})

class PainelDepartamentoView(ModulePermissionRequiredMixin, View):
    module = 'painel'
    action = 'view'
    def get(self, request, departamento_id):
        departamento = get_object_or_404(Departamento, id=departamento_id)
        # analysts currently attending should be excluded from 'available'
        analistas_em_atendimento = Atendimento.objects.filter(
            status='atendendo',
            analista__departamento=departamento
        ).values_list('analista_id', flat=True)

        analistas_disponiveis = Analista.objects.filter(
            departamento=departamento
        ).exclude(id__in=analistas_em_atendimento)
        
        # 👇 BUSCA OS ATENDIMENTOS 👇
        atendimentos_pendentes = Atendimento.objects.filter(departamento=departamento, status='pendente').order_by('criado_em')
        atendimentos_andamento = Atendimento.objects.filter(departamento=departamento, status='atendendo').order_by('iniciado_em')
        
        # Allow forcing TV mode with ?tv=1 (useful for testing on the same machine).
        force_tv = request.GET.get('tv') == '1'
        
        # For public viewers (not an analyst of this department), show the TV-friendly view.
        user_analista = getattr(request.user, 'analista', None)
        
        # 👇 CRIA O CONTEXT COM TÍTULO E SUBTÍTULO 👇
        context = {
            'departamento': departamento,
            'analistas': analistas_disponiveis,
            'analistas_disponiveis': analistas_disponiveis,
            'atendimentos_pendentes': atendimentos_pendentes,  # Renomeado de 'pendentes'
            'atendimentos_andamento': atendimentos_andamento,  # Já está correto
            'title': f'Painel - {departamento.nome}',  # ← NOVO
            'subtitle': 'Visão do departamento em tempo real',  # ← NOVO
        }
        
        if force_tv or not user_analista or user_analista.departamento_id != departamento.id:
            # Modo TV (público)
            return render(request, 'core/painel/painel_departamento.html', context)
        
        # Modo analista (com permissões extras)
        pessoa = getattr(request.user, 'pessoa', None)
        user_can_manage = False
        try:
            if pessoa and pessoa.has_perm_code('painel.manage_departamento'):
                user_can_manage = True
        except Exception:
            user_can_manage = False
        
        # Adiciona a permissão ao context existente
        context['user_can_manage_painel'] = user_can_manage
        return render(request, 'core/painel/painel_departamento.html', context)

class ToggleDisponibilidadeView(LoginRequiredMixin, View):
    """Altera disponibilidade do analista associado ao usuário atual.
    Retorna JSON com o novo estado.
    """
    def post(self, request):
        try:
            analista = request.user.analista
        except Exception:
            return HttpResponseForbidden('Usuário não é analista')
        analista.disponivel = not bool(analista.disponivel)
        if analista.disponivel:
            analista.disponivel_em = timezone.now()
        else:
            analista.disponivel_em = None
        analista.save()
        try:
            notificar_painel_departamento(analista.departamento.id)
        except Exception:
            pass
        return JsonResponse({'disponivel': analista.disponivel})


class MeuPainelView(LoginRequiredMixin, View):
    """Redirects the current user to their relevant painel page.

    - If the user is an `Analista`, redirect to the department painel.
    - If the user has managerial access, redirect to the gestor report.
    - Otherwise redirect to the cliente identification page.
    """
    def get(self, request):
        # If user is an analyst, render their personal painel showing only
        # pending atendimentos for their department.
        analista = getattr(request.user, 'analista', None)
        if analista is not None:
            try:
                departamento = analista.departamento
                atendimentos_pendentes = Atendimento.objects.filter(departamento=departamento, status='pendente').order_by('criado_em')
                meus_atendimentos = Atendimento.objects.filter(analista=analista).order_by('-iniciado_em')
                return render(request, 'core/painel/meu_painel.html', {
                    'analista': analista,
                    'departamento': departamento,
                    'atendimentos_pendentes': atendimentos_pendentes,
                    'meus_atendimentos': meus_atendimentos,
                })
            except Exception:
                # fall through to other handlers
                pass

        pessoa = getattr(request.user, 'pessoa', None)
        if pessoa and pessoa.has_perm_code('painel.view'):
            return HttpResponseRedirect(reverse('painel:relatorio_gestor'))

        return HttpResponseRedirect(reverse('painel:cliente_atendimentos'))


class PuxarProximoView(LoginRequiredMixin, View):
    """Claim the next pending atendimento for the current analyst and redirect to it."""
    def get(self, request):
        # show next pending atendimento for confirmation
        analista = getattr(request.user, 'analista', None)
        if analista is None:
            return HttpResponseForbidden('Usuário não é analista')
        atendimento = Atendimento.objects.filter(departamento=analista.departamento, status='pendente').order_by('criado_em').first()
        return render(request, 'core/painel/puxar_confirm.html', {'atendimento': atendimento})

    def post(self, request):
        try:
            analista = request.user.analista
        except Exception:
            return HttpResponseForbidden('Usuário não é analista')
        # find oldest pending atendimento in this department
        atendimento = Atendimento.objects.filter(departamento=analista.departamento, status='pendente').order_by('criado_em').first()
        if not atendimento:
            from django.contrib import messages
            messages.info(request, 'Nenhum atendimento pendente.')
            return HttpResponseRedirect(reverse('painel:index'))
        atendimento.analista = analista
        atendimento.status = 'atendendo'
        atendimento.iniciado_em = timezone.now()
        atendimento.save()
        try:
            notificar_painel_departamento(analista.departamento.id)
        except Exception:
            pass
        return HttpResponseRedirect(reverse('painel:atendimento_analista', args=[atendimento.id]))


class PainelTVView(ModulePermissionRequiredMixin, View):
    module = 'painel'
    action = 'view'
    def get(self, request, departamento_id):
        departamento = get_object_or_404(Departamento, id=departamento_id)
        # Redirect to the unified department painel URL and force TV mode
        return HttpResponseRedirect(reverse('painel:painel_departamento', args=[departamento.id]) + '?tv=1')


class PainelTVIndexView(LoginRequiredMixin, View):
    """Simple selector page that lets the user choose a department and open the TV painel."""
    def get(self, request):
        # Render a simple selector listing departments so user can open the TV painel for one.
        departamentos = Departamento.objects.all().order_by('nome')
        return render(request, 'core/painel/tv_index.html', {'departamentos': departamentos})


class SecretariaPainelView(LoginRequiredMixin, View):
    def get(self, request):
        departamentos = Departamento.objects.all()
        # support optional date range filter via GET params (YYYY-MM-DD)
        start = request.GET.get('start_date')
        end = request.GET.get('end_date')
        ultimas_qs = Atendimento.objects.all().order_by('-criado_em')
        try:
            if start:
                from datetime import datetime
                sd = datetime.strptime(start, '%Y-%m-%d')
                ultimas_qs = ultimas_qs.filter(criado_em__date__gte=sd.date())
            if end:
                from datetime import datetime
                ed = datetime.strptime(end, '%Y-%m-%d')
                ultimas_qs = ultimas_qs.filter(criado_em__date__lte=ed.date())
        except Exception:
            # ignore parse errors, return unfiltered
            pass
        ultimas = ultimas_qs[:20]
        # provide company list for auto-complete or selection
        empresas = Empresa.objects.filter(ativo=True).order_by('nome_fantasia')[:100]
        analistas = Analista.objects.select_related('departamento').order_by('departamento__nome')[:200]
        pessoa = getattr(request.user, 'pessoa', None)
        user_can_manage = False
        try:
            if pessoa and pessoa.has_perm_code('painel.manage_departamento'):
                user_can_manage = True
        except Exception:
            user_can_manage = False
        return render(request, 'core/painel/secretaria_painel.html', {'departamentos': departamentos, 'ultimas': ultimas, 'empresas': empresas, 'analistas': analistas, 'user_can_manage': user_can_manage})

    def post(self, request):
        empresa = request.POST.get('empresa')
        empresa_id = request.POST.get('empresa_id')
        # optional detailed fields from autocomplete
        empresa_cnpj = request.POST.get('empresa_cnpj')
        empresa_razao = request.POST.get('empresa_razao')
        empresa_inscricao_municipal = request.POST.get('empresa_inscricao_municipal')
        empresa_inscricao_estadual = request.POST.get('empresa_inscricao_estadual')
        empresa_cep = request.POST.get('empresa_cep')
        empresa_logradouro = request.POST.get('empresa_logradouro')
        empresa_numero = request.POST.get('empresa_numero')
        empresa_complemento = request.POST.get('empresa_complemento')
        empresa_bairro = request.POST.get('empresa_bairro')
        empresa_municipio = request.POST.get('empresa_municipio')
        empresa_uf = request.POST.get('empresa_uf')
        departamento_id = request.POST.get('departamento')
        motivo = request.POST.get('motivo')
        empresa_obj = None
        if empresa_id and empresa_id.isdigit() and int(empresa_id) > 0:
            try:
                empresa_obj = Empresa.objects.get(pk=int(empresa_id))
            except Exception:
                empresa_obj = None
        if not empresa_obj and empresa:
            qs = Empresa.objects.filter(nome_fantasia__iexact=empresa)
            if qs.exists():
                empresa_obj = qs.first()
        if not empresa_obj and empresa:
            empresa_obj = Empresa.objects.create(cnpj='', razao_social=empresa, nome_fantasia=empresa, ativo=True)
            if hasattr(request.user, 'pessoa'):
                empresa_obj.usuarios.add(request.user.pessoa)
        # Update empresa_obj with details from autocomplete when provided
        if empresa_obj:
            changed = False
            if empresa_cnpj and empresa_cnpj.strip() and empresa_obj.cnpj != empresa_cnpj:
                empresa_obj.cnpj = empresa_cnpj.strip(); changed = True
            if empresa_razao and empresa_razao.strip() and empresa_obj.razao_social != empresa_razao:
                empresa_obj.razao_social = empresa_razao.strip(); changed = True
            if empresa_inscricao_municipal and empresa_obj.inscricao_municipal != empresa_inscricao_municipal:
                empresa_obj.inscricao_municipal = empresa_inscricao_municipal; changed = True
            if empresa_inscricao_estadual and empresa_obj.inscricao_estadual != empresa_inscricao_estadual:
                empresa_obj.inscricao_estadual = empresa_inscricao_estadual; changed = True
            if empresa_cep and empresa_obj.cep != empresa_cep:
                empresa_obj.cep = empresa_cep; changed = True
            if empresa_logradouro and empresa_obj.logradouro != empresa_logradouro:
                empresa_obj.logradouro = empresa_logradouro; changed = True
            if empresa_numero and empresa_obj.numero != empresa_numero:
                empresa_obj.numero = empresa_numero; changed = True
            if empresa_complemento and empresa_obj.complemento != empresa_complemento:
                empresa_obj.complemento = empresa_complemento; changed = True
            if empresa_bairro and empresa_obj.bairro != empresa_bairro:
                empresa_obj.bairro = empresa_bairro; changed = True
            if empresa_municipio and empresa_obj.municipio != empresa_municipio:
                empresa_obj.municipio = empresa_municipio; changed = True
            if empresa_uf and empresa_obj.uf != empresa_uf:
                empresa_obj.uf = empresa_uf; changed = True
            if changed:
                empresa_obj.save()
        if empresa_obj and departamento_id and motivo:
            at = Atendimento.objects.create(
                empresa_obj=empresa_obj,
                empresa=empresa_obj.nome_fantasia,
                departamento_id=departamento_id,
                motivo=motivo,
                status='pendente',
            )
            try:
                notificar_painel_departamento(int(departamento_id))
            except Exception:
                pass
        departamentos = Departamento.objects.all()
        ultimas_qs = Atendimento.objects.all().order_by('-criado_em')[:20]
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # return recent atendimentos as JSON for AJAX clients
            ultimas = []
            for at in ultimas_qs:
                ultimas.append({'id': at.pk, 'empresa': at.empresa, 'departamento': at.departamento.nome if at.departamento else None, 'status': at.status, 'criado_em': at.criado_em.isoformat() if at.criado_em else None})
            return JsonResponse({'status': 'ok', 'ultimas': ultimas})
        ultimas = ultimas_qs
        empresas = Empresa.objects.filter(ativo=True).order_by('nome_fantasia')[:100]
        analistas = Analista.objects.select_related('departamento').order_by('departamento__nome')[:200]
        return render(request, 'core/painel/secretaria_painel.html', {'departamentos': departamentos, 'ultimas': ultimas, 'empresas': empresas, 'analistas': analistas})


class TransferAtendimentoView(LoginRequiredMixin, View):
    """AJAX endpoint to transfer an atendimento to another analista or department.
    Rules:
    - Users with 'painel.manage_departamento' permission may transfer between departments.
    - Analistas may transfer only to other analistas within the same department.
    """
    def post(self, request):
        atendimento_id = request.POST.get('atendimento_id')
        to_analista_id = request.POST.get('to_analista_id')
        to_departamento_id = request.POST.get('to_departamento_id')
        if not atendimento_id:
            return JsonResponse({'status': 'error', 'msg': 'missing atendimento_id'}, status=400)
        atendimento = get_object_or_404(Atendimento, pk=atendimento_id)
        pessoa = getattr(request.user, 'pessoa', None)
        is_manager = False
        try:
            if pessoa and pessoa.has_perm_code('painel.manage_departamento'):
                is_manager = True
        except Exception:
            is_manager = False

        # transfer by department (manager only)
        if to_departamento_id:
            if not is_manager:
                return HttpResponseForbidden('Sem permissão para transferir entre departamentos')
            try:
                dept = Departamento.objects.get(pk=int(to_departamento_id))
                atendimento.departamento = dept
                atendimento.analista = None
                atendimento.status = 'pendente'
                atendimento.save()
                try:
                    notificar_painel_departamento(dept.id)
                except Exception:
                    pass
                return JsonResponse({'status': 'ok', 'msg': 'transferido_departamento', 'departamento': dept.nome})
            except Exception as e:
                return JsonResponse({'status': 'error', 'msg': str(e)}, status=400)

        # transfer to an analista
        if to_analista_id:
            try:
                target = Analista.objects.get(pk=int(to_analista_id))
            except Analista.DoesNotExist:
                return JsonResponse({'status': 'error', 'msg': 'analista nao encontrado'}, status=404)
            # if not manager, ensure same department
            if not is_manager and target.departamento_id != atendimento.departamento_id:
                return HttpResponseForbidden('Analista só pode transferir dentro do próprio departamento')
            atendimento.analista = target
            # if atendimento was pendente, set to atendendo
            if atendimento.status == 'pendente':
                atendimento.status = 'atendendo'
                atendimento.iniciado_em = timezone.now()
            atendimento.departamento = target.departamento
            atendimento.save()
            try:
                notificar_painel_departamento(atendimento.departamento.id)
            except Exception:
                pass
            return JsonResponse({'status': 'ok', 'msg': 'transferido_analista', 'analista': str(target)})

        return JsonResponse({'status': 'error', 'msg': 'nenhuma ação especificada'}, status=400)

    