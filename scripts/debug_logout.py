import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
import django
django.setup()
from django.test import Client
from django.contrib.auth.models import User

u = User.objects.create_user('tmpu_dbg', 'dbg@example.com', 'pw')
client = Client()
client.login(username='tmpu_dbg', password='pw')
resp = client.get('/accounts/logout/')
print('GET /accounts/logout/ ->', resp.status_code)
print(resp.content.decode()[:800])
resp2 = client.post('/accounts/logout/')
print('POST /accounts/logout/ ->', resp2.status_code)
print(resp2.content.decode()[:800])
