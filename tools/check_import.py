import sys
sys.path.insert(0, '.')
import traceback
try:
    import core.conversor_service as cs
    print('Imported OK, has get_formatos_destino?', hasattr(cs, 'get_formatos_destino'))
    print([a for a in dir(cs) if 'get_formatos' in a.lower()])
except Exception:
    traceback.print_exc()
