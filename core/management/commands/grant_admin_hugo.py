"""
Management command para atribuir todas as permissões administrativas ao usuário Hugo.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Pessoa
from core.permission_system import PERMISSION_MAP


class Command(BaseCommand):
    help = 'Atribui todas as permissões administrativas ao usuário Hugo'

    def handle(self, *args, **options):
        # Procura pelo usuário Hugo (pode ser por email ou username)
        user = User.objects.filter(
            username__icontains='hugo'
        ).first() or User.objects.filter(
            first_name__icontains='hugo'
        ).first()
        
        if not user:
            self.stdout.write(self.style.ERROR('❌ Usuário Hugo não encontrado!'))
            return
        
        # Garante que existe um objeto Pessoa
        pessoa, created = Pessoa.objects.get_or_create(
            user=user,
            defaults={'cpf': '00000000000'}  # CPF provisório
        )
        
        if created:
            self.stdout.write(self.style.WARNING(f'⚠️  Objeto Pessoa criado para {user.username}'))
        
        # Coleta TODAS as permissões disponíveis
        all_permissions = []
        for module, actions in PERMISSION_MAP.items():
            for action in actions.keys():
                all_permissions.append(f'{module}.{action}')
        
        # Atribui as permissões diretas
        pessoa.permissions = ','.join(all_permissions)
        pessoa.save()
        
        
        # Exibe resultado
        self.stdout.write(self.style.SUCCESS('\n✅ SUCESSO! Todas as permissões diretas foram atribuídas ao Hugo'))
        self.stdout.write(f'   Nome: {user.get_full_name() or user.username}')
        self.stdout.write(f'   Email: {user.email}')
        self.stdout.write(f'   Total de permissões: {len(all_permissions)}')
        self.stdout.write(f'   Módulos: {len(PERMISSION_MAP)}')
        
        # Exibe detalhes das permissões
        self.stdout.write('\n📋 Permissões por módulo:')
        for module, actions in sorted(PERMISSION_MAP.items()):
            self.stdout.write(f'   • {module}: {len(actions)} ações')
