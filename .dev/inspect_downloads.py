import sqlite3
from pathlib import Path

DB = Path('db.sqlite3')
if not DB.exists():
    print('db.sqlite3 not found')
    raise SystemExit(1)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

print('Últimas 5 tarefas (core_tarefadownload):')
for row in cur.execute('SELECT id, empresa_id, tipo_nota, data_inicio, data_fim, status, data_criacao FROM core_tarefadownload ORDER BY data_criacao DESC LIMIT 5'):
    print(row)

print('\nEmpresas com certificado (id, nome_fantasia, certificado_arquivo):')
for row in cur.execute("SELECT id, nome_fantasia, certificado_arquivo FROM core_empresa WHERE certificado_arquivo IS NOT NULL AND certificado_arquivo != '' ORDER BY nome_fantasia"):
    print(row)

conn.close()