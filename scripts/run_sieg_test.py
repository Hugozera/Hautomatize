import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from core.sieg_service import SiegClient

if __name__ == '__main__':
    client = SiegClient()
    print('SIEG base_url=', client.base_url)
    print('Using API key present? ->', bool(client.api_key))
    openapi = client.get_openapi()
    if not openapi:
        print('OpenAPI fetch failed or returned no data')
    else:
        paths = openapi.get('paths', {})
        print('OpenAPI paths count =', len(paths))
        # Try find certificados
        method, path, meta = client.find_path_for_keyword('certificado')
        print('Found certificado path:', method, path)
        if path and method:
            status, hdrs, body = client.fetch_list(method, path, operation_meta=meta)
            print('fetch_list status=', status)
            if status == 200:
                if isinstance(body, list):
                    print('Items returned:', len(body))
                    for it in body[:3]:
                        print('-', json.dumps(it, ensure_ascii=False)[:200])
                else:
                    print('Body is dict/string:', type(body))
                    print(json.dumps(body, ensure_ascii=False)[:400])
