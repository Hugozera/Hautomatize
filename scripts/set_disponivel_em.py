import os
import sys
import django

# ensure project root is on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()
from django.utils import timezone
from core.models import Analista

qs = Analista.objects.filter(disponivel=True, disponivel_em__isnull=True)
count = qs.update(disponivel_em=timezone.now())
print('Updated disponivel_em for', count, 'analistas')
