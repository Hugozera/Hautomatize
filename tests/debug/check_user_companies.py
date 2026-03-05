import sqlite3

conn = sqlite3.connect('db_prod.sqlite3')
cursor = conn.cursor()

# Total de empresas
cursor.execute('SELECT COUNT(*) FROM core_empresa')
total = cursor.fetchone()[0]
print(f'Total de empresas no banco: {total}')

# Usuários com mais empresas associadas
query = """
SELECT u.username, COUNT(DISTINCT e.id) as qtd
FROM auth_user u
LEFT JOIN core_pessoa p ON u.id = p.user_id
LEFT JOIN core_empresa_usuarios eu ON p.id = eu.pessoa_id
LEFT JOIN core_empresa e ON eu.empresa_id = e.id
WHERE u.username != 'hugomartinscavalcante@gmail.com'
GROUP BY u.username
ORDER BY qtd DESC
LIMIT 10
"""

cursor.execute(query)
rows = cursor.fetchall()
print("\nUsuários com mais empresas associadas:")
for row in rows:
    print(f"  {row[0]}: {row[1]} empresas")

conn.close()
