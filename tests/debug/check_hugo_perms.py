#!/usr/bin/env python
"""Verificar permissões de Hugo"""

import django
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from django.contrib.auth.models import User
from core.permissions import check_perm, get_user_permissions
from core.models import Pessoa, Role

# Obter Hugo
hugo = User.objects.get(pk=1)
print(f"\n{'='*80}")
print(f" VERIFICANDO PERMISSÕES DE HUGO")
print(f"{'='*80}\n")

print(f"Usuario: {hugo.username} (ID: {hugo.pk})")
print(f"Email: {hugo.email}")
print(f"Superuser: {hugo.is_superuser}")
print(f"Staff: {hugo.is_staff}\n")

# Verificar permissão específica
has_edit = check_perm(hugo, 'pessoa.edit')
print(f"Tem permissão 'pessoa.edit': {has_edit}")

# Listar todas as permissões
all_perms = get_user_permissions(hugo)
print(f"\nTotal de permissões: {len(all_perms)}")

# Verificar papéis
try:
    pessoa = Pessoa.objects.get(user=hugo)
    roles = pessoa.roles.all()
    print(f"Papéis: {[r.name for r in roles]}")
    print(f"\nPrimeiras 10 permissões:")
    for perm in all_perms[:10]:
        print(f"  - {perm}")
except Exception as e:
    print(f"Erro: {e}")

print(f"\n{'='*80}\n")
