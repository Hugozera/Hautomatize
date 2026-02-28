import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from core.sieg_service import SiegClient

c = SiegClient()
print('Base URL:', c.base_url)
print('Has API key configured?', bool(c.api_key))
openapi = c.get_openapi()
if not openapi:
    print('No OpenAPI available')
else:
    # OpenAPI v2 may use 'securityDefinitions'; v3 uses components.securitySchemes
    sd = openapi.get('securityDefinitions') or (openapi.get('components') or {}).get('securitySchemes')
    print('securityDefinitions / components.securitySchemes:')
    print(json.dumps(sd, indent=2, ensure_ascii=False) if sd else 'None')
    print('\nGlobal security:', json.dumps(openapi.get('security'), indent=2, ensure_ascii=False))
    # Show for a couple of paths the 'security' field and operationId/summary
    paths = openapi.get('paths', {})
    for i,(p,(m,meta)) in enumerate(((p, next(iter(methods.items()))) for p,methods in paths.items())):
        print('\nPath sample:', p)
        print(' Method sample:', m)
        print(' Meta keys:', list(meta.keys()) if isinstance(meta, dict) else meta)
        if isinstance(meta, dict):
            print(' security:', meta.get('security'))
            print(' summary:', meta.get('summary'))
        if i>=4:
            break
