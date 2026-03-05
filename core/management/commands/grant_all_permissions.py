from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Concede todas as permissões diretas ao usuário (username opcional).'

    def add_arguments(self, parser):
        parser.add_argument(
            'username',
            nargs='?',
            help='Nome de usuário para receber as permissões. Se omitido, usa o primeiro usuário.',
        )

    def handle(self, *args, **options):
        from django.contrib.auth.models import User
        from core.models import Pessoa
        from core.permission_system import get_all_permissions

        username = options.get('username')
        if username:
            user = User.objects.filter(username=username).first()
            if not user:
                self.stdout.write(self.style.ERROR(f'Usuário "{username}" não encontrado.'))
                return
        else:
            user = User.objects.first()
            if not user:
                self.stdout.write(self.style.ERROR('Nenhum usuário encontrado no sistema.'))
                return

        pessoa = getattr(user, 'pessoa', None)
        if not pessoa:
            cpf_seed = (user.username or '000').ljust(11, '0')[:11]
            pessoa = Pessoa.objects.create(user=user, cpf=cpf_seed)
            self.stdout.write(
                self.style.WARNING(f'Pessoa criada para usuário {user.username} (cpf={cpf_seed}).')
            )

        perms = get_all_permissions()
        pessoa.permissions = ','.join(perms)
        pessoa.ativo = True
        pessoa.save(update_fields=['permissions', 'ativo'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Permissões diretas ({len(perms)}) atribuídas a {user.username} ({pessoa.pk}).'
            )
        )