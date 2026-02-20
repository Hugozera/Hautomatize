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

pasta_download = os.path.abspath('downloads_debug2')
os.makedirs(pasta_download, exist_ok=True)

cli = EmissorNacionalPlaywright(empresa, download_path=pasta_download, headless=True)
cli.iniciar(usar_cookies=False)

# Tenta acessar dashboard e imprime URL
cli.page.goto(cli.base_url + '/EmissorNacional/Dashboard')
print('URL after Dashboard attempt:', cli.page.url)

# Agora chama fazer_login() e imprime page.url
res = cli.fazer_login()
print('fazer_login returned:', res)
print('URL after fazer_login:', cli.page.url)

# Acessa notas explicitamente
cli.acessar_notas('recebidas')
print('URL after acessar_notas:', cli.page.url)

# Carrega conteúdo e conta links
cli.aplicar_filtro('2026-02-01','2026-02-28')
print('URL after aplicar_filtro:', cli.page.url)
print('Content length:', len(cli.page.content()))
print('PDF links count:', cli.page.locator("a[href*='/Notas/Download/DANFSe/']").count())
print('XML links count:', cli.page.locator("a[href*='/Notas/Download/NFSe/']").count())

cli.fechar()
print('Fechado')