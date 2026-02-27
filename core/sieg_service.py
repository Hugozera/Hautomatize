import os
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SiegClient:
    """Client for SIEG with retries, caching and pagination helpers.

    Usage:
      client = SiegClient(api_key='...')
      openapi = client.get_openapi()
      items = client.fetch_list(method, path)
    """

    DEFAULT_CACHE_TTL = 60 * 5

    def __init__(self, base_url=None, api_key=None, timeout=15, max_retries=3):
        self.base_url = base_url or getattr(settings, 'SIEG_BASE_URL', 'https://api.sieg.com')
        self.api_key = api_key or getattr(settings, 'SIEG_API_KEY', None) or os.environ.get('SIEG_API_KEY')
        self.timeout = timeout
        self.session = requests.Session()
        retries = Retry(total=max_retries, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset(['GET','POST','PUT','DELETE','PATCH','OPTIONS']))
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))

    def _headers(self):
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'Hautomatize/1.0'
        }
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
            headers['x-api-key'] = self.api_key
        return headers

    def get_openapi(self, use_cache=True):
        """Fetch the OpenAPI/Swagger JSON with optional caching."""
        cache_key = f'sieg_openapi:{self.base_url}:{self.api_key}'
        if use_cache:
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

        url = f"{self.base_url.rstrip('/')}/swagger/docs/ver"
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            cache.set(cache_key, data, timeout=self.DEFAULT_CACHE_TTL)
            return data
        except requests.HTTPError as e:
            logger.warning('Failed to fetch OpenAPI (%s): %s', url, e)
            return None
        except Exception as e:
            logger.exception('Unexpected error fetching OpenAPI: %s', e)
            return None

    def list_tags_and_paths(self):
        data = self.get_openapi()
        if not data:
            return {}
        paths = data.get('paths', {})
        by_tag = {}
        for path, methods in paths.items():
            for method, meta in methods.items():
                tags = meta.get('tags') or ['Default']
                summary = meta.get('summary') or meta.get('description') or ''
                for tag in tags:
                    by_tag.setdefault(tag, []).append((method.upper(), path, summary))
        return by_tag

    def find_path_for_keyword(self, keyword: str):
        data = self.get_openapi()
        if not data:
            return None, None, None
        paths = data.get('paths', {})
        key = keyword.lower()
        for path, methods in paths.items():
            if key in path.lower():
                for method, meta in methods.items():
                    return method.upper(), path, meta
        for path, methods in paths.items():
            for method, meta in methods.items():
                tags = meta.get('tags') or []
                summary = (meta.get('summary') or '')
                if any(key in (t or '').lower() for t in tags) or key in summary.lower():
                    return method.upper(), path, meta
        return None, None, None

    def _build_url(self, path: str):
        if path.startswith('http://') or path.startswith('https://'):
            return path
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def request_generic(self, method: str, path: str, params=None, json_body=None, data=None, files=None, timeout=None, stream=False):
        timeout = timeout or self.timeout
        method = method.upper()
        url = self._build_url(path)
        try:
            resp = self.session.request(method, url, headers=self._headers(), params=params, json=json_body, data=data, files=files, timeout=timeout, stream=stream)
            status = resp.status_code
            # handle common auth / quota errors
            if status in (401, 403):
                # Try a few fallback header combinations in case the API expects
                # only `x-api-key`, a different header casing, or a different
                # Authorization scheme (some SIEG installs vary).
                original_headers = self._headers()
                fallbacks = []
                # 1) try without Authorization header (only x-api-key)
                if 'Authorization' in original_headers and 'x-api-key' in original_headers:
                    h = {k: v for k, v in original_headers.items() if k.lower() != 'authorization'}
                    fallbacks.append(h)
                # 2) try uppercase header name
                if 'x-api-key' in original_headers:
                    h2 = dict(original_headers)
                    h2.pop('x-api-key', None)
                    h2['X-API-KEY'] = original_headers.get('x-api-key')
                    fallbacks.append(h2)
                # 3) try Authorization with ApiKey scheme
                if 'x-api-key' in original_headers:
                    h3 = dict(original_headers)
                    h3['Authorization'] = f'ApiKey {original_headers.get("x-api-key")}'
                    fallbacks.append(h3)

                for fh in fallbacks:
                    try:
                        resp2 = self.session.request(method, url, headers=fh, params=params, json=json_body, data=data, files=files, timeout=timeout, stream=stream)
                        if stream:
                            if resp2.status_code not in (401, 403):
                                return resp2.status_code, dict(resp2.headers), resp2
                        else:
                            if resp2.status_code not in (401, 403):
                                content_type2 = resp2.headers.get('Content-Type', '')
                                try:
                                    if 'application/json' in content_type2:
                                        body2 = resp2.json()
                                    else:
                                        body2 = resp2.text
                                except Exception:
                                    body2 = resp2.text
                                return resp2.status_code, dict(resp2.headers), body2
                    except requests.RequestException:
                        continue

                return status, dict(resp.headers), {'error': 'Unauthorized or invalid API key', 'status': status}
            if status == 429:
                return status, dict(resp.headers), {'error': 'Rate limited (429)', 'status': status}

            # streaming: return response object to caller to handle content
            if stream:
                return status, dict(resp.headers), resp

            content_type = resp.headers.get('Content-Type', '')
            try:
                if 'application/json' in content_type:
                    body = resp.json()
                else:
                    body = resp.text
            except Exception:
                body = resp.text
            return status, dict(resp.headers), body
        except requests.RequestException as e:
            logger.exception('Sieg request failed: %s %s', method, path)
            return 0, {}, {'error': str(e)}

    def fetch_list(self, method: str, path: str, params=None, json_body=None, max_pages=20, page_param_names=None, page_size_param_names=None, operation_meta=None):
        """Attempt to fetch a list of items from an endpoint handling common pagination patterns.

        Returns a tuple (status, headers, items_or_error).
        """
        # try a cached call first
        cache_key = f'sieg_req:{method}:{path}:{str(params or {})}:{str(json_body or {})}:{self.api_key}'
        cached = cache.get(cache_key)
        if cached is not None:
            return 200, {}, cached

        # default pagination param candidates
        page_param_names = page_param_names or ['pagina', 'page', 'pageNumber', 'pageIndex', 'page']
        page_size_param_names = page_size_param_names or ['pageSize', 'take', 'limit']

        # try to infer required params from OpenAPI operation meta if provided
        if operation_meta is None:
            # locate meta in openapi if possible
            try:
                openapi = self.get_openapi()
                if openapi:
                    paths = openapi.get('paths', {})
                    # path keys in OpenAPI may be absolute; try to find matching path
                    meta = None
                    for pkey, methods in paths.items():
                        if pkey.rstrip('/').lower() == path.rstrip('/').lower():
                            meta = methods.get(method.lower())
                            break
                    operation_meta = meta
            except Exception:
                operation_meta = None

        # if operation_meta has required parameters, prepare sensible defaults
        if operation_meta and isinstance(operation_meta, dict):
            for p in operation_meta.get('parameters', []):
                try:
                    if p.get('in') == 'query' and p.get('required') and (not params or p.get('name') not in params):
                        pname = p.get('name')
                        ptype = p.get('type') or (p.get('schema') or {}).get('type')
                        if pname.lower() == 'active' or pname.lower() == 'ativo':
                            params = dict(params or {})
                            params[pname] = True
                        elif ptype == 'boolean':
                            params = dict(params or {})
                            params[pname] = True
                        elif ptype in ('integer', 'number'):
                            params = dict(params or {})
                            params[pname] = 1
                        else:
                            params = dict(params or {})
                            params[pname] = ''
                except Exception:
                    continue
            # if body param required and no json_body, send empty object
            for p in operation_meta.get('parameters', []):
                if p.get('in') == 'body' and p.get('required') and not json_body:
                    json_body = {}

        # initial request
        status, hdrs, body = self.request_generic(method, path, params=params, json_body=json_body)
        if status != 200:
            return status, hdrs, body

        items = []
        # if body is list -> return directly
        if isinstance(body, list):
            items = body
            cache.set(cache_key, items, timeout=self.DEFAULT_CACHE_TTL)
            return 200, hdrs, items

        # if body contains common wrappers
        if isinstance(body, dict):
            # direct items
            for key in ('data', 'items', 'result', 'value'):
                if isinstance(body.get(key), list):
                    items = body.get(key)
                    cache.set(cache_key, items, timeout=self.DEFAULT_CACHE_TTL)
                    return 200, hdrs, items

        # attempt incremental pagination using query params
        # try different page param names until we get a working pattern
        for page_param in page_param_names:
            collected = []
            for p in range(0, max_pages):
                q = dict(params or {})
                # many APIs are 1-based page
                q[page_param] = p + 1
                status2, hdrs2, body2 = self.request_generic(method, path, params=q, json_body=json_body)
                if status2 != 200:
                    break
                if isinstance(body2, list):
                    if not body2:
                        break
                    collected.extend(body2)
                elif isinstance(body2, dict):
                    found = None
                    for key in ('data', 'items', 'result', 'value'):
                        if isinstance(body2.get(key), list):
                            found = body2.get(key)
                            break
                    if found is None:
                        # not a paginated shape
                        collected = []
                        break
                    if not found:
                        break
                    collected.extend(found)
                else:
                    break
                # heuristic: stop if less than typical page size
                if len(collected) >= 10000:
                    break
            if collected:
                cache.set(cache_key, collected, timeout=self.DEFAULT_CACHE_TTL)
                return 200, hdrs, collected

        # fallback: return original body
        return 200, hdrs, body
