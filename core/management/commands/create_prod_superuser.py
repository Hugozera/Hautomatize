from django.core.management.base import BaseCommand
import os
import json
import subprocess
import sys


class Command(BaseCommand):
    help = 'Cria ou atualiza um superuser no banco de produção e garante permissões (usa settings_prod).'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Nome do superuser a criar (ex: Sferna123)')
        parser.add_argument('--email', required=False, help='Email do superuser')
        parser.add_argument('--password', required=False, help='Senha em texto (se omitido, tenta copiar hash do sqlite)')

    def handle(self, *args, **options):
        username = options['username']
        email = options.get('email') or ''
        password = options.get('password')

        self.stdout.write(f'Preparando criação do superuser "{username}" em produção...')

        # Executa a criação no contexto do settings_prod via subprocess
        manage_py = os.path.join(os.getcwd(), 'manage.py')
        env = os.environ.copy()
        env['DJANGO_SETTINGS_MODULE'] = 'nfse_downloader.settings_prod'

        # Se senha em texto for fornecida, usa set_password; caso contrário, tentamos copiar o hash do sqlite
        if password:
            create_py = f"""
from django.contrib.auth import get_user_model
User = get_user_model()
username = {json.dumps(username)}
email = {json.dumps(email)}
pwd = {json.dumps(password)}
if not User.objects.filter(username=username).exists():
    u = User.objects.create_user(username=username, email=email, password=pwd, is_staff=True, is_superuser=True)
    print('CREATED')
else:
    u = User.objects.get(username=username)
    u.email = email
    u.is_staff = True
    u.is_superuser = True
    u.set_password(pwd)
    u.save()
    print('UPDATED')
"""
        else:
            # tenta copiar hash do sqlite dev
            create_py = f"""
from django.contrib.auth import get_user_model
User = get_user_model()
import sqlite3, os
dev_db = {json.dumps(os.path.join(os.getcwd(), 'db.sqlite3'))}
username = {json.dumps(username)}
email = {json.dumps(email)}
hash_pw = None
if os.path.exists(dev_db):
    try:
        conn = sqlite3.connect(dev_db)
        cur = conn.cursor()
        cur.execute('SELECT password FROM auth_user WHERE username=? LIMIT 1', (username,))
        r = cur.fetchone()
        conn.close()
        if r:
            hash_pw = r[0]
    except Exception:
        hash_pw = None

if not hash_pw:
    # fallback: create without password and print instruction
    if not User.objects.filter(username=username).exists():
        u = User(username=username, email=email, is_staff=True, is_superuser=True)
        u.set_unusable_password()
        u.save()
        print('CREATED_NO_PWD')
    else:
        u = User.objects.get(username=username)
        u.email = email
        u.is_staff = True
        u.is_superuser = True
        u.save()
        print('UPDATED_NO_PWD')
else:
    if not User.objects.filter(username=username).exists():
        u = User(username=username, email=email, is_staff=True, is_superuser=True)
        u.password = hash_pw
        u.save()
        print('CREATED_WITH_HASH')
    else:
        u = User.objects.get(username=username)
        u.email = email
        u.is_staff = True
        u.is_superuser = True
        u.password = hash_pw
        u.save()
        print('UPDATED_WITH_HASH')
"""

        try:
            subprocess.run([sys.executable, manage_py, 'shell', '-c', create_py, '--settings=nfse_downloader.settings_prod'], check=True, env=env)
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.ERROR(f'Erro ao criar superuser em produção: {e}'))
            self.stdout.write('Verifique se o Postgres/DB de produção está acessível e as variáveis em .env estão corretas.')
            return

        # Tenta atribuir permissões via comando já existente
        try:
            subprocess.run([sys.executable, manage_py, 'grant_all_permissions', username, '--settings=nfse_downloader.settings_prod'], check=True, env=env)
        except subprocess.CalledProcessError:
            self.stdout.write(self.style.WARNING('Não foi possível executar grant_all_permissions automaticamente. Execute manualmente se necessário.'))

        self.stdout.write(self.style.SUCCESS('Comando concluído. Superuser criado/atualizado (produção).'))
