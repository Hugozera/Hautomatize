# emissor_autenticado.py
"""
Cliente completo para o Emissor Nacional
Simula o fluxo de um navegador real
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

class EmissorNacionalAutenticado:
    def __init__(self, session):
        self.session = session
        self.base_url = "https://www.nfse.gov.br"
        self.logged_in = False
    
    def fazer_login_completo(self):
        """
        Executa o fluxo completo de login como um navegador faria
        """
        print("\n🔐 Iniciando fluxo de login completo...")
        
        # Passo 1: Acessar página inicial
        print("1. Acessando página inicial...")
        resp = self.session.get(f"{self.base_url}/EmissorNacional", allow_redirects=True)
        
        # Passo 2: Procurar e clicar no link de certificado
        soup = BeautifulSoup(resp.text, 'html.parser')
        link_cert = soup.find('a', {'href': '/EmissorNacional/Certificado'})
        
        if link_cert:
            url_cert = urljoin(self.base_url, link_cert['href'])
            print(f"2. Acessando link do certificado: {url_cert}")
            resp = self.session.get(url_cert, allow_redirects=True)
            
            # Passo 3: Verificar se foi redirecionado para dashboard
            if 'Dashboard' in resp.url:
                print(f"✅ Login bem-sucedido! Dashboard: {resp.url}")
                self.logged_in = True
                return True
        
        # Passo 4: Tentar acesso direto às notas
        print("3. Tentando acesso direto às notas...")
        for area in ['/EmissorNacional/Notas/Recebidas', '/EmissorNacional/Notas/Emitidas']:
            url = f"{self.base_url}{area}"
            resp = self.session.get(url, allow_redirects=True)
            
            if 'Login' not in resp.url and 'Acesso' not in resp.url:
                print(f"✅ Acesso direto funcionou! {resp.url}")
                self.logged_in = True
                return True
            else:
                print(f"   ⚠️ Redirecionado para: {resp.url}")
        
        return False
    
    def buscar_notas(self, tipo, data_inicio, data_fim):
        """
        Busca notas em um período
        """
        if not self.logged_in:
            if not self.fazer_login_completo():
                raise Exception("Não foi possível fazer login")
        
        from urllib.parse import quote
        data_inicio_fmt = data_inicio.replace('-', '/')
        data_fim_fmt = data_fim.replace('-', '/')
        
        if tipo == 'emitidas':
            url_base = f"{self.base_url}/EmissorNacional/Notas/Emitidas"
        else:
            url_base = f"{self.base_url}/EmissorNacional/Notas/Recebidas"
        
        url_busca = f"{url_base}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"
        print(f"\n🔍 Buscando: {url_busca}")
        
        return self.session.get(url_busca, allow_redirects=True)

def criar_sessao_autenticada(thumbprint, senha):
    """
    Cria uma sessão completamente autenticada
    """
    from core.certificado_service import criar_sessao_certificado
    
    # Cria sessão base com certificado
    session = criar_sessao_certificado(thumbprint, senha)
    
    # Cria cliente autenticado
    cliente = EmissorNacionalAutenticado(session)
    
    if cliente.fazer_login_completo():
        return cliente
    else:
        raise Exception("Falha na autenticação completa")

# Teste
if __name__ == "__main__":
    thumbprint = input("Thumbprint: ").strip()
    senha = input("Senha: ").strip()
    
    cliente = criar_sessao_autenticada(thumbprint, senha)
    print("✅ Cliente autenticado!")
    
    # Testa busca
    resp = cliente.buscar_notas("recebidas", "2026-02-01", "2026-02-28")
    print(f"Status: {resp.status_code}")
    print(f"URL final: {resp.url}")