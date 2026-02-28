from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
c = Client()
u = User.objects.filter(email='hugomartinscavalcante@gmail.com').first()
if u:
    c.force_login(u)
    r = c.get('/pessoas/nova/')
    html = r.content.decode('utf-8')
    idx = html.find('modalCadastroUsuario')
    snippet = html[max(0, idx-300):idx+600]
    print(snippet)
    print('--- classes in div ---')
    import re
    for m in re.finditer(r'<div[^>]+class="([^"]+)"', snippet):
        print(m.group(1))
    print('backdrop count', html.count('modal-backdrop'))
else:
    print('no user found')
