#!/usr/bin/env python
"""Script para verificar o usuário hugomartinscavalcante"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Pessoa

# Procurar usuário
usuarios = User.objects.filter(username__icontains='hugo')
print(f"Usuários encontrados com 'hugo': {usuarios.count()}")
for u in usuarios:
    print(f"\n--- Usuário: {u.username} ---")
    print(f"  Email: {u.email}")
    print(f"  Is superuser: {u.is_superuser}")
    print(f"  Is staff: {u.is_staff}")
    print(f"  Is active: {u.is_active}")
    
    if hasattr(u, 'pessoa'):
        pessoa = u.pessoa
        print(f"  Tem pessoa: Sim (ID {pessoa.id})")
        print(f"  Nome pessoa: {pessoa.nome}")
        print(f"  Empresas associadas: {pessoa.empresas.count()}")
    else:
        print(f"  Tem pessoa: Não")

# Verificar total de empresas
from core.models import Empresa
total_empresas = Empresa.objects.filter(ativo=True).count()
print(f"\n\nTotal de empresas ativas no sistema: {total_empresas}")
