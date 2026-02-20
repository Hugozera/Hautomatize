from django.core.management.base import BaseCommand
import os
import subprocess
import sys


class Command(BaseCommand):
    help = 'Inicia o servidor de desenvolvimento usando as configurações de produção (usa Postgres).'

    def add_arguments(self, parser):
        parser.add_argument('--addr', default='0.0.0.0:8000', help='Endereço para bind (default 0.0.0.0:8000)')

    def handle(self, *args, **options):
        from django.conf import settings

        addr = options.get('addr')
        manage_py = os.path.join(settings.BASE_DIR, 'manage.py')

        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'nfse_downloader.settings_prod'

        self.stdout.write(f'Iniciando servidor de desenvolvimento (produção) em {addr}...')
        # Executa manage.py runserver em subprocess com settings de produção
        try:
            subprocess.run([sys.executable, manage_py, 'runserver', addr, '--settings=nfse_downloader.settings_prod'], env=env)
        except KeyboardInterrupt:
            self.stdout.write('Servidor interrompido pelo usuário')
