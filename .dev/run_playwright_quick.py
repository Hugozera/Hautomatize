import os
import sys
sys.path.append(os.path.abspath('.'))

from core.playwright_service import baixar_com_playwright

class EmpresaSimulada:
    def __init__(self, nome, cert_path, senha, thumbprint=None):
        self.nome_fantasia = nome
        self.certificado_arquivo = type('X', (), {'path': cert_path})
        self.certificado_senha = senha
        self.certificado_thumbprint = thumbprint

cert_path = os.path.abspath('media/certificados/CERTIFICADO_BAZIQUETO.pfx')
empresa = EmpresaSimulada('FARMAIVI', cert_path, 'LG$XiA82')

pasta_download = os.path.abspath('downloads_recebidas_2026-02-01_a_2026-02-28')

print('Iniciando baixar_com_playwright (headless=True) \n')
links, sucesso, pasta = baixar_com_playwright(empresa, 'recebidas', '2026-02-01', '2026-02-28', pasta_destino=pasta_download, headless=True)
print('\nResultado:', links, sucesso, pasta)

if os.path.exists(pasta_download):
    arquivos = os.listdir(pasta_download)
    print('\nArquivos na pasta:')
    for a in arquivos:
        print(' -', a)
else:
    print('\nPasta de download não encontrada')