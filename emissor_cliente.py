# emissor_client.py
"""
Cliente direto para o Emissor Nacional
Executa o fluxo completo de autenticação e download
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import os
import tempfile
import subprocess
import time

class EmissorNacionalClient:
    """
    Cliente direto para o Emissor Nacional
    """
    
    def __init__(self, thumbprint, senha):
        self.thumbprint = thumbprint
        self.senha = senha
        self.session = None
        self.base_url = "https://www.nfse.gov.br"
        self.logged_in = False
        
    def _criar_sessao_certificado(self):
        """Cria sessão com certificado (cópia do código que funciona)"""
        from core.certificado_service import criar_sessao_certificado
        self.session = criar_sessao_certificado(self.thumbprint, self.senha)
        
    def login(self):
        """Tenta diferentes estratégias de login"""
        print("\n" + "="*60)
        print("🔐 TENTATIVA DE LOGIN")
        print("="*60)
        
        # Primeiro, cria a sessão
        self._criar_sessao_certificado()
        
        # Estratégia 1: Acessar página inicial e clicar no link de certificado
        print("\n📌 Estratégia 1: Acesso via link de certificado")
        resp = self.session.get(f"{self.base_url}/EmissorNacional", allow_redirects=True)
        print(f"   Página inicial: {resp.url}")
        
        # Procura por links de acesso com certificado
        soup = BeautifulSoup(resp.text, 'html.parser')
        links_cert = soup.find_all('a', href=True)
        
        for link in links_cert:
            href = link['href']
            if 'Certificado' in href or 'certificado' in href or 'AcessoCertificado' in href:
                url_cert = urljoin(self.base_url, href)
                print(f"   Link encontrado: {url_cert}")
                
                resp = self.session.get(url_cert, allow_redirects=True)
                print(f"   URL após clique: {resp.url}")
                
                if 'Notas' in resp.url or 'Emitidas' in resp.url or 'Recebidas' in resp.url:
                    print("✅ Login bem-sucedido via link de certificado!")
                    self.logged_in = True
                    return True
        
        # Estratégia 2: Tentar POST direto para autenticação
        print("\n📌 Estratégia 2: POST direto")
        login_url = f"{self.base_url}/EmissorNacional/AutenticarCertificado"
        resp = self.session.post(login_url, allow_redirects=True)
        print(f"   URL após POST: {resp.url}")
        
        if 'Notas' in resp.url or 'Emitidas' in resp.url or 'Recebidas' in resp.url:
            print("✅ Login bem-sucedido via POST!")
            self.logged_in = True
            return True
        
        # Estratégia 3: Tentar acessar área logada diretamente
        print("\n📌 Estratégia 3: Acesso direto")
        for area in ['/EmissorNacional/Notas/Recebidas', '/EmissorNacional/Notas/Emitidas']:
            url = f"{self.base_url}{area}"
            print(f"   Tentando: {url}")
            resp = self.session.get(url, allow_redirects=True)
            print(f"   URL final: {resp.url}")
            
            if 'Login' not in resp.url and 'Acesso' not in resp.url:
                print(f"✅ Acesso direto funcionou para {area}!")
                self.logged_in = True
                return True
        
        print("❌ Todas as estratégias de login falharam")
        return False
    
    def buscar_notas(self, tipo, data_inicio, data_fim):
        """Busca notas em um período"""
        if not self.logged_in:
            if not self.login():
                raise Exception("Não foi possível fazer login")
        
        # Formata datas
        data_inicio_fmt = data_inicio.replace('-', '/')
        data_fim_fmt = data_fim.replace('-', '/')
        
        # Define URL base
        url_base = f"{self.base_url}/EmissorNacional/Notas/{'Emitidas' if tipo == 'emitidas' else 'Recebidas'}"
        
        # Monta URL de busca
        url_busca = f"{url_base}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"
        
        print(f"\n🔍 Buscando: {url_busca}")
        resp = self.session.get(url_busca, allow_redirects=True)
        
        return resp
    
    def extrair_notas(self, html):
        """Extrai informações das notas do HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        notas = []
        
        # Procura por linhas da tabela que contenham notas
        linhas = soup.find_all('tr')
        for linha in linhas:
            # Procura links de download na linha
            links = linha.find_all('a', href=True)
            for link in links:
                href = link['href']
                if '/Notas/Download/' in href:
                    numero = href.split('/')[-1]
                    url_completa = urljoin(self.base_url, href)
                    notas.append({
                        'numero': numero,
                        'url': url_completa,
                        'tipo': 'XML' if 'NFSe' in href else 'PDF'
                    })
        
        return notas
    
    def baixar_nota(self, url, pasta_destino):
        """Baixa uma nota específica"""
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 200:
                numero = url.split('/')[-1]
                content_type = resp.headers.get('Content-Type', '')
                
                if 'pdf' in content_type:
                    extensao = '.pdf'
                else:
                    extensao = '.xml'
                
                caminho = os.path.join(pasta_destino, f"{numero}{extensao}")
                with open(caminho, 'wb') as f:
                    f.write(resp.content)
                return True
        except:
            return False

# Teste direto
if __name__ == "__main__":
    print("="*60)
    print("🚀 EMISSOR NACIONAL CLIENT - TESTE")
    print("="*60)
    
    thumbprint = input("Thumbprint: ").strip()
    senha = input("Senha: ").strip()
    
    client = EmissorNacionalClient(thumbprint, senha)
    
    if client.login():
        print("\n✅ Login realizado com sucesso!")
        
        tipo = input("\nTipo (emitidas/recebidas): ").strip() or "recebidas"
        data_inicio = input("Data início (YYYY-MM-DD): ").strip() or "2026-02-01"
        data_fim = input("Data fim (YYYY-MM-DD): ").strip() or "2026-02-28"
        
        resp = client.buscar_notas(tipo, data_inicio, data_fim)
        notas = client.extrair_notas(resp.text)
        
        print(f"\n📊 Notas encontradas: {len(notas)}")
        for nota in notas:
            print(f"   {nota['numero']} - {nota['tipo']}")
        
        # Cria pasta para download
        pasta = os.path.join("downloads", f"{tipo}_{data_inicio}_a_{data_fim}")
        os.makedirs(pasta, exist_ok=True)
        
        print(f"\n⬇️ Baixando notas para {pasta}...")
        for nota in notas:
            if client.baixar_nota(nota['url'], pasta):
                print(f"   ✅ {nota['numero']}")
            else:
                print(f"   ❌ {nota['numero']}")
    else:
        print("\n❌ Falha no login")