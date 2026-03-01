import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()
from django.test import Client
from django.contrib.auth import get_user_model
U = get_user_model()
user = U.objects.filter(is_superuser=True).first()
print('using user:', user)
client = Client()
if user:
    client.force_login(user)
paths = ['/painel/secretaria/', '/painel/cliente_identificacao/']
for path in paths:
    r = client.get(path)
    fname = path.strip('/').replace('/','_') or 'index'
    out = f"rendered_{fname}.html"
    with open(out, 'w', encoding='utf-8') as f:
        f.write(r.content.decode('utf-8'))
    print(path, '->', out, 'status', r.status_code)
