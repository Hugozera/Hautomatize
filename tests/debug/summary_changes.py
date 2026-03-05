#!/usr/bin/env python
"""Script para listar todas as mudanças feitas"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Empresa

print("=" * 60)
print("RESUMO DAS ALTERAÇÕES")
print("=" * 60)

print("\n✅ LIMITAÇÕES REMOVIDAS:\n")
print("1. painel_views.py, linha 601:")
print("   ANTES: empresas = Empresa.objects.filter(ativo=True).order_by('nome_fantasia')[:100]")
print("   DEPOIS: empresas = Empresa.objects.filter(ativo=True).order_by('nome_fantasia')")

print("\n2. painel_views.py, linha 691:")
print("   ANTES: empresas = Empresa.objects.filter(ativo=True).order_by('nome_fantasia')[:100]")
print("   DEPOIS: empresas = Empresa.objects.filter(ativo=True).order_by('nome_fantasia')")

print("\n3. views.py (empresa_search API), linha 1798:")
print("   ANTES: qs = Empresa.objects.filter(...)[:20]")
print("   DEPOIS: qs = Empresa.objects.filter(...)[:200]")

print("\n✅ LÓGICA DE PERMISSÕES CORRIGIDA:\n")
print("4. Garantido que superusers sempre vejam todas as empresas nas views:")
print("   - agendamento_list")
print("   - dashboard")
print("   - historico")
print("   - listar_downloads")

print("\n" + "=" * 60)
print("VERIFICAÇÃO DO USUÁRIO")
print("=" * 60)

user = User.objects.filter(username__icontains='hugo').first()
if user:
    print(f"\n✅ Usuário: {user.username}")
    print(f"   Email: {user.email}")
    print(f"   É superuser: {'SIM' if user.is_superuser else 'NÃO'}")
    print(f"   É staff: {'SIM' if user.is_staff else 'NÃO'}")
    
    if hasattr(user, 'pessoa'):
        print(f"   Tem objeto pessoa: SIM")
        print(f"   Empresas associadas ao pessoa: {user.pessoa.empresas.count()}")
    
    print(f"\n✅ TOTAL DE EMPRESAS NO SISTEMA:")
    total = Empresa.objects.count()
    ativas = Empresa.objects.filter(ativo=True).count()
    print(f"   Total: {total} empresas")
    print(f"   Ativas: {ativas} empresas")
    
    print(f"\n✅ O que o usuário {user.username} DEVE ver:")
    print(f"   - Na view empresa_list: {total} empresas (todas)")
    print(f"   - Na view dashboard: {ativas} empresas (ativas)")
    print(f"   - No painel secretaria: TODAS as empresas (sem limite de 100)")
    print(f"   - Na API de busca: até 200 resultados por busca (antes era 20)")
    
print("\n" + "=" * 60)
print("PRÓXIMOS PASSOS")
print("=" * 60)
print("\n1. Faça logout e login novamente no sistema")
print("2. Limpe o cache do navegador (Ctrl+Shift+Delete)")
print("3. Acesse as páginas de empresas")
print("4. Todas as empresas devem estar visíveis agora!")
print("\n" + "=" * 60)
