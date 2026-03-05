#!/usr/bin/env python
"""Script para testar se o usuário vê todas as empresas"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import Empresa

# Buscar usuário
user = User.objects.filter(username__icontains='hugo').first()
if not user:
    print("Usuário não encontrado!")
    exit(1)

print(f"Usuário: {user.username}")
print(f"Is superuser: {user.is_superuser}")
print(f"Is staff: {user.is_staff}\n")

# Simular lógica da view empresa_list (deve mostrar todas)
empresas = Empresa.objects.all()
print(f"empresa_list view: {empresas.count()} empresas (deve ser todas)")

# Simular lógica da view dashboard
if user.is_superuser:
    empresas_dash = Empresa.objects.filter(ativo=True)
    print(f"dashboard view (superuser): {empresas_dash.count()} empresas ativas")
elif hasattr(user, 'pessoa') and user.pessoa.empresas.exists():
    empresas_dash = user.pessoa.empresas.filter(ativo=True)
    print(f"dashboard view (pessoa com empresas): {empresas_dash.count()} empresas")
else:
    empresas_dash = Empresa.objects.filter(ativo=True)
    print(f"dashboard view (else): {empresas_dash.count()} empresas ativas")

# Simular lógica da view agendamento_list
if user.is_superuser:
    from core.models import Agendamento
    agendamentos = Agendamento.objects.select_related('empresa').all()
    print(f"agendamento_list view (superuser): {agendamentos.count()} agendamentos")

# Total
print(f"\nTotal de empresas no sistema: {Empresa.objects.count()}")
print(f"Total de empresas ativas: {Empresa.objects.filter(ativo=True).count()}")
