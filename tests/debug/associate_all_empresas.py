#!/usr/bin/env python
"""Script OPCIONAL para associar todas as empresas ativas ao usuário hugomartinscavalcante
IMPORTANTE: Isso NÃO é necessário porque o usuário já é superuser e pode ver tudo.
Execute apenas se desejar ter essa associação explícita.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Empresa

# Buscar usuário
user = User.objects.filter(username__icontains='hugo').first()
if not user:
    print("❌ Usuário não encontrado!")
    exit(1)

if not hasattr(user, 'pessoa'):
    print("❌ Usuário não tem objeto pessoa!")
    exit(1)

pessoa = user.pessoa
print(f"✅ Usuário: {user.username}")
print(f"✅ Pessoa: {pessoa.nome}\n")

# Contar empresas ativas
empresas_ativas = Empresa.objects.filter(ativo=True)
total_ativas = empresas_ativas.count()

# Verificar quantas empresas já estão associadas
empresas_associadas_atual = pessoa.empresas.count()

print(f"Total de empresas ativas: {total_ativas}")
print(f"Empresas já associadas: {empresas_associadas_atual}\n")

# Perguntar confirmação
resposta = input("⚠️  ATENÇÃO: Isso associará TODAS as empresas ativas ao usuário.\n"
                "Como você já é superuser, isso NÃO é necessário.\n"
                "Deseja continuar mesmo assim? (digite 'SIM' para confirmar): ")

if resposta.strip().upper() != 'SIM':
    print("\n❌ Operação cancelada.")
    exit(0)

# Associar todas as empresas
print(f"\n🔄 Associando {total_ativas} empresas ativas...")
pessoa.empresas.set(empresas_ativas)
pessoa.save()

empresas_associadas_final = pessoa.empresas.count()
print(f"✅ Concluído! {empresas_associadas_final} empresas associadas.")
print(f"\nNOTA: Como você é superuser, continuará vendo todas as empresas "
      f"independentemente desta associação.")
