from django.core.management.base import BaseCommand
from django.test import Client
from django.contrib.auth import get_user_model
from django.conf import settings

URLS_TO_CHECK = [
    '/',
    '/pessoas/',
    '/pessoas/nova/',
    '/empresas/',
    '/empresas/nova/',
    '/agendamentos/',
    '/agendamentos/novo/',
    '/download/',
    '/configuracao/',
    '/perfil/',
    '/perfil/generate-token/',
    '/certificados/',
    '/certificados/testar/',
    '/progresso/1/',
    '/historico/',
    '/download/lista/',
    '/conversor/',
    '/conversor/historico/',
    '/conversor/formatos/?ext=pdf',
    '/login/',
]

class Command(BaseCommand):
    help = 'Percorre páginas principais do sistema como usuário autenticado e reporta erros (uso local)'

    def handle(self, *args, **options):
        User = get_user_model()
        username = 'autotest'
        password = 'autotest123'

        # Criar usuário de teste (superuser) se não existir
        user, created = User.objects.get_or_create(username=username)
        if created:
            user.set_password(password)
            user.is_superuser = True
            user.is_staff = True
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Criado usuário de teste: {username}'))
        else:
            user.set_password(password)
            user.save()

        # Garantir hosts permitidos para o teste (evita DisallowedHost no test client)
        if not getattr(settings, 'ALLOWED_HOSTS', None):
            settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

        client = Client()
        logged = client.login(username=username, password=password)
        if not logged:
            self.stdout.write(self.style.ERROR('Falha ao logar com o usuário de teste'))
            return

        self.stdout.write(self.style.NOTICE('Usuário autenticado — iniciando verificação de páginas...'))
        failures = []

        for url in URLS_TO_CHECK:
            try:
                resp = client.get(url)
                status = resp.status_code
                if status >= 500:
                    failures.append((url, status, resp.content.decode('utf-8', errors='ignore')[:8000]))
                    self.stdout.write(self.style.ERROR(f'[ERR] {url} -> {status}'))
                elif status >= 400:
                    failures.append((url, status, resp.content.decode('utf-8', errors='ignore')[:2000]))
                    self.stdout.write(self.style.WARNING(f'[WARN] {url} -> {status}'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'[OK]  {url} -> {status}'))
            except Exception as e:
                failures.append((url, 'exception', str(e)))
                self.stdout.write(self.style.ERROR(f'[EXC] {url} -> {e}'))

        self.stdout.write('\n' + '='*60)
        if failures:
            self.stdout.write(self.style.ERROR(f'Foram encontrados {len(failures)} problema(s)'))
            for u, s, detail in failures:
                self.stdout.write(self.style.ERROR(f'--- {u} -> {s}'))
                self.stdout.write(detail[:2000])
                self.stdout.write('')
        else:
            self.stdout.write(self.style.SUCCESS('Todas as páginas verificadas retornaram 2xx/3xx/4xx sem erro 5xx.'))

        # Não removemos o usuário de teste — útil para rechecks locais
