"""
EXEMPLOS DE VIEWS PROTEGIDAS COM O NOVO SISTEMA DE PERMISSÕES

Este arquivo demonstra como:
1. Proteger views com @login_required + check_perm
2. Retornar erro 403 forbiddne se sem permissão
3. Passar dados de permissão para template
4. Usar em modais/actions

Copy and paste nos seus arquivos de views!
"""

# ==================== EXEMPLO 1: PROTEGER E EXIBIR LISTA ====================

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from core.permissions import (
    can_view_empresa,
    can_list_empresa,
    can_create_empresa,
    can_edit_empresa,
    can_delete_empresa,
    check_perm,
)
from core.models import Empresa


@login_required
def lista_empresas(request):
    """
    View de listagem de empresas com proteção de permissões
    """
    # 1. Verificar permissão para LISTAR
    if not can_list_empresa(request.user):
        return HttpResponseForbidden(
            "Você não tem permissão para listar empresas"
        )
    
    # 2. Buscar dados
    empresas = Empresa.objects.filter(ativo=True)
    
    # 3. Passou as permissões para o template
    context = {
        'empresas': empresas,
        'pode_criar': can_create_empresa(request.user),
        'pode_editar': can_edit_empresa(request.user),
        'pode_deletar': can_delete_empresa(request.user),
    }
    
    return render(request, 'empresa_list.html', context)


# ==================== EXEMPLO 2: DETALHES COM AÇÕES CONDICIONAIS ====================

@login_required
def detalhe_empresa(request, empresa_id):
    """
    View de detalhes com botões que aparecem conforme permissão
    """
    # Buscar empresa
    empresa = get_object_or_404(Empresa, id=empresa_id)
    
    # Verificar se pode VER ao menos
    if not can_view_empresa(request.user, empresa):
        return HttpResponseForbidden("Acesso negado")
    
    # Carregar actions disponíveis
    actions = {
        'editar': can_edit_empresa(request.user, empresa),
        'deletar': can_delete_empresa(request.user, empresa),
        'upload_certificado': check_perm(request.user, 'certificado.upload'),
        'fazer_download': check_perm(request.user, 'nfse_downloader.download_manual'),
    }
    
    context = {
        'empresa': empresa,
        'actions': actions,
    }
    
    return render(request, 'empresa_detalhe.html', context)


# ==================== EXEMPLO 3: FORMULÁRIO COM PROTEÇÃO ====================

@login_required
def editar_empresa(request, empresa_id):
    """
    View de edição com proteção de permissão
    """
    empresa = get_object_or_404(Empresa, id=empresa_id)
    
    # Verificar permissão ANTES de processar POST
    if not can_edit_empresa(request.user, empresa):
        return HttpResponseForbidden(
            "Você não tem permissão para editar esta empresa"
        )
    
    if request.method == 'POST':
        # Validar e salvar
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            empresa = form.save()
            from django.contrib import messages
            messages.success(request, f"Empresa {empresa.nome_fantasia} atualizada!")
            return redirect('empresa_detalhe', empresa_id=empresa.id)
    else:
        form = EmpresaForm(instance=empresa)
    
    context = {
        'form': form,
        'empresa': empresa,
    }
    
    return render(request, 'empresa_form.html', context)


# ==================== EXEMPLO 4: CRIAR COM PROTEÇÃO ====================

@login_required
def criar_empresa(request):
    """
    View de criação de empresa
    """
    # Verificar permissão
    if not can_create_empresa(request.user):
        return HttpResponseForbidden(
            "Você não tem permissão para criar empresas"
        )
    
    if request.method == 'POST':
        form = EmpresaForm(request.POST)
        if form.is_valid():
            empresa = form.save()
            from django.contrib import messages
            messages.success(request, f"Empresa {empresa.nome_fantasia} criada!")
            return redirect('empresa_detalhe', empresa_id=empresa.id)
    else:
        form = EmpresaForm()
    
    context = {'form': form, 'acao': 'Criar'}
    return render(request, 'empresa_form.html', context)


# ==================== EXEMPLO 5: DELETAR COM PROTEÇÃO ====================

@login_required
def deletar_empresa(request, empresa_id):
    """
    View de deleção com confirmação
    """
    empresa = get_object_or_404(Empresa, id=empresa_id)
    
    # Verificar permissão
    if not can_delete_empresa(request.user, empresa):
        return HttpResponseForbidden(
            "Você não tem permissão para deletar empresas"
        )
    
    if request.method == 'POST':
        empresa_nome = empresa.nome_fantasia
        empresa.delete()
        from django.contrib import messages
        messages.success(request, f"Empresa {empresa_nome} deletada!")
        return redirect('empresa_list')
    
    context = {'empresa': empresa}
    return render(request, 'empresa_confirm_delete.html', context)


# ==================== EXEMPLO 6: ENDPOINT AJAX COM PROTEÇÃO ====================

from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json


@login_required
@require_POST
@csrf_exempt
def api_editar_empresa_ajax(request, empresa_id):
    """
    Endpoint AJAX para editar empresa
    POST: { "nome": "novo nome", "ativo": true }
    """
    # Verificação de permissão
    if not can_edit_empresa(request.user):
        return JsonResponse({
            'sucesso': False,
            'erro': 'Acesso negado'
        }, status=403)
    
    try:
        empresa = Empresa.objects.get(id=empresa_id)
    except Empresa.DoesNotExist:
        return JsonResponse({
            'sucesso': False,
            'erro': 'Empresa não encontrada'
        }, status=404)
    
    # Processar dados
    try:
        data = json.loads(request.body)
        empresa.nome_fantasia = data.get('nome', empresa.nome_fantasia)
        empresa.ativo = data.get('ativo', empresa.ativo)
        empresa.save()
        
        return JsonResponse({
            'sucesso': True,
            'mensagem': 'Empresa atualizada com sucesso'
        })
    except Exception as e:
        return JsonResponse({
            'sucesso': False,
            'erro': str(e)
        }, status=400)


# ==================== EXEMPLO 7: CLASS-BASED VIEW ====================

from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy


class EmpresaListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Class-based view para listar empresas
    Usa mixin UserPassesTestMixin para verificação de permissões
    """
    model = Empresa
    template_name = 'empresa_list.html'
    context_object_name = 'empresas'
    paginate_by = 20
    
    def test_func(self):
        """Verifica se usuário pode acessar"""
        return can_list_empresa(self.request.user)
    
    def handle_no_permission(self):
        """O que fazer se falhar no test_func"""
        return HttpResponseForbidden("Você não tem permissão para acessar")
    
    def get_context_data(self, **kwargs):
        """Adiciona dados de permissão ao contexto"""
        context = super().get_context_data(**kwargs)
        context['pode_criar'] = can_create_empresa(self.request.user)
        context['pode_editar'] = can_edit_empresa(self.request.user)
        context['pode_deletar'] = can_delete_empresa(self.request.user)
        return context


class EmpresaCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Criar empresa com proteção
    """
    model = Empresa
    form_class = EmpresaForm
    template_name = 'empresa_form.html'
    success_url = reverse_lazy('empresa_list')
    
    def test_func(self):
        return can_create_empresa(self.request.user)
    
    def handle_no_permission(self):
        return HttpResponseForbidden("Você não tem permissão para criar empresas")


class EmpresaUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Editar empresa com proteção
    """
    model = Empresa
    form_class = EmpresaForm
    template_name = 'empresa_form.html'
    pk_url_kwarg = 'empresa_id'
    
    def test_func(self):
        return can_edit_empresa(self.request.user)
    
    def handle_no_permission(self):
        return HttpResponseForbidden("Você não tem permissão para editar")


# ==================== EXEMPLO 8: TEMPLATE - MOSTRANDO AÇÕES CONDICIONAIS ====================

"""
<!-- empresa_detalhe.html -->

{% extends "core/base.html" %}

{% block content %}
<div class="container">
    <h1>{{ empresa.nome_fantasia }}</h1>
    
    <div class="action-buttons mb-3">
        {% if actions.editar %}
            <a href="{% url 'empresa_edit' empresa.id %}" class="btn btn-warning">
                <i class="bi bi-pencil-square"></i> Editar
            </a>
        {% endif %}
        
        {% if actions.upload_certificado %}
            <a href="{% url 'certificado_create' %}?empresa={{ empresa.id }}" class="btn btn-info">
                <i class="bi bi-cloud-upload"></i> Upload Certificado
            </a>
        {% endif %}
        
        {% if actions.fazer_download %}
            <a href="{% url 'download_manual' %}?empresa={{ empresa.id }}" class="btn btn-success">
                <i class="bi bi-cloud-download"></i> Download NFs
            </a>
        {% endif %}
        
        {% if actions.deletar %}
            <a href="{% url 'empresa_delete' empresa.id %}" class="btn btn-danger">
                <i class="bi bi-trash"></i> Deletar
            </a>
        {% endif %}
    </div>
    
    <!-- Informações da empresa -->
    <div class="card">
        <div class="card-body">
            <p><strong>CNPJ:</strong> {{ empresa.cnpj }}</p>
            <p><strong>Razão Social:</strong> {{ empresa.razao_social }}</p>
            <p><strong>Status:</strong> {% if empresa.ativo %}Ativo{% else %}Inativo{% endif %}</p>
        </div>
    </div>
</div>
{% endblock %}
"""


# ==================== EXEMPLO 9: PROTEÇÃO EM MÚLTIPLAS PERMISSÕES ====================

from core.permissions import user_has_any_permission, user_has_all_permissions


def dashboard_empresa(request):
    """
    Dashboard que requer múltiplas permissões
    """
    # Precisa ter PELO MENOS UMA destas permissões
    if not user_has_any_permission(
        request.user,
        'empresa.view',
        'certificado.view',
        'nfse_downloader.view',
    ):
        return HttpResponseForbidden("Acesso negado")
    
    # Para ver dados financeiros, requer AMBAS
    pode_ver_financeiro = user_has_all_permissions(
        request.user,
        'empresa.view_financeiro',
        'empresa.list',
    )
    
    context = {
        'pode_ver_financeiro': pode_ver_financeiro,
    }
    
    return render(request, 'dashboard_empresa.html', context)


# ==================== EXEMPLO 10: COMBINANDO TUDO ====================

@login_required
def painel_empresas(request):
    """
    Painel completo com todos os tipos de proteção/ações
    """
    # Base: pode ver empresas?
    if not can_view_empresa(request.user):
        return HttpResponseForbidden("Acesso negado")
    
    # Buscar dados
    empresas = Empresa.objects.filter(ativo=True)
    
    # Cada ação tem sua permissão
    pode_criar = can_create_empresa(request.user)
    pode_editar = can_edit_empresa(request.user)
    pode_deletar = can_delete_empresa(request.user)
    pode_upload_cert = check_perm(request.user, 'certificado.upload')
    pode_download = check_perm(request.user, 'nfse_downloader.download_manual')
    pode_ver_financeiro = check_perm(request.user, 'empresa.view_financeiro')
    
    context = {
        'empresas': empresas,
        'permissoes': {
            'criar': pode_criar,
            'editar': pode_editar,
            'deletar': pode_deletar,
            'upload_cert': pode_upload_cert,
            'download': pode_download,
            'ver_financeiro': pode_ver_financeiro,
        },
    }
    
    return render(request, 'painel_empresas.html', context)


"""
<!-- painel_empresas.html - TEMPLATE COM TUDO DINÂMICO -->

{% extends "core/base.html" %}

{% block content %}
<div class="container-fluid">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h1>Empresas</h1>
        {% if permissoes.criar %}
            <a href="{% url 'empresa_create' %}" class="btn btn-success">
                <i class="bi bi-plus-circle"></i> Criar Empresa
            </a>
        {% endif %}
    </div>
    
    <table class="table table-hover">
        <thead>
            <tr>
                <th>Nome</th>
                <th>CNPJ</th>
                <th>Status</th>
                {% if permissoes.editar or permissoes.deletar or permissoes.download %}
                    <th>Ações</th>
                {% endif %}
            </tr>
        </thead>
        <tbody>
            {% for empresa in empresas %}
                <tr>
                    <td><a href="{% url 'empresa_detalhe' empresa.id %}">{{ empresa.nome_fantasia }}</a></td>
                    <td>{{ empresa.cnpj }}</td>
                    <td>
                        <span class="badge bg-{% if empresa.ativo %}success{% else %}danger{% endif %}">
                            {% if empresa.ativo %}Ativa{% else %}Inativa{% endif %}
                        </span>
                    </td>
                    {% if permissoes.editar or permissoes.deletar or permissoes.download %}
                        <td>
                            {% if permissoes.download %}
                                <a href="{% url 'download_manual' %}?empresa={{ empresa.id }}" class="btn btn-sm btn-success" title="Download">
                                    <i class="bi bi-cloud-download"></i>
                                </a>
                            {% endif %}
                            {% if permissoes.editar %}
                                <a href="{% url 'empresa_edit' empresa.id %}" class="btn btn-sm btn-warning" title="Editar">
                                    <i class="bi bi-pencil"></i>
                                </a>
                            {% endif %}
                            {% if permissoes.deletar %}
                                <a href="{% url 'empresa_delete' empresa.id %}" class="btn btn-sm btn-danger" title="Deletar">
                                    <i class="bi bi-trash"></i>
                                </a>
                            {% endif %}
                        </td>
                    {% endif %}
                </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}
"""
