import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import conversor_service

p = r"c:\Hautomatize\media\conversor\processing\173\ExtratoContaCorrenteBNB_20251010_1138_setembro_aonqdaG.txt"
with open(p, 'r', encoding='utf-8', errors='replace') as f:
    t = f.read()
insts = conversor_service._load_parser_instances()
print('Loaded parsers:', [getattr(i,'banco_nome',None) for i in insts])
for i in insts:
    try:
        print(i.banco_nome, '->', i.detectar_banco(t))
    except Exception as e:
        print(i.banco_nome, '-> error', e)

# Try to run BNB parser extraction if present
for i in insts:
    if getattr(i,'banco_nome','').upper() in ('BANCO DO NORDESTE','BNB'):
        print('\nTesting extrair_transacoes for', i.banco_nome)
        trans = i.extrair_transacoes(t)
        print('Found', len(trans), 'transactions')
        for idx, tr in enumerate(trans[:10]):
            print(idx+1, tr)
        break
