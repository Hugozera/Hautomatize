from pathlib import Path
from importlib import import_module
import importlib.util
import sys

def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)  # type: ignore
        return mod
    except Exception as e:
        print(f'  load error for {path}:', e)
        return None

def try_read(p: Path):
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8', errors='replace')
    except Exception as e:
        return None

def main():
    base = Path('media/conversor/convertidos')
    candidates = [
        base / 'BB.txt',
    ]
    # add any BNB-like files
    candidates += list(base.glob('ExtratoContaCorrenteBNB*.txt'))

    # import parsers
    # Ensure project root is on sys.path so absolute imports in modules work
    sys.path.insert(0, str(Path('.').resolve()))

    # Try to load modules directly by path to avoid package import issues
    bb_path = Path('core/parsers/bb_parser.py')
    bnb_path = Path('core/parsers/bnb_parser.py')
    BBParser = None
    BNBParser = None
    if bb_path.exists():
        m = load_module_from_path('bb_parser', str(bb_path))
        if m and hasattr(m, 'BBParser'):
            BBParser = getattr(m, 'BBParser')
    else:
        print('bb_parser.py not found')
    if bnb_path.exists():
        m = load_module_from_path('bnb_parser', str(bnb_path))
        if m and hasattr(m, 'BNBParser'):
            BNBParser = getattr(m, 'BNBParser')
    else:
        print('bnb_parser.py not found')

    for p in candidates:
        txt = try_read(p)
        print('---', p)
        if txt is None:
            print('  missing or unreadable')
            continue
        print('  len', len(txt))
        print('  preview:', (txt[:400].replace('\n','\\n')))
        if BBParser:
            try:
                b = BBParser()
                print('  BB detected?', b.detectar_banco(txt))
            except Exception as e:
                print('  BB detect error', e)
        if BNBParser:
            try:
                n = BNBParser()
                print('  BNB detected?', n.detectar_banco(txt))
            except Exception as e:
                print('  BNB detect error', e)

if __name__ == '__main__':
    main()
