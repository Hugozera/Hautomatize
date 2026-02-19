"""
Serviço de navegação para o Emissor Nacional
HDowloader - Download Automático de NFSe
"""

import requests
import os
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# Import absoluto
from core.certificado_service import criar_sessao_certificado

class EmissorNacionalSession:
    def __init__(self, thumbprint, senha):
        self.thumbprint = thumbprint
        self.senha = senha
        self.session = None
        self.base_url = "https://www.nfse.gov.br"
        self.logged_in = False
    
    def criar_sessao(self):
        print(f"\n🔐 Criando sessão com certificado...")
        self.session = criar_sessao_certificado(self.thumbprint, self.senha)
        print("✅ Sessão criada!")
        return self.session
    
    def verificar_acesso(self):
        if not self.session:
            self.criar_sessao()
        
        # Tenta acessar diretamente as áreas restritas
        for area in ['/EmissorNacional/Notas/Recebidas', '/EmissorNacional/Notas/Emitidas']:
            url = f"{self.base_url}{area}"
            print(f"   Verificando acesso: {url}")
            try:
                resp = self.session.get(url, allow_redirects=True, timeout=30)
                if 'Login' not in resp.url and 'Acesso' not in resp.url:
                    print(f"✅ Acesso permitido a {area}")
                    self.logged_in = True
                    return True
            except:
                continue
        return False
    
    def buscar_notas(self, tipo, data_inicio, data_fim):
        if not self.session:
            self.criar_sessao()
        
        if not self.logged_in:
            if not self.verificar_acesso():
                raise Exception("Não foi possível autenticar")
        
        data_inicio_fmt = data_inicio.replace('-', '/')
        data_fim_fmt = data_fim.replace('-', '/')
        
        if tipo == 'emitidas':
            url_base = f"{self.base_url}/EmissorNacional/Notas/Emitidas"
        else:
            url_base = f"{self.base_url}/EmissorNacional/Notas/Recebidas"
        
        url_busca = f"{url_base}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"
        print(f"\n🔍 Buscando: {url_busca}")
        return self.session.get(url_busca, allow_redirects=True, timeout=30)
    
    def extrair_links_notas(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/Notas/Download/' in href:
                numero = href.split('/')[-1]
                url_completa = urljoin(self.base_url, href)
                links.append((numero, url_completa))
                print(f"   📄 Link: {numero}")
        return links

# ============================================
# FUNÇÃO QUE SERÁ IMPORTADA
# ============================================
def criar_sessao_navegador(thumbprint, senha):
    """Factory function para criar uma sessão do navegador"""
    print(f"📌 criar_sessao_navegador chamada com thumbprint: {thumbprint[:10]}...")
    navegador = EmissorNacionalSession(thumbprint, senha)
    navegador.criar_sessao()
    
    if navegador.verificar_acesso():
        print("✅ Navegador autenticado!")
        return navegador
    else:
        raise Exception("Falha na autenticação")

# ============================================
# TESTE RÁPIDO
# ============================================
if __name__ == "__main__":
    print("="*60)
    print("TESTE DO NAVEGADOR")
    print("="*60)
    print("✅ Arquivo carregado com sucesso!")
    print("✅ Função criar_sessao_navegador disponível")