"""
Management command para gerenciar permissões de usuários específicos.

Permite adicionar/remover roles e permissões de um usuário.
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import Pessoa, Role
from core.permission_system import get_all_permissions, get_permissions_for_role


class Command(BaseCommand):
    help = 'Gerencia permissões e papéis de um usuário específico'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username do usuário')
        
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument(
            '--add-role',
            type=str,
            help='Adiciona um papel ao usuário (ex: admin, gestor, analista, operador, visualizador)',
        )
        group.add_argument(
            '--remove-role',
            type=str,
            help='Remove um papel do usuário',
        )
        group.add_argument(
            '--set-roles',
            type=str,
            help='Define papéis (substitui todos) - separados por vírgula (ex: gestor,analista)',
        )
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
            help='Remove todos os papéis e permissões do usuário',
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

        # ===== ADD ROLE =====
        if options['add_role']:
            role_codename = options['add_role'].lower()
            try:
                role = Role.objects.get(codename=role_codename)
            except Role.DoesNotExist:
                raise CommandError(
                    f'Papel "{role_codename}" não encontrado. '
                    f'Use: admin, gestor, analista, operador, visualizador'
                )

            pessoa.roles.add(role)
            self.stdout.write(
                self.style.SUCCESS(f'✅ Papel "{role.name}" adicionado a {username}')
            )

        # ===== REMOVE ROLE =====
        elif options['remove_role']:
            role_codename = options['remove_role'].lower()
            try:
                role = Role.objects.get(codename=role_codename)
            except Role.DoesNotExist:
                raise CommandError(f'Papel "{role_codename}" não encontrado')

            pessoa.roles.remove(role)
            self.stdout.write(
                self.style.SUCCESS(f'✅ Papel "{role.name}" removido de {username}')
            )

        # ===== SET ROLES =====
        elif options['set_roles']:
            role_codenames = [r.strip() for r in options['set_roles'].split(',')]
            roles = []

            for role_codename in role_codenames:
                try:
                    role = Role.objects.get(codename=role_codename)
                    roles.append(role)
                except Role.DoesNotExist:
                    raise CommandError(f'Papel "{role_codename}" não encontrado')

            pessoa.roles.set(roles)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Papéis definidos para {username}: {', '.join(r.name for r in roles)}"
                )
            )

        # ===== ADD PERM =====
        elif options['add_perm']:
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
            roles = pessoa.roles.filter(ativo=True)

            self.stdout.write(self.style.SUCCESS('\n📋 PAPÉIS (ROLES):'))
            if roles:
                for role in roles:
                    self.stdout.write(f'  • {role.name} ({role.codename})')
            else:
                self.stdout.write('  (nenhum papel atribuído)')

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
            pessoa.roles.clear()
            pessoa.permissions = ''
            pessoa.save()
            self.stdout.write(self.style.SUCCESS('✅ Usuário resetado para sem permissões'))

        self.stdout.write('')
