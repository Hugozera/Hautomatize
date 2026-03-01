"""
ASGI config for nfse_downloader project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')

# Import the ProtocolTypeRouter application assembled in painel.routing
try:
	from painel.routing import application
except Exception:
	# Fallback to default ASGI app if painel routing isn't available
	application = get_asgi_application()
