from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Cria um Role "Full Access" e atribui ao usuário (username opcional).'

    def add_arguments(self, parser):
        parser.add_argument('username', nargs='?', help='Nome de usuário para receber o role. Se omitido, usa o primeiro usuário.')

    def handle(self, *args, **options):
        from django.contrib.auth.models import User
        from core.models import Role, Pessoa

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

        # Garante que exista um objeto Pessoa
        pessoa = getattr(user, 'pessoa', None)
        if not pessoa:
            # Cria Pessoa mínima se necessário
            cpf_seed = (user.username or '000').ljust(11, '0')[:11]
            pessoa = Pessoa.objects.create(user=user, cpf=cpf_seed)
            self.stdout.write(self.style.WARNING(f'Pessoa criada para usuário {user.username} (cpf={cpf_seed}).'))

        # Permissões que queremos garantir
        perms = [
            'empresa.edit', 'empresa.view', 'certificado.manage', 'conversor.use',
            'pessoa.edit', 'agendamento.manage', 'download.manage', 'historico.view',
            'role.manage'
        ]
        perm_txt = ','.join(perms)

        role, created = Role.objects.get_or_create(
            codename='admin.full',
            defaults={
                'name': 'Full Access',
                'descricao': 'Acesso total (gerado automaticamente).',
                'permissions': perm_txt,
                'ativo': True,
            }
        )
        if not created:
            role.permissions = perm_txt
            role.ativo = True
            role.save()

        # Atribui pessoa ao role
        role.pessoas.add(pessoa)
        role.save()

        self.stdout.write(self.style.SUCCESS(f'Role "{role.name}" atribuído a {user.username} ({pessoa.pk}).'))
        self.stdout.write(self.style.SUCCESS(f'Permissões garantidas: {perm_txt}'))