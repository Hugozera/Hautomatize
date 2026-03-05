"""
Serviço de navegação para o Emissor Nacional
HDowloader - Download Automático de NFSe
"""

import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# Import absoluto em vez de relativo
from core.certificado_service import criar_sessao_certificado

class EmissorNacionalSession:
    """
    Classe que simula um navegador acessando o Emissor Nacional
    """
    
    def __init__(self, session):
        self.session = session
        self.base_url = "https://www.nfse.gov.br"
        self.logged_in = False
    
    def fazer_login(self):
        """
        Executa o fluxo completo de login com certificado
        """
        print("\n🔐 Executando fluxo de login...")
        
        # Passo 1: Acessar a página inicial
        print("   Acessando página inicial...")
        resp = self.session.get(f"{self.base_url}/EmissorNacional", allow_redirects=True)
        
        # Passo 2: Procurar pelo link de acesso com certificado
        soup = BeautifulSoup(resp.text, 'html.parser')
        link_cert = soup.find('a', href=lambda x: x and 'AcessoCertificado' in x)
        
        if link_cert:
            url_cert = urljoin(self.base_url, link_cert['href'])
            print(f"   Link de certificado encontrado: {url_cert}")
            
            # Passo 3: Clicar no link de acesso com certificado
            resp = self.session.get(url_cert, allow_redirects=True)
            
            # Passo 4: Verificar se foi redirecionado para a área logada
            if 'Notas' in resp.url or 'Emitidas' in resp.url or 'Recebidas' in resp.url:
                print(f"✅ Login bem-sucedido! URL: {resp.url}")
                self.logged_in = True
                return True
        
        print("❌ Falha no login automático. Verificando alternativa...")
        
        # Alternativa: tentar acessar diretamente a área de notas
        for tentativa in ['/EmissorNacional/Notas/Recebidas', '/EmissorNacional/Notas/Emitidas']:
            url = f"{self.base_url}{tentativa}"
            print(f"   Tentando acesso direto: {url}")
            resp = self.session.get(url, allow_redirects=True)
            
            if 'Login' not in resp.url and 'Acesso' not in resp.url:
                print(f"✅ Acesso direto funcionou! URL: {resp.url}")
                self.logged_in = True
                return True
        
        return False
    
    def buscar_notas(self, tipo, data_inicio, data_fim):
        """
        Busca notas em um período específico
        """
        if not self.logged_in:
            if not self.fazer_login():
                raise Exception("Não foi possível fazer login")
        
        # Formata datas
        data_inicio_fmt = data_inicio.replace('-', '/')
        data_fim_fmt = data_fim.replace('-', '/')
        
        # Define URL base
        if tipo == 'emitidas':
            url_base = f"{self.base_url}/EmissorNacional/Notas/Emitidas"
        else:
            url_base = f"{self.base_url}/EmissorNacional/Notas/Recebidas"
        
        # Monta URL de busca
        url_busca = f"{url_base}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"
        
        print(f"\n🔍 Buscando notas: {url_busca}")
        resp = self.session.get(url_busca, allow_redirects=True)
        
        return resp
    
    def extrair_links_notas(self, html):
        """
        Extrai links de download do HTML
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/Notas/Download/' in href:
                numero = href.split('/')[-1]
                url_completa = urljoin(self.base_url, href)
                links.append((numero, url_completa))
                print(f"   📄 Link encontrado: {numero}")
        
        return links

def criar_sessao_navegador(thumbprint, senha):
    """
    Cria uma sessão com fluxo completo de navegação
    """
    # Primeiro cria a sessão com certificado (import absoluto já está no topo)
    session = criar_sessao_certificado(thumbprint, senha)
    
    # Depois cria o navegador em cima dela
    navegador = EmissorNacionalSession(session)
    
    # Tenta fazer login
    if navegador.fazer_login():
        return navegador
    else:
        raise Exception("Não foi possível estabelecer sessão autenticada")

# Função de teste para execução direta
if __name__ == "__main__":
    print("="*60)
    print("TESTE DIRETO DO NAVEGADOR")
    print("="*60)
    
    thumbprint = input("Digite o thumbprint: ").strip()
    senha = input("Digite a senha: ").strip()
    
    try:
        navegador = criar_sessao_navegador(thumbprint, senha)
        print("✅ Navegador criado com sucesso!")
        
        # Testa busca
        tipo = input("Tipo (emitidas/recebidas): ").strip() or "recebidas"
        data_inicio = input("Data início (YYYY-MM-DD) [2026-02-01]: ").strip() or "2026-02-01"
        data_fim = input("Data fim (YYYY-MM-DD) [2026-02-28]: ").strip() or "2026-02-28"
        
        resp = navegador.buscar_notas(tipo, data_inicio, data_fim)
        print(f"Status: {resp.status_code}")
        print(f"URL final: {resp.url}")
        
        links = navegador.extrair_links_notas(resp.text)
        print(f"Total de links encontrados: {len(links)}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()