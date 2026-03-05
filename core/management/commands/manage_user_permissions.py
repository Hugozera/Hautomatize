"""
Management command para gerenciar permissões de usuários específicos.

Permite adicionar/remover permissões diretas de um usuário.
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import Pessoa
from core.permission_system import get_all_permissions


class Command(BaseCommand):
    help = 'Gerencia permissões diretas de um usuário específico'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username do usuário')

        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--add-perm',
            type=str,
            help='Adiciona uma permissão direta (ex: empresa.edit)',
        )
        group.add_argument(
            '--remove-perm',
            type=str,
            help='Remove uma permissão direta',
        )
        group.add_argument(
            '--list-perms',
            action='store_true',
            help='Lista todas as permissões do usuário',
        )
        group.add_argument(
            '--reset',
            action='store_true',
            help='Remove todas as permissões diretas do usuário',
        )

    def handle(self, *args, **options):
        username = options['username']

        # ===== ENCONTRAR USUÁRIO =====
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            raise CommandError(f'Usuário "{username}" não encontrado')

        # Garante que existe Pessoa
        pessoa, created = Pessoa.objects.get_or_create(
            user=user,
            defaults={'cpf': '00000000000', 'ativo': True}
        )

        self.stdout.write(
            self.style.SUCCESS(f'\n👤 Usuário: {user.get_full_name() or username}')
        )
        self.stdout.write(f'   Email: {user.email}\n')

        # ===== ADD PERM =====
        if options['add_perm']:
            perm_code = options['add_perm'].lower()
            all_perms = get_all_permissions()

            if perm_code not in all_perms:
                raise CommandError(
                    f'Permissão "{perm_code}" inválida. '
                    f'Use setup_permissions --verbose-perms para listar todas'
                )

            perms = pessoa.perm_list()
            if perm_code not in perms:
                perms.append(perm_code)
                pessoa.permissions = ','.join(sorted(perms))
                pessoa.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Permissão "{perm_code}" adicionada a {username}')
                )
            else:
                self.stdout.write(f'⚠️  {username} já possui a permissão "{perm_code}"')

        # ===== REMOVE PERM =====
        elif options['remove_perm']:
            perm_code = options['remove_perm'].lower()
            perms = pessoa.perm_list()

            if perm_code in perms:
                perms.remove(perm_code)
                pessoa.permissions = ','.join(sorted(perms)) if perms else ''
                pessoa.save()
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Permissão "{perm_code}" removida de {username}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️  {username} não possui a permissão "{perm_code}"')
                )

        # ===== LIST PERMS =====
        elif options['list_perms']:
            all_perms = pessoa.perm_list()

            self.stdout.write(self.style.SUCCESS('\n📝 PERMISSÕES DIRETAS:'))
            direct_perms = pessoa.permissions.split(',') if pessoa.permissions else []
            direct_perms = [p.strip() for p in direct_perms if p.strip()]

            if direct_perms:
                for perm in sorted(direct_perms):
                    self.stdout.write(f'  • {perm}')
            else:
                self.stdout.write('  (nenhuma permissão direta)')

            self.stdout.write(self.style.SUCCESS(f'\n📊 TOTAL: {len(all_perms)} permissões'))
            
            # Agrupa por módulo
            from collections import defaultdict
            by_module = defaultdict(list)
            for perm in sorted(all_perms):
                module = perm.split('.')[0]
                by_module[module].append(perm)

            self.stdout.write(self.style.SUCCESS('\n📦 POR MÓDULO:'))
            for module in sorted(by_module.keys()):
                count = len(by_module[module])
                self.stdout.write(f'  • {module}: {count} permissões')

        # ===== RESET =====
        elif options['reset']:
            self.stdout.write(
                self.style.WARNING(f'⚠️  Removendo TODAS as permissões de {username}...')
            )
            pessoa.permissions = ''
            pessoa.save()
            self.stdout.write(self.style.SUCCESS('✅ Usuário resetado para sem permissões'))

        self.stdout.write('')
