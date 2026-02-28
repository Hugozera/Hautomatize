import os
import django
import json
from pprint import pprint

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
django.setup()

from core.sieg_service import SiegClient

CLIENT_TIMEOUT = 10

def safe_preview(x, length=240):
    try:
        if isinstance(x, (dict, list)):
            s = json.dumps(x, ensure_ascii=False)
        else:
            s = str(x)
    except Exception:
        s = repr(x)
    return s[:length]


def main():
    client_auth = SiegClient()
    client_anon = SiegClient(api_key=None)

    print('SIEG base_url=', client_auth.base_url)
    print('Using API key present? ->', bool(client_auth.api_key))

    openapi = client_auth.get_openapi()
    if not openapi:
        print('OpenAPI not available; aborting scan')
        return

    paths = openapi.get('paths', {})
    print('OpenAPI paths count =', len(paths))

    results = []
    for path, methods in paths.items():
        for method, meta in methods.items():
            m = method.upper()
            if m not in ('GET','POST','PUT','DELETE','PATCH'):
                continue
            entry = {'method': m, 'path': path}
            try:
                st_a, hdr_a, body_a = client_auth.request_generic(m, path, timeout=CLIENT_TIMEOUT)
            except Exception as e:
                st_a, hdr_a, body_a = 0, {}, {'error': str(e)}
            try:
                st_b, hdr_b, body_b = client_anon.request_generic(m, path, timeout=CLIENT_TIMEOUT)
            except Exception as e:
                st_b, hdr_b, body_b = 0, {}, {'error': str(e)}

            entry.update({
                'auth_status': st_a,
                'anon_status': st_b,
                'auth_preview': safe_preview(body_a),
                'anon_preview': safe_preview(body_b),
                'summary': meta.get('summary') if isinstance(meta, dict) else None,
                'security': meta.get('security') if isinstance(meta, dict) else None,
            })
            results.append(entry)

    out_path = 'scripts/sieg_scan_results.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Summarize
    auth_ok = [r for r in results if r['auth_status'] == 200]
    anon_ok = [r for r in results if r['anon_status'] == 200]
    print('\nSummary:')
    print(' Endpoints total:', len(results))
    print(' Endpoints accessible with key (200):', len(auth_ok))
    print(' Endpoints accessible without key (200):', len(anon_ok))

    if auth_ok:
        print('\nSample endpoints with auth OK:')
        for r in auth_ok[:10]:
            print(f"  {r['method']} {r['path']} -> auth_status={r['auth_status']} anon_status={r['anon_status']}")
            print('   preview:', r['auth_preview'][:200])
    if anon_ok:
        print('\nSample endpoints without auth (public):')
        for r in anon_ok[:10]:
            print(f"  {r['method']} {r['path']} -> anon_status={r['anon_status']}")
            print('   preview:', r['anon_preview'][:200])

    print('\nFull results saved to', out_path)


if __name__ == '__main__':
    main()
