"""
Exemplos de uso do sistema de permissões

Este arquivo demonstra como usar o sistema de permissões em diferentes contextos.
Copied pode ser usado como referência para implementação.
"""

# ==================== EXEMPLO 1: Em uma View ====================

# views.py
from django.shortcuts import render, redirect
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from core.permissions import (
    check_perm,
    can_edit_empresa,
    can_download_nota,
    get_user_permissions,
)
from core.models import Empresa


@login_required
def editar_empresa(request, empresa_id):
    """Exemplo de proteção de view com permissões"""
    
    # Verificação 1: Permissão simples
    if not check_perm(request.user, 'empresa.edit'):
        return HttpResponseForbidden("Você não tem permissão para editar empresas")
    
    # Verificação 2: Usar função específica
    if not can_edit_empresa(request.user):
        return HttpResponseForbidden("Acesso negado")
    
    empresa = Empresa.objects.get(pk=empresa_id)
    
    if request.method == 'POST':
        # processar edição
        pass
    
    # Passar permissões para template
    context = {
        'empresa': empresa,
        'pode_editar': can_edit_empresa(request.user),
        'permissoes': get_user_permissions(request.user),
    }
    
    return render(request, 'editar_empresa.html', context)


# ==================== EXEMPLO 2: Em um Template ====================

"""
<!-- template: editar_empresa.html -->

{% if pode_editar %}
    <form method="post">
        {% csrf_token %}
        <input type="text" name="nome" value="{{ empresa.nome_fantasia }}">
        <button type="submit">Salvar</button>
    </form>
{% else %}
    <p class="error">Você não tem permissão para editar esta empresa</p>
{% endif %}

<!-- Mostrar menu condicional -->
<nav>
    {% if user.pessoa|has_perm:'empresa.view' %}
        <a href="{% url 'empresas' %}">Empresas</a>
    {% endif %}
    
    {% if user.pessoa|has_perm:'certificado.manage' %}
        <a href="{% url 'certificados' %}">Certificados</a>
    {% endif %}
    
    {% if user.pessoa|has_perm:'painel.view' %}
        <a href="{% url 'painel' %}">Painel</a>
    {% endif %}
</nav>
"""


# ==================== EXEMPLO 3: Verificar Múltiplas Permissões ====================

from core.permissions import user_has_any_permission, user_has_all_permissions

def dashboard(request):
    """Usuário só vê dashboard se tiver ao menos 1 permissão"""
    
    # Verificar se tem ALGUMA permissão
    if user_has_any_permission(
        request.user,
        'empresa.view',
        'conversor.view',
        'painel.view',
    ):
        # Mostrar dashboard
        pass
    else:
        return HttpResponseForbidden("Você não tem acesso ao sistema")

def administracao(request):
    """Usuário só acessa se tiver TODAS as permissões"""
    
    if user_has_all_permissions(
        request.user,
        'sistema.edit_config',
        'sistema.manage_users',
    ):
        # Permitir acesso administrativo
        pass
    else:
        return HttpResponseForbidden("Acesso negado")


# ==================== EXEMPLO 4: Management Command ====================

from django.core.management.base import BaseCommand
from core.permissions import check_perm

class Command(BaseCommand):
    help = 'Exemplo de command que usa permissões'
    
    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
    
    def handle(self, *args, **options):
        from django.contrib.auth.models import User
        
        username = options['username']
        user = User.objects.get(username=username)
        
        # Verificar permissão
        if check_perm(user, 'nfse_downloader.download_manual'):
            self.stdout.write('✅ Usuário pode executar downloads')
        else:
            self.stdout.write('❌ Usuário NÃO pode executar downloads')


# ==================== EXEMPLO 5: Class-Based View ====================

from django.views import View
from django.views.generic import ListView
from django.http import HttpResponseForbidden
from core.permissions import can_list_pessoa

class PessoaListView(ListView):
    """Listar pessoas - protegido por permissão"""
    
    model = Pessoa
    template_name = 'pessoas_list.html'
    paginate_by = 20
    
    def get(self, request, *args, **kwargs):
        # Verificar permissão
        if not can_list_pessoa(request.user):
            return HttpResponseForbidden("Você não tem permissão para ver pessoas")
        
        return super().get(request, *args, **kwargs)


# ==================== EXEMPLO 6: Adicionar Contexto Global ====================

# middleware.py
from core.permissions import get_user_permissions

class PermissionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Adicionar permissões ao request
        if request.user.is_authenticated:
            request.user_permissions = get_user_permissions(request.user)
        else:
            request.user_permissions = []
        
        response = self.get_response(request)
        return response


# ==================== EXEMPLO 7: Programação Defensiva ====================

from core.permissions import check_perm
from core.models import Empresa

def deletar_empresa(request, empresa_id):
    """Deletar empresa com verificações robustas"""
    
    # 1. Verificar autenticação
    if not request.user.is_authenticated:
        return HttpResponseForbidden("Faça login primeiro")
    
    # 2. Verificar permissão específica
    if not check_perm(request.user, 'empresa.delete'):
        return HttpResponseForbidden("Você não tem permissão para deletar empresas")
    
    # 3. Verificar existência
    try:
        empresa = Empresa.objects.get(pk=empresa_id)
    except Empresa.DoesNotExist:
        return HttpResponseForbidden("Empresa não encontrada")
    
    # 4. Fazer a ação
    empresa.delete()
    
    from django.contrib import messages
    messages.success(request, f"Empresa {empresa.nome_fantasia} deletada com sucesso")
    
    return redirect('empresas_list')


# ==================== EXEMPLO 8: Combinar com Django Permissions ====================

from django.contrib.auth.models import Permission
from django.contrib.auth.decorators import permission_required
from core.permissions import check_perm

def view_relatorio(request):
    """Combinar Django permissions com sistema customizado"""
    
    # Verificar ambos os sistemas
    custom_perm = check_perm(request.user, 'relatorio.view')
    django_perm = request.user.has_perm('relatorio.view')
    
    if not (custom_perm or django_perm):
        return HttpResponseForbidden("Sem permissão")
    
    return render(request, 'relatorio.html')


# ==================== EXEMPLO 9: Listar Permissões por Módulo ====================

from core.permission_system import get_module_permissions

def admin_permissoes(request):
    """Página de admin que mostra permissões por módulo"""
    
    from core.permission_system import PERMISSION_MAP
    
    context = {
        'modulos': {}
    }
    
    for modulo, permissoes in PERMISSION_MAP.items():
        context['modulos'][modulo] = {
            'total': len(permissoes),
            'permissoes': list(permissoes.items())
        }
    
    return render(request, 'admin_permissoes.html', context)


# ==================== EXEMPLO 10: Auditoria de Permissões ====================

from core.permission_system import get_permissions_for_role
from core.models import Role, Pessoa

def audit_permissions_change(username, old_roles, new_roles):
    """Log de auditoria quando permissões são alteradas"""
    
    import logging
    logger = logging.getLogger(__name__)
    
    # Calcular permissões antigas
    old_perms = set()
    for role_code in old_roles:
        old_perms.update(get_permissions_for_role(role_code))
    
    # Calcular permissões novas
    new_perms = set()
    for role_code in new_roles:
        new_perms.update(get_permissions_for_role(role_code))
    
    # Registrar mudanças
    added = new_perms - old_perms
    removed = old_perms - new_perms
    
    if added:
        logger.info(f"{username}: Permissões adicionadas: {added}")
    
    if removed:
        logger.info(f"{username}: Permissões removidas: {removed}")


# ==================== COMANDOS DE TESTE ====================

"""
# Testar no Django Shell:

python manage.py shell

from django.contrib.auth.models import User
from core.models import Pessoa, Role
from core.permissions import check_perm, get_user_permissions

# 1. Obter usuário Hugo
hugo = User.objects.get(pk=1)

# 2. Verificar permissões
check_perm(hugo, 'empresa.edit')  # True
check_perm(hugo, 'sistema.admin')  # True

# 3. Listar todas as permissões
perms = get_user_permissions(hugo)
print(f"Hugo tem {len(perms)} permissões")

# 4. Verificar papel
print(list(hugo.pessoa.roles.values_list('name', flat=True)))

# 5. Adicionar nova pessoa com papel
novo_user = User.objects.create_user('joao', 'joao@example.com')
nova_pessoa = Pessoa.objects.create(user=novo_user, cpf='12345678901')
role_analista = Role.objects.get(codename='analista')
nova_pessoa.roles.add(role_analista)

# 6. Verificar permissões do novo usuário
check_perm(novo_user, 'painel.view')  # True
check_perm(novo_user, 'empresa.edit')  # False
"""


# ==================== RESUMO DE COMANDOS GIT ====================

"""
# Após implementar permissões:

git add core/permission_system.py
git add core/permissions.py
git add core/management/commands/setup_permissions.py
git add core/management/commands/manage_user_permissions.py
git add core/management/commands/check_permissions.py
git add PERMISSIONS_DOCUMENTATION.md

git commit -m "feat: sistema completo de permissões com roles independentes

- Criado permission_system.py com mapa completo de permissões
- 5 papéis pré-definidos (Admin, Gestor, Analista, Operador, Visualizador)
- Management commands para setup e gerenciamento
- Hugo (id=1) com acesso total ao sistema
- Permissões e papéis são independentes
- Documentação completa"

git push origin main
"""
