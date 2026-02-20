import os
import sys
sys.path.append(os.path.abspath('.'))

from core.playwright_service import EmissorNacionalPlaywright

class EmpresaSimulada:
    def __init__(self, nome, cert_path, senha, thumbprint=None):
        self.nome_fantasia = nome
        self.certificado_arquivo = type('X', (), {'path': cert_path})
        self.certificado_senha = senha
        self.certificado_thumbprint = thumbprint

cert_path = os.path.abspath('media/certificados/CERTIFICADO_BAZIQUETO.pfx')
empresa = EmpresaSimulada('FARMAIVI', cert_path, 'LG$XiA82')

pasta_download = os.path.abspath('downloads_debug')
os.makedirs(pasta_download, exist_ok=True)

cli = EmissorNacionalPlaywright(empresa, download_path=pasta_download, headless=True)
print('iniciar ->', cli.iniciar(usar_cookies=True))
print('fazer_login ->', cli.fazer_login())
print('acessar_notas ->', cli.acessar_notas('recebidas'))
print('aplicar_filtro ->', cli.aplicar_filtro('2026-02-01','2026-02-28'))

# Conteúdo da página após filtro
content = cli.page.content()
print('\nTamanho do content:', len(content))
print('\nTrecho (0..1000):\n', content[:1000])

# Contagens de elementos
count_pdf = cli.page.locator("a[href*='/Notas/Download/DANFSe/']").count()
count_xml = cli.page.locator("a[href*='/Notas/Download/NFSe/']").count()
print('\nCount PDF links:', count_pdf)
print('Count XML links:', count_xml)

# Extrair atributos href para checar
pdfs = cli.page.locator("a[href*='/Notas/Download/DANFSe/']")
xmls = cli.page.locator("a[href*='/Notas/Download/NFSe/']")
for i in range(min(5, pdfs.count())):
    print('PDF href', i, pdfs.nth(i).get_attribute('href'))
for i in range(min(5, xmls.count())):
    print('XML href', i, xmls.nth(i).get_attribute('href'))

cli.fechar()
print('\nFechado')