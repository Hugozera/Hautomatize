from django.core.management.base import BaseCommand
import os
import sqlite3
import json
import subprocess
import sys


class Command(BaseCommand):
    help = 'Prepara o ambiente de produção: migra DB (Postgres), copia superuser do sqlite e atribui permissões.'

    def handle(self, *args, **options):
        from django.conf import settings

        self.stdout.write('Iniciando preparação do ambiente de produção...')

        # Local do manage.py
        manage_py = os.path.join(settings.BASE_DIR, 'manage.py')

        # Local do arquivo sqlite atual (dev)
        sqlite_db = settings.DATABASES['default'].get('NAME')
        if not sqlite_db or not os.path.exists(sqlite_db):
            self.stdout.write(self.style.ERROR(f'Arquivo sqlite não encontrado: {sqlite_db}'))
            return

        # Busca um superuser existente no sqlite
        try:
            conn = sqlite3.connect(sqlite_db)
            cur = conn.cursor()
            cur.execute("SELECT username, email, password, is_staff, is_superuser FROM auth_user WHERE is_superuser=1 ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao ler sqlite: {e}'))
            return

        if not row:
            self.stdout.write(self.style.ERROR('Nenhum superuser encontrado no banco de desenvolvimento (sqlite). Crie um antes ou forneça credenciais manualmente.'))
            return

        username, email, password_hash, is_staff, is_superuser = row

        self.stdout.write(f'Encontrei superuser local: {username} <{email}>')

        # Preparar ambiente para executar comandos com settings de produção
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'nfse_downloader.settings_prod'

        # 1) Rodar migrations na DB de produção
        self.stdout.write('Executando migrations na DB de produção...')
        try:
            subprocess.run([sys.executable, manage_py, 'migrate', '--noinput', '--settings=nfse_downloader.settings_prod'], check=True, env=env)
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f'Erro ao rodar migrate: {e}'))
            return

        # 2) Criar/atualizar superuser no banco de produção preservando hash de senha
        self.stdout.write('Criando/atualizando superuser na DB de produção...')

        create_user_py = f"""
from django.contrib.auth import get_user_model
User = get_user_model()
username = {json.dumps(username)}
email = {json.dumps(email)}
password_hash = {json.dumps(password_hash)}
if not User.objects.filter(username=username).exists():
    user = User(username=username, email=email, is_staff=True, is_superuser=True)
    user.password = password_hash
    user.save()
    print('CREATED')
else:
    user = User.objects.get(username=username)
    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.password = password_hash
    user.save()
    print('UPDATED')
"""

        try:
            subprocess.run([sys.executable, manage_py, 'shell', '-c', create_user_py, '--settings=nfse_downloader.settings_prod'], check=True, env=env)
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f'Erro ao criar/atualizar usuário: {e}'))
            return

        # 3) Atribuir permissões via comando existente `grant_all_permissions`
        self.stdout.write('Atribuindo permissões (grant_all_permissions)...')
        try:
            subprocess.run([sys.executable, manage_py, 'grant_all_permissions', username, '--settings=nfse_downloader.settings_prod'], check=True, env=env)
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f'Erro ao rodar grant_all_permissions: {e}'))
            # não retorna; permissões podem ser aplicadas manualmente

        self.stdout.write(self.style.SUCCESS('Bootstrap de produção concluído com sucesso.'))
