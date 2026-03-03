"""
Exemplos práticos de uso da interface visual de permissões
e do sistema de permissões do NFSE Downloader
"""

# ============================================================================
# EXEMPLO 1: Criar novo usuário com permissões via interface
# ============================================================================
"""
URL: http://localhost:8000/admin/core/pessoa/add/

Passos no formulário visual:

1. Avatar:
   - Arraste uma imagem ou clique para selecionar
   - Visualização em tempo real

2. Dados do usuário:
   - Username: hugo_martins
   - Email: hugo@empresa.com
   - First Name: Hugo
   - Last Name: Martins
   - CPF: 12345678901
   - Telefone: 11999999999
   - Ativo: ✓

3. Senha:
   - Veja o medidor ficar verde/azul com senha forte
   - Confirme a senha no segundo campo

4. Papéis (Roles):
   - Clique no card "Gestor" para selecioná-lo
   - O card fica destacado com borda azul
   - Badge mostra "52 permissões"

5. Permissões Diretas:
   - Use busca para "nfse"
   - Marque "download_nota" e "view_nfse"
   - Clique "Expandir All" para ver tudo

6. Resumo:
   - Mostra: 1 papel, 2 permissões diretas
   - Total: 54 permissões (52 + 2)

7. Salvar: Clique em "Salvar"
"""


# ============================================================================
# EXEMPLO 2: Verificar permissões no código Python
# ============================================================================

from core.permissions import check_perm
from core.models import Pessoa
from django.contrib.auth.models import User

# Obter usuário
user = User.objects.get(username='hugo_martins')

# ✅ VERIFICAR PERMISSÃO ÚNICA
if check_perm(user, 'add_empresa'):
    print("✅ Hugo pode adicionar empresas")
else:
    print("❌ Hugo não pode adicionar empresas")

# ✅ VERIFICAR MÚLTIPLAS PERMISSÕES (requer TODAS)
if check_perm(user, ['view_empresa', 'edit_empresa']):
    print("✅ Hugo pode ver E editar empresas")
else:
    print("❌ Hugo não tem todas as permissões")

# ✅ VERIFICAR QUALQUER PERMISSÃO
from core.permissions import user_has_any_permission
if user_has_any_permission(user, ['delete_empresa', 'delete_pessoa']):
    print("✅ Hugo pode deletar algo")
else:
    print("❌ Hugo não pode deletar")

# ✅ LISTAR TODAS AS PERMISSÕES DO USUÁRIO
from core.permissions import get_user_permissions
perms = get_user_permissions(user)
print(f"Permissões de Hugo: {len(perms)} total")
for perm in perms[:5]:
    print(f"  - {perm}")


# ============================================================================
# EXEMPLO 3: Usar em Views com decoradores
# ============================================================================

from django.shortcuts import redirect
from functools import wraps

def permission_required(perm_code):
    """Decorador para verificar permissão antes de executar view"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if check_perm(request.user, perm_code):
                return view_func(request, *args, **kwargs)
            else:
                # Log do acesso negado
                print(f"❌ Acesso negado para {request.user}: {perm_code}")
                return redirect('permission_denied')
        return wrapper
    return decorator


# Uso em view
@permission_required('add_nota_fiscal')
def create_nota_fiscal(request):
    """Apenas usuários com permissão podem acessar"""
    # ... lógica da view
    return render(request, 'template.html')


# ============================================================================
# EXEMPLO 4: Verificações em templates
# ============================================================================

"""
No seu template HTML (Django templates):

{% load custom_tags %}

<!-- Verificar permissão única -->
{% if user|has_perm:"view_empresa" %}
    <button>Ver Empresa</button>
{% endif %}

<!-- Verificar múltiplas permissões -->
{% if user|has_perm:"edit_empresa" %}
    <div class="edit-section">
        <input type="text" name="empresa_name">
        <button>Salvar</button>
    </div>
{% endif %}

<!-- Verificar qualquer permissão -->
{% if user|has_any_perm:"download_nota,view_nfse" %}
    <section class="nota-fiscal-area">
        <!-- Conteúdo -->
    </section>
{% endif %}
"""

# Custom template tag para verificar permissão
from django import template
register = template.Library()

@register.filter
def has_perm(user, perm_code):
    """Template filter para verificar permissão"""
    return check_perm(user, perm_code)

@register.filter
def has_any_perm(user, perm_codes):
    """Template filter para verificar qualquer permissão"""
    if ',' in str(perm_codes):
        perms = [p.strip() for p in perm_codes.split(',')]
    else:
        perms = [perm_codes]
    return user_has_any_permission(user, perms)


# ============================================================================
# EXEMPLO 5: Gerenciar permissões programaticamente
# ============================================================================

from core.models import Pessoa, Role
from core.permission_system import ROLE_DEFINITIONS

# Obter pessoa e suas roles atuais
pessoa = Pessoa.objects.get(username='hugo_martins')

# ✅ ADICIONAR PAPEL
gestor_role = Role.objects.get(codename='gestor')
pessoa.roles.add(gestor_role)

# ✅ REMOVER PAPEL
analista_role = Role.objects.get(codename='analista')
pessoa.roles.remove(analista_role)

# ✅ ADICIONAR PERMISSÃO DIRETA
current_perms = pessoa.permissions.split(',') if pessoa.permissions else []
current_perms.append('download_nota')
pessoa.permissions = ','.join(set(current_perms))
pessoa.save()

# ✅ REMOVER PERMISSÃO DIRETA
if 'download_nota' in pessoa.permissions:
    perms = pessoa.permissions.split(',')
    perms.remove('download_nota')
    pessoa.permissions = ','.join(perms)
    pessoa.save()

# ✅ LISTAR TODAS AS PERMISSÕES (diretas + via papéis)
all_perms = pessoa.perm_list()
print(f"Permissões totais: {all_perms}")

# ✅ VERIFICAR PERMISSÃO ESPECÍFICA
has_perm = pessoa.has_perm_code('view_empresa')
print(f"Tem permissão 'view_empresa': {has_perm}")


# ============================================================================
# EXEMPLO 6: Usar management commands
# ============================================================================

"""
# Setup inicial do sistema
python manage.py setup_permissions --reset --assign-hugo-admin

# Verificar permissões de um usuário
python manage.py check_permissions --user hugo_martins@gmail.com

# Verificar permissões de um papel
python manage.py check_permissions --role gestor

# Verificar permissões de um módulo
python manage.py check_permissions --module empresa

# Gerenciar permissões de usuário
python manage.py manage_user_permissions \\
    --user hugo_martins \\
    --add-role gestor \\
    --add-perm download_nota

# Remover papel
python manage.py manage_user_permissions \\
    --user hugo_martins \\
    --remove-role analista

# Listar todas as permissões de um usuário
python manage.py manage_user_permissions \\
    --user hugo_martins \\
    --list-perms
"""


# ============================================================================
# EXEMPLO 7: Casos de uso comuns
# ============================================================================

def criar_gerente_comercial():
    """Criar novo gerente com permissões apropriadas"""
    # Criar usuário Django
    user = User.objects.create_user(
        username='gerente_001',
        email='gerente@empresa.com',
        password='senha_forte_123!'
    )
    
    # Criar Pessoa
    pessoa = Pessoa.objects.create(
        user=user,
        cpf='12345678901',
        telefone='11999999999'
    )
    
    # Atribuir papel de Gestor
    gestor = Role.objects.get(codename='gestor')
    pessoa.roles.add(gestor)
    
    print(f"✅ Gerente criado: {pessoa.user.username}")
    print(f"Permissões: {len(pessoa.perm_list())}")
    return pessoa


def criar_operator_limitado():
    """Criar operador com acesso apenas a certificados"""
    user = User.objects.create_user(
        username='operator_001',
        email='operator@empresa.com',
        password='senha_123'
    )
    
    pessoa = Pessoa.objects.create(
        user=user,
        cpf='98765432100',
        telefone='11988888888'
    )
    
    # Atribuir papel base
    operador = Role.objects.get(codename='operador')
    pessoa.roles.add(operador)
    
    # Adicionar permissões específicas
    pessoa.permissions = 'view_certificado,download_certificado'
    pessoa.save()
    
    print(f"✅ Operador criado: {pessoa.user.username}")
    return pessoa


def verificar_acesso_empresa(usuario, empresa_id):
    """Verificar se usuário pode acessar empresa específica"""
    if not check_perm(usuario, 'view_empresa'):
        return False, "Sem permissão para visualizar empresas"
    
    # Aqui você pode adicionar lógica de empresa específica
    # Por exemplo, verificar se a empresa pertence ao grupo do usuário
    
    return True, "Acesso concedido"


def audit_permissoes_usuario(usuario):
    """Gerar relatório de permissões de um usuário"""
    from core.permission_system import ROLE_DEFINITIONS
    
    pessoa = Pessoa.objects.get(user=usuario)
    report = {
        'username': usuario.username,
        'email': usuario.email,
        'roles': list(pessoa.roles.values_list('name', flat=True)),
        'direct_permissions': pessoa.perm_list(),
        'total_permissions': len(pessoa.perm_list()),
    }
    
    # Contar permissões por módulo
    modules = {}
    for perm in pessoa.perm_list():
        module = perm.split('_')[0]
        modules[module] = modules.get(module, 0) + 1
    
    report['permissions_by_module'] = modules
    
    return report


# ============================================================================
# EXEMPLO 8: Testes de permissão
# ============================================================================

from django.test import TestCase
from core.models import Pessoa, Role
from core.permissions import check_perm

class PermissionTestCase(TestCase):
    """Testes para o sistema de permissões"""
    
    def setUp(self):
        """Configurar dados para testes"""
        self.user = User.objects.create_user(
            username='test_user',
            email='test@example.com',
            password='test123'
        )
        self.pessoa = Pessoa.objects.create(user=self.user)
    
    def test_admin_has_all_permissions(self):
        """Admin deve ter todas as permissões"""
        admin_role = Role.objects.get(codename='admin')
        self.pessoa.roles.add(admin_role)
        
        # Verificar várias permissões
        assert check_perm(self.user, 'add_empresa')
        assert check_perm(self.user, 'delete_nfse')
        assert check_perm(self.user, 'view_relatorio')
    
    def test_operator_limited_permissions(self):
        """Operador tem apenas permissões limitadas"""
        op_role = Role.objects.get(codename='operador')
        self.pessoa.roles.add(op_role)
        
        # Deve ter permissão de visualizar
        assert check_perm(self.user, 'view_empresa')
        # Não deve ter permissão de deletar
        assert not check_perm(self.user, 'delete_empresa')
    
    def test_direct_permission_override(self):
        """Permissões diretas funcionam mesmo sem papel"""
        # Adicionar permissão direta
        self.pessoa.permissions = 'download_nota'
        self.pessoa.save()
        
        # Deve ter a permissão
        assert check_perm(self.user, 'download_nota')
        # Mas não outras
        assert not check_perm(self.user, 'view_empresa')


# ============================================================================
# EXEMPLO 9: Integração com formulário Django
# ============================================================================

from django import forms
from core.models import Pessoa, Role

class PessoaPermissionForm(forms.ModelForm):
    """Formulário para gerenciar permissões de pessoa"""
    
    class Meta:
        model = Pessoa
        fields = ['user', 'roles', 'permissions']
    
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Papéis (Roles)"
    )
    
    permissions = forms.MultipleChoiceField(
        choices=[],  # Será populado no __init__
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Permissões Diretas"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Popular choices de permissões
        from core.permission_system import get_all_permissions
        all_perms = get_all_permissions()
        self.fields['permissions'].choices = [
            (perm, perm.replace('_', ' ').title()) for perm in all_perms
        ]
    
    def save(self, commit=True):
        pessoa = super().save(commit=False)
        
        # Salvar roles (many-to-many)
        if commit:
            pessoa.save()
            pessoa.roles.set(self.cleaned_data['roles'])
        
        # Salvar permissões diretas
        perms = self.cleaned_data['permissions']
        pessoa.permissions = ','.join(perms) if perms else ''
        
        if commit:
            pessoa.save()
        
        return pessoa


# ============================================================================
# EXEMPLO 10: Dashboard de permissões
# ============================================================================

def permission_dashboard_data():
    """Gerar dados para dashboard de permissões"""
    from core.permission_system import ROLE_DEFINITIONS
    
    dashboard = {
        'total_users': Pessoa.objects.count(),
        'users_with_roles': Pessoa.objects.exclude(roles__isnull=True).distinct().count(),
        'total_roles': Role.objects.count(),
        'role_distribution': {},
        'permission_stats': {}
    }
    
    # Distribuição por papel
    for role in Role.objects.all():
        dashboard['role_distribution'][role.name] = role.pessoa_set.count()
    
    # Estatísticas de permissões
    all_pessoas = Pessoa.objects.all()
    for pessoa in all_pessoa:
        perm_count = len(pessoa.perm_list())
        if perm_count not in dashboard['permission_stats']:
            dashboard['permission_stats'][perm_count] = 0
        dashboard['permission_stats'][perm_count] += 1
    
    return dashboard

"""
Resultado do dashboard:
{
    'total_users': 15,
    'users_with_roles': 12,
    'total_roles': 5,
    'role_distribution': {
        'Admin': 1,
        'Gestor': 3,
        'Analista': 5,
        'Operador': 4,
        'Visualizador': 2
    },
    'permission_stats': {
        90: 1,  # 1 usuário com 90 permissões (admin)
        52: 3,  # 3 usuários com 52 permissões (gestores)
        28: 5,  # etc...
        21: 4,
        15: 2
    }
}
"""


if __name__ == '__main__':
    print("Exemplos de uso do sistema de permissões visual")
    print("=" * 60)
    print("Ver os comentários e código acima para detalhes")
