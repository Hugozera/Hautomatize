import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Pessoa
from core.permissions import check_perm, can_edit_pessoa

# Procurar usuario Hugo
hugo_user = User.objects.filter(username__icontains='hugo').first()

if not hugo_user:
    print("-- Usuarios Hugo nao encontrado!")
else:
    print(f"\n++ Usuario encontrado: {hugo_user.username}")
    print(f"   Nome: {hugo_user.get_full_name()}")
    print(f"   Email: {hugo_user.email}")
    
    # Verificar objeto Pessoa
    try:
        pessoa = hugo_user.pessoa
        print(f"\n++ Objeto Pessoa vinculado")
        print(f"   Pessoa ID: {pessoa.pk}")
        print(f"   Foto: {'Sim' if pessoa.foto else 'Nao'}")
        print(f"   Ativo: {'Sim' if pessoa.ativo else 'Nao'}")
        
        # Listar permissoes
        perms = pessoa.perm_list()
        print(f"\n-- Total de permissoes: {len(perms)}")
        
        # Agrupar por modulo
        modules = {}
        for perm in perms:
            if '.' in perm:
                mod = perm.split('.')[0]
                if mod not in modules:
                    modules[mod] = []
                modules[mod].append(perm)
        
        print("\n   Permissoes por modulo:")
        for mod in sorted(modules.keys()):
            print(f"   * {mod}: {len(modules[mod])} acoes")
        
        # Testar permissoes criticas
        print("\n-- Permissoes Criticas:")
        
        perms_to_test = [
            ('pessoa.edit', 'Editar pessoas/usuarios'),
            ('empresa.edit', 'Editar empresas'),
            ('certificado.manage', 'Gerenciar certificados'),
            ('conversor.use', 'Usar conversor'),
        ]
        
        for perm_code, desc in perms_to_test:
            has_perm = check_perm(hugo_user, perm_code)
            status = '++' if has_perm else '--'
            print(f"   {status} {perm_code}: {desc}")
        
        # Testar funcao can_edit_pessoa
        print("\n-- Testes de Funcao:")
        can_edit = can_edit_pessoa(hugo_user, pessoa)
        status = '++' if can_edit else '--'
        print(f"   {status} can_edit_pessoa(hugo_user, pessoa_obj): {can_edit}")
        
    except Exception as e:
        print(f"\n-- Erro ao acessar Pessoa: {str(e)}")

print("\n" + "="*60)
print("Resultado Final: VERIFICACAO DE PERMISSOES DO HUGO COMPLETA")
print("="*60)
