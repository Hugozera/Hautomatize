"""
Management command para diagnosticar e visualizar o estado de permissões do sistema.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Pessoa
from core.permission_system import (
    PERMISSION_MAP,
    get_all_permissions,
)


class Command(BaseCommand):
    help = 'Visualiza diagnóstico completo do sistema de permissões'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Username específico para diagnosticar',
        )
        parser.add_argument(
            '--module',
            type=str,
            help='Módulo específico para listar permissões',
        )
        parser.add_argument(
            '--summary',
            action='store_true',
            help='Mostra apenas um resumo (padrão)',
        )

    def handle(self, *args, **options):
        # ===== DIAGNÓSTICO ESPECÍFICO DE USUÁRIO =====
        if options['user']:
            self._show_user_diagnosis(options['user'])
            return

        # ===== DIAGNÓSTICO ESPECÍFICO DE MÓDULO =====
        if options['module']:
            self._show_module_diagnosis(options['module'])
            return

        # ===== RESUMO GERAL =====
        self._show_summary()

    def _show_summary(self):
        """Mostra resumo geral do sistema."""
        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('DIAGNÓSTICO DE PERMISSÕES - RESUMO GERAL'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        # Estatísticas gerais
        all_perms = get_all_permissions()
        total_users = User.objects.count()
        total_pessoas = Pessoa.objects.count()
        self.stdout.write(self.style.SUCCESS('📊 ESTATÍSTICAS:'))
        self.stdout.write(f'  • Usuários Django: {total_users}')
        self.stdout.write(f'  • Objetos Pessoa: {total_pessoas}')
        self.stdout.write(f'  • Permissões totais: {len(all_perms)}')
        self.stdout.write(f'  • Módulos: {len(PERMISSION_MAP)}')

        # Hugo com permissões diretas
        self.stdout.write(self.style.SUCCESS('\n🔐 USUÁRIO PRINCIPAL (HUGO):'))
        try:
            hugo = User.objects.get(pk=1)
            hugo_pessoa = getattr(hugo, 'pessoa', None)
            if hugo_pessoa:
                direct_perms = hugo_pessoa.perm_list()
                self.stdout.write(f'  • Nome: {hugo.get_full_name() or hugo.username}')
                self.stdout.write(f'  • Email: {hugo.email}')
                self.stdout.write(f'  • Permissões totais: {len(direct_perms)}')
            else:
                self.stdout.write('  ⚠️  Hugo não tem objeto Pessoa!')
        except User.DoesNotExist:
            self.stdout.write('  ⚠️  Usuário Hugo (id=1) não encontrado!')

        # Módulos
        self.stdout.write(self.style.SUCCESS('\n📦 MÓDULOS E PERMISSÕES:'))
        for module in sorted(PERMISSION_MAP.keys()):
            perms_count = len(PERMISSION_MAP[module])
            self.stdout.write(f'  • {module}: {perms_count} permissões')

        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(self.style.WARNING('💡 DICAS:'))
        self.stdout.write('  • Use "--user <username>" para diagnosticar um usuário específico')
        self.stdout.write('  • Use "--module <name>" para listar permissões de um módulo')
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

    def _show_user_diagnosis(self, username):
        """Mostra diagnóstico detalhado de um usuário."""
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Usuário "{username}" não encontrado'))
            return

        pessoa = getattr(user, 'pessoa', None)
        if not pessoa:
            self.stdout.write(self.style.ERROR(f'❌ Usuário "{username}" sem objeto Pessoa'))
            return

        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(
            self.style.SUCCESS(f'DIAGNÓSTICO DE USUÁRIO: {user.get_full_name() or username}')
        )
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        # Informações básicas
        self.stdout.write(self.style.SUCCESS('📋 INFORMAÇÕES:'))
        self.stdout.write(f'  • Username: {user.username}')
        self.stdout.write(f'  • Email: {user.email}')
        self.stdout.write(f'  • Ativo: {"Sim" if user.is_active else "Não"}')
        self.stdout.write(f'  • Superuser: {"Sim" if user.is_superuser else "Não"}')
        self.stdout.write(f'  • Pessoa ID: {pessoa.pk}')
        self.stdout.write(f'  • Pessoa Ativa: {"Sim" if pessoa.ativo else "Não"}')

        # Permissões diretas
        direct_perms = pessoa.perm_list()
        self.stdout.write(self.style.SUCCESS(f'\n🔐 PERMISSÕES DIRETAS ({len(direct_perms)}):'))
        for perm in sorted(direct_perms):
            self.stdout.write(f'  • {perm}')

        # Agrupa por módulo
        from collections import defaultdict
        by_module = defaultdict(list)
        for perm in direct_perms:
            module = perm.split('.')[0]
            by_module[module].append(perm)

        self.stdout.write(self.style.SUCCESS('\n📊 POR MÓDULO:'))
        for module in sorted(by_module.keys()):
            perms = by_module[module]
            self.stdout.write(f'  • {module}: {len(perms)} permissões')

        self.stdout.write('\n' + self.style.SUCCESS('='*80 + '\n'))

    def _show_module_diagnosis(self, module):
        """Mostra diagnóstico de um módulo específico."""
        module = module.lower()

        if module not in PERMISSION_MAP:
            self.stdout.write(self.style.ERROR(f'❌ Módulo "{module}" não encontrado'))
            self.stdout.write('Módulos disponíveis:')
            for m in sorted(PERMISSION_MAP.keys()):
                self.stdout.write(f'  • {m}')
            return

        module_perms = PERMISSION_MAP[module]

        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS(f'DIAGNÓSTICO DE MÓDULO: {module}'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        self.stdout.write(self.style.SUCCESS(f'📝 PERMISSÕES ({len(module_perms)}):'))
        for perm_name, description in sorted(module_perms.items()):
            self.stdout.write(f'  • {module}.{perm_name}')
            self.stdout.write(f'     → {description}')

        self.stdout.write('\n' + self.style.SUCCESS('='*80 + '\n'))
