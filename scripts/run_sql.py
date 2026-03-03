import sqlite3
import os

db = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db.sqlite3'))
sql_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pdfs', 'sql.sql')
with open(sql_path, 'r', encoding='utf-8') as f:
    sql = f.read()
print('Adjusting schema to allow empty certificate fields...')
# ensure certificado_thumbprint and senha have default '' to avoid NOT NULL errors
try:
    db.executescript(r"""
    PRAGMA foreign_keys=off;
    BEGIN TRANSACTION;
    ALTER TABLE core_empresa RENAME TO old_core_empresa;
    CREATE TABLE core_empresa (
        id integer primary key,
        cnpj varchar(18) UNIQUE NOT NULL,
        razao_social varchar(200) NOT NULL,
        nome_fantasia varchar(200) NOT NULL,
        inscricao_municipal varchar(50) NOT NULL,
        ativo bool NOT NULL,
        certificado_thumbprint varchar(40) NOT NULL DEFAULT '',
        certificado_senha varchar(255) NOT NULL DEFAULT '',
        certificado_validade date,
        certificado_emitente varchar(255) NOT NULL DEFAULT '',
        data_cadastro datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
        ultimo_download datetime,
        bairro varchar(100) NOT NULL,
        cep varchar(9) NOT NULL,
        certificado_arquivo varchar(100),
        complemento varchar(100) NOT NULL,
        inscricao_estadual varchar(50) NOT NULL,
        logradouro varchar(200) NOT NULL,
        municipio varchar(100) NOT NULL,
        numero varchar(20) NOT NULL,
        uf varchar(2) NOT NULL,
        tipo varchar(10) NOT NULL,
        ultimo_zip varchar(100)
    );
    INSERT INTO core_empresa SELECT * FROM old_core_empresa;
    DROP TABLE old_core_empresa;
    COMMIT;
    PRAGMA foreign_keys=on;
    """
    )
    print('Schema adjusted.')
except Exception as e:
    print('Schema adjustment failed (may already be applied):', e)

print('Executing SQL import...')
db.executescript(sql)
db.commit()
db.close()

# Atualizar todas as empresas para ativo
print('Updating all companies to active...')
db = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db.sqlite3'))
try:
    db.execute("UPDATE core_empresa SET ativo = 1")
    db.commit()
    result = db.execute("SELECT COUNT(*) FROM core_empresa WHERE ativo = 1").fetchone()
    print(f'All {result[0]} companies are now active.')
except Exception as e:
    print('Failed to update companies:', e)
finally:
    db.close()

print('Done')
