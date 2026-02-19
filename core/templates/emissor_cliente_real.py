# emissor_cliente_real.py
"""
Cliente que simula um navegador real para o Emissor Nacional
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

class EmissorNacionalReal:
    """
    Cliente que simula um navegador real, incluindo:
    - Headers completos
    - Cookies
    - Sequência de cliques
    - Tempo de espera realista
    """
    
    def __init__(self, thumbprint, senha):
        self.thumbprint = thumbprint
        self.senha = senha
        self.session = None
        self.base_url = "https://www.nfse.gov.br"
        self.logged_in = False
        
        # Headers completos de um navegador real
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }
    
    def criar_sessao_base(self):
        """Cria a sessão base com certificado"""
        from core.certificado_service import criar_sessao_certificado
        print("\n🔐 Criando sessão base com certificado...")
        self.session = criar_sessao_certificado(self.thumbprint, self.senha)
        self.session.headers.update(self.headers)
        print("✅ Sessão base criada")
    
    def fazer_login_completo(self):
        """
        Executa o fluxo COMPLETO de login como um navegador faria
        """
        if not self.session:
            self.criar_sessao_base()
        
        print("\n🌐 Iniciando fluxo de navegação real...")
        
        # Passo 1: Acessar página inicial
        print("1. Acessando página inicial...")
        resp = self.session.get(f"{self.base_url}/EmissorNacional", allow_redirects=True)
        time.sleep(1)  # Pausa realista
        
        # Passo 2: Procurar e clicar no link de certificado
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Procura por qualquer link que leve à autenticação por certificado
        links_cert = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if 'Certificado' in href or 'certificado' in href:
                links_cert.append(href)
        
        if links_cert:
            url_cert = urljoin(self.base_url, links_cert[0])
            print(f"2. Acessando link de certificado: {url_cert}")
            resp = self.session.get(url_cert, allow_redirects=True)
            time.sleep(1)
            
            # Passo 3: Verificar se fomos redirecionados para área logada
            if 'Dashboard' in resp.url or 'Notas' in resp.url:
                print(f"✅ Login bem-sucedido! URL: {resp.url}")
                self.logged_in = True
                return True
        
        # Passo 4: Se falhou, tentar acesso direto com headers realistas
        print("3. Tentando acesso direto com headers completos...")
        for area in ['/EmissorNacional/Notas/Recebidas', '/EmissorNacional/Notas/Emitidas']:
            url = f"{self.base_url}{area}"
            print(f"   Tentando: {url}")
            resp = self.session.get(url, allow_redirects=True)
            time.sleep(0.5)
            
            # Verifica se não foi redirecionado para login
            if 'Login' not in resp.url and 'Acesso' not in resp.url:
                print(f"✅ Acesso direto funcionou! {resp.url}")
                self.logged_in = True
                
                # Salva cookies importantes
                print("\n🍪 Cookies da sessão:")
                for cookie in self.session.cookies:
                    print(f"   {cookie.name}: {cookie.value[:30]}...")
                
                return True
            else:
                print(f"   ⚠️ Redirecionado para: {resp.url}")
        
        return False
    
    def buscar_notas(self, tipo, data_inicio, data_fim):
        """Busca notas mantendo a sessão"""
        if not self.logged_in:
            if not self.fazer_login_completo():
                raise Exception("Falha na autenticação")
        
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

def criar_sessao_navegador_real(thumbprint, senha):
    """Factory function para criar o cliente real"""
    cliente = EmissorNacionalReal(thumbprint, senha)
    if cliente.fazer_login_completo():
        return cliente
    else:
        raise Exception("Falha na autenticação real")

# Teste
if __name__ == "__main__":
    thumbprint = input("Thumbprint: ").strip()
    senha = input("Senha: ").strip()
    
    cliente = criar_sessao_navegador_real(thumbprint, senha)
    print("\n✅ Cliente real autenticado!")
    
    # Testa busca
    resp = cliente.buscar_notas("recebidas", "2026-02-01", "2026-02-28")
    print(f"Status: {resp.status_code}")
    print(f"URL final: {resp.url}")
    
    # Analisa resultado
    soup = BeautifulSoup(resp.text, 'html.parser')
    if 'Nenhum registro encontrado' in resp.text:
        print("📊 Nenhuma nota no período")
    else:
        print("📊 Período com notas")