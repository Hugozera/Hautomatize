"""
Management command para inicializar o sistema de permissões.

Atribui permissões diretas ao usuário Hugo (id=1) e prepara diagnóstico básico.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Pessoa
from core.permission_system import get_all_permissions


class Command(BaseCommand):
    help = 'Inicializa o sistema de permissões diretas e atribui acesso ao usuário Hugo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Remove todas as permissões diretas de usuários antes de reconfigurar (careful!)',
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
            self.stdout.write(self.style.WARNING('⚠️  Limpando permissões diretas de usuários...'))
            for pessoa in Pessoa.objects.all():
                pessoa.permissions = ''
                pessoa.save(update_fields=['permissions'])
            self.stdout.write(self.style.WARNING('   Permissões diretas limpas.\n'))

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
            pessoa.permissions = ','.join(all_perms)
            pessoa.save(update_fields=['permissions'])

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n   ✅ TOTAL: Hugo possui {len(all_perms)} permissões diretas'
                )
            )

        # ===== DOCUMENTAÇÃO =====
        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('RESUMO DO SISTEMA DE PERMISSÕES'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        all_perms = get_all_permissions()
        self.stdout.write(f'Total de Permissões: {len(all_perms)}')

        if options['verbose_perms']:
            self.stdout.write('\n📝 PERMISSÕES CRIADAS:')
            for i, perm in enumerate(all_perms, 1):
                self.stdout.write(f"  {i:3}. {perm}")

        self.stdout.write('\n' + self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('✅ SISTEMA DE PERMISSÕES INICIALIZADO COM SUCESSO!'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        self.stdout.write(self.style.WARNING('📌 PRÓXIMOS PASSOS:'))
        self.stdout.write('  1. Adicione outros usuários ao sistema')
        self.stdout.write('  2. Atribua permissões diretas conforme necessidade')
        self.stdout.write('  3. Revise o menu dinâmico para refletir os acessos')
        self.stdout.write('  4. Editar core/permission_system.py para ajustar permissões\n')
