#!/usr/bin/env python3
import sys
from pathlib import Path
import pkgutil
import importlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PAR_DIR = ROOT / 'media' / 'conversor' / 'convertidos'
SRC_DIR = ROOT / 'media' / 'conversor' / 'originais'

from importlib import import_module

def load_parsers():
    parsers = []
    try:
        import core.parsers as parsers_pkg
    except Exception as e:
        return parsers
    for finder, name, ispkg in pkgutil.iter_modules(parsers_pkg.__path__):
        try:
            mod = import_module(f"{parsers_pkg.__name__}.{name}")
        except Exception:
            continue
        for attr in dir(mod):
            obj = getattr(mod, attr)
            try:
                cls = obj
                if hasattr(cls, 'detectar_banco') and hasattr(cls, 'extrair_transacoes'):
                    parsers.append(cls)
            except Exception:
                continue
    return parsers

parsers = load_parsers()
results = []

for pdf in sorted(SRC_DIR.iterdir()):
    if not pdf.name.lower().endswith('.pdf'):
        continue
    base = pdf.stem
    txt_path = PAR_DIR / f"{base}.txt"
    text = ''
    if txt_path.exists():
        text = txt_path.read_text(encoding='utf-8', errors='replace')
    else:
        # try padrao
        pad = PAR_DIR / f"{base}_padrao.txt"
        if pad.exists():
            text = pad.read_text(encoding='utf-8', errors='replace')

    matched = []
    for cls in parsers:
        try:
            inst = cls()
            ok = False
            try:
                ok = inst.detectar_banco(text)
            except Exception:
                ok = False
            if ok:
                nome = getattr(inst, 'banco_nome', cls.__name__)
                matched.append(nome)
        except Exception:
            continue

    results.append({'file': pdf.name, 'matched': ';'.join(matched)})

out = PAR_DIR / 'detected_banks.csv'
with open(out, 'w', encoding='utf-8') as f:
    f.write('file,matched\n')
    for r in results:
        f.write(f"{r['file']},{r['matched']}\n")

print('Wrote', out)
