"""
Script para verificar se Hugo tem todas as permissões necessárias e pode editar usuários.
"""
from django.contrib.auth.models import User
from core.models import Pessoa
from core.permissions import check_perm, can_edit_pessoa

# Procurar usuário Hugo
hugo_user = User.objects.filter(username__icontains='hugo').first()

if not hugo_user:
    print("❌ Usuário Hugo não encontrado!")
else:
    print(f"\n✅ Usuário encontrado: {hugo_user.username}")
    print(f"   Nome: {hugo_user.get_full_name()}")
    print(f"   Email: {hugo_user.email}")
    
    # Verificar objeto Pessoa
    try:
        pessoa = hugo_user.pessoa
        print(f"\n✅ Objeto Pessoa vinculado")
        print(f"   Pessoa ID: {pessoa.pk}")
        print(f"   Foto: {'Sim' if pessoa.foto else 'Não'}")
        print(f"   Ativo: {'Sim' if pessoa.ativo else 'Não'}")
        
        # Listar permissões
        perms = pessoa.perm_list()
        print(f"\n📋 Total de permissões: {len(perms)}")
        
        # Agrupar por módulo
        modules = {}
        for perm in perms:
            if '.' in perm:
                mod = perm.split('.')[0]
                if mod not in modules:
                    modules[mod] = []
                modules[mod].append(perm)
        
        print("\n   Permissões por módulo:")
        for mod in sorted(modules.keys()):
            print(f"   • {mod}: {len(modules[mod])} ações")
        
        # Testar permissões críticas
        print("\n🔐 Permissões Críticas:")
        
        perms_to_test = [
            ('pessoa.edit', 'Editar pessoas/usuários'),
            ('empresa.edit', 'Editar empresas'),
            ('certificado.manage', 'Gerenciar certificados'),
            ('conversor.use', 'Usar conversor'),
            ('painel.manage', 'Gerenciar painel'),
            ('role.manage', 'Gerenciar papéis/roles'),
        ]
        
        for perm_code, desc in perms_to_test:
            has_perm = check_perm(hugo_user, perm_code)
            status = '✅' if has_perm else '❌'
            print(f"   {status} {perm_code}: {desc}")
        
        # Testar função can_edit_pessoa
        print("\n🔧 Testes de Função:")
        can_edit = can_edit_pessoa(hugo_user, pessoa)
        status = '✅' if can_edit else '❌'
        print(f"   {status} can_edit_pessoa(hugo_user, pessoa_obj)")
        
        # Verificar roles
        roles = pessoa.roles.filter(ativo=True)
        print(f"\n👥 Papéis (Roles): {roles.count()}")
        for role in roles:
            print(f"   • {role.name} ({role.codename})")
            print(f"     - Ativo: {'Sim' if role.ativo else 'Não'}")
            print(f"     - Permissões: {len(role.perm_list())} ações")
        
    except Exception as e:
        print(f"\n❌ Erro ao acessar Pessoa: {str(e)}")

# Verificar se há outras pessoas para comparação
print("\n" + "="*60)
print("Resumo de Usuários do Sistema")
print("="*60)

all_users = User.objects.all()
print(f"\nTotal de usuários: {all_users.count()}")

for user in all_users[:5]:  # Mostrar apenas os primeiros 5
    try:
        pessoa = user.pessoa
        perm_count = len(pessoa.perm_list())
        print(f"  {user.username}: {perm_count} permissões")
    except:
        print(f"  {user.username}: Sem objeto Pessoa")
