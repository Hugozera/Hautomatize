"""
Management command para inicializar o sistema de permissões.

Cria todos os roles e atribui permissões corretamente ao usuário Hugo (id=1).
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from core.models import Pessoa, Role
from core.permission_system import (
    ROLE_DEFINITIONS,
    get_permissions_for_role,
    get_all_permissions,
)


class Command(BaseCommand):
    help = 'Inicializa o sistema de permissões: cria todos os papéis e atribui permissões'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Remove todos os roles existentes antes de criar novos (careful!)',
        )
        parser.add_argument(
            '--assign-hugo-admin',
            action='store_true',
            default=True,
            help='Atribui acesso total ao usuário Hugo (id=1) [padrão: True]',
        )
        parser.add_argument(
            '--verbose-perms',
            action='store_true',
            help='Mostra todas as permissões criadas',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('INICIALIZANDO SISTEMA DE PERMISSÕES'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        # ===== RESET (se solicitado) =====
        if options['reset']:
            self.stdout.write(self.style.WARNING('⚠️  Deletando todos os roles existentes...'))
            deleted_count, _ = Role.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'   Deletado {deleted_count} roles.\n'))

        # ===== CRIAR ROLES =====
        self.stdout.write(self.style.SUCCESS('📋 Criando papéis (roles)...\n'))

        created_roles = {}
        for role_codename, role_def in ROLE_DEFINITIONS.items():
            perms = get_permissions_for_role(role_codename)
            perm_string = ','.join(perms)

            role, created = Role.objects.update_or_create(
                codename=role_codename,
                defaults={
                    'name': role_def['name'],
                    'descricao': role_def['descricao'],
                    'permissions': perm_string,
                    'ativo': True,
                }
            )

            action = '✅ CRIADO' if created else '♻️  ATUALIZADO'
            self.stdout.write(
                f'{action}: Role "{role.name}" ({role_codename})'
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'           → {len(perms)} permissões'
                )
            )

            created_roles[role_codename] = role

        # ===== ATRIBUIR HUGO COMO ADMIN =====
        if options['assign_hugo_admin']:
            self.stdout.write('\n' + self.style.SUCCESS('👤 Atribuindo permissões a Hugo (id=1)...\n'))

            try:
                hugo = User.objects.get(pk=1)
                self.stdout.write(f'   Usuario encontrado: {hugo.username} ({hugo.get_full_name()})')
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        '❌ Usuário com id=1 não encontrado. Criando com username "hughgo"...'
                    )
                )
                hugo = User.objects.create_user(
                    username='hugomartinscavalcante',
                    email='hugo@hautomatize.com.br',
                    first_name='Hugo',
                    last_name='Martins Cavalcante',
                    password='changeme123'
                )
                # Força id=1 se não fosse o primeiro
                if hugo.pk != 1:
                    self.stdout.write(
                        self.style.WARNING(
                            f'   ⚠️  Usuário criado mas com id={hugo.pk} (não 1).'
                        )
                    )

            # Cria ou atualiza Pessoa para Hugo
            pessoa, p_created = Pessoa.objects.get_or_create(
                user=hugo,
                defaults={
                    'cpf': '00000000000',
                    'ativo': True,
                }
            )

            if p_created:
                self.stdout.write(self.style.SUCCESS('   ✅ Objeto Pessoa criado para Hugo'))
            else:
                self.stdout.write(self.style.SUCCESS('   ♻️  Objeto Pessoa já existia para Hugo'))

            # Atribui TODAS as permissões diretas à pessoa
            all_perms = get_all_permissions()
            perm_string = ','.join(all_perms)
            pessoa.permissions = perm_string
            pessoa.save()

            # Limpa roles anteriores e atribui apenas Admin
            pessoa.roles.clear()
            admin_role = created_roles.get('admin')
            if admin_role:
                pessoa.roles.add(admin_role)
                self.stdout.write(self.style.SUCCESS(f'   ✅ Role "Admin" atribuído a Hugo'))

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n   ✅ TOTAL: Hugo possui {len(all_perms)} PERMISSÕES DIRETAS + Role Admin'
                )
            )

        # ===== DOCUMENTAÇÃO =====
        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('RESUMO DO SISTEMA DE PERMISSÕES'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        all_perms = get_all_permissions()
        self.stdout.write(f'Total de Permissões: {len(all_perms)}')
        self.stdout.write(f'Total de Papéis: {len(ROLE_DEFINITIONS)}')

        self.stdout.write('\n📋 PAPÉIS CRIADOS:')
        for role_codename, role in created_roles.items():
            role_def = ROLE_DEFINITIONS[role_codename]
            print(f"  • {role.name} ({role_codename})")
            print(f"    - {role_def['descricao']}")
            print(f"    - Permissões: {role.permissions.count(',') + 1}")

        if options['verbose_perms']:
            self.stdout.write('\n📝 PERMISSÕES CRIADAS:')
            for i, perm in enumerate(all_perms, 1):
                self.stdout.write(f"  {i:3}. {perm}")

        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('✅ SISTEMA DE PERMISSÕES INICIALIZADO COM SUCESSO!'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        self.stdout.write(self.style.WARNING('📌 PRÓXIMOS PASSOS:'))
        self.stdout.write('  1. Adicione outros usuários ao sistema')
        self.stdout.write('  2. Atribua papéis apropriados a cada usuário')
        self.stdout.write('  3. Customize permissões específicas se necessário')
        self.stdout.write('  4. Editar core/permission_system.py para ajustar permissões\n')
