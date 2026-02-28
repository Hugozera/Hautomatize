import os
import sys
import django

# ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from core.models import ArquivoConversao
from core.views_conversor import processar_conversao
from django.conf import settings

PDF_PATH = r"c:\Hautomatize\media\conversor\originais\STONE_AGOSTO_TODO.pdf"

def ensure_superuser():
    User = get_user_model()
    try:
        su = User.objects.filter(is_superuser=True).first()
        if su:
            return su
        # create a temp superuser
        su = User.objects.create(username='simulator', is_superuser=True, is_staff=True)
        su.set_password('simulator')
        su.save()
        return su
    except Exception as e:
        print('Failed to get/create superuser:', e)
        raise

def main():
    if not os.path.exists(PDF_PATH):
        print('PDF not found:', PDF_PATH)
        return

    su = ensure_superuser()

    # Create ArquivoConversao record
    rel_name = os.path.relpath(PDF_PATH, settings.MEDIA_ROOT).replace('\\','/')
    conv = ArquivoConversao.objects.create(
        usuario=None,
        nome_original=os.path.basename(PDF_PATH),
        formato_origem='pdf',
        formato_destino='ofx',
        tamanho_original=os.path.getsize(PDF_PATH),
        status='pendente'
    )
    # assign file field path relative to MEDIA_ROOT
    conv.arquivo_original.name = rel_name
    conv.save()
    print('Created conversao id:', conv.id, 'file name:', conv.arquivo_original.name)

    # Build request
    rf = RequestFactory()
    req = rf.post(f'/conversor/processar/{conv.id}/')
    req.user = su

    # Call view
    resp = processar_conversao(req, conv.id)
    try:
        content = resp.content.decode('utf-8')
    except Exception:
        content = str(resp)
    print('Response status:', getattr(resp, 'status_code', 'n/a'))
    print('Response content:', content[:1000])

if __name__ == '__main__':
    main()
