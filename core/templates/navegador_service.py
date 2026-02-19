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

# ============================================
# CLASSE PRINCIPAL
# ============================================

class EmissorNacionalSession:
    """
    Cliente direto para o Emissor Nacional - usa acesso direto às URLs
    """
    
    def __init__(self, thumbprint, senha):
        self.thumbprint = thumbprint
        self.senha = senha
        self.session = None
        self.base_url = "https://www.nfse.gov.br"
        self.logged_in = False
    
    def criar_sessao(self):
        """Cria a sessão com certificado usando a senha fornecida"""
        print(f"\n🔐 Criando sessão com certificado...")
        print(f"📌 Thumbprint: {self.thumbprint}")
        print(f"📌 Senha: {'*' * len(self.senha)}")
        
        self.session = criar_sessao_certificado(self.thumbprint, self.senha)
        print("✅ Sessão criada!")
        return self.session

    def verificar_acesso(self):
        """
        Verifica se a sessão está autenticada tentando acessar área restrita
        """
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
                else:
                    print(f"   ⚠️ Redirecionado para: {resp.url}")
            except Exception as e:
                print(f"   ⚠️ Erro ao acessar {area}: {e}")
                continue
        
        return False
    
    def buscar_notas(self, tipo, data_inicio, data_fim):
        """
        Busca notas diretamente sem passar por páginas intermediárias
        """
        if not self.session:
            self.criar_sessao()
        
        if not self.logged_in:
            if not self.verificar_acesso():
                raise Exception("Não foi possível autenticar com o certificado. Verifique a senha.")
        
        # Formata datas
        data_inicio_fmt = data_inicio.replace('-', '/')
        data_fim_fmt = data_fim.replace('-', '/')
        
        # Define URL base
        if tipo == 'emitidas':
            url_base = f"{self.base_url}/EmissorNacional/Notas/Emitidas"
        else:
            url_base = f"{self.base_url}/EmissorNacional/Notas/Recebidas"
        
        # Monta URL de busca
        from urllib.parse import quote
        url_busca = f"{url_base}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"
        
        print(f"\n🔍 Buscando notas: {url_busca}")
        resp = self.session.get(url_busca, allow_redirects=True, timeout=30)
        
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
    
    def baixar_nota(self, url, pasta_destino, numero_nota):
        """
        Baixa uma nota específica
        """
        try:
            print(f"⬇️ Baixando nota {numero_nota}...")
            resp = self.session.get(url, timeout=30)
            
            if resp.status_code == 200:
                content_type = resp.headers.get('Content-Type', '').lower()
                if 'pdf' in content_type:
                    extensao = '.pdf'
                elif 'xml' in content_type:
                    extensao = '.xml'
                else:
                    extensao = '.pdf'
                
                caminho = os.path.join(pasta_destino, f"{numero_nota}{extensao}")
                with open(caminho, 'wb') as f:
                    f.write(resp.content)
                print(f"✅ Nota {numero_nota} baixada")
                return True
            else:
                print(f"❌ Erro {resp.status_code} ao baixar {numero_nota}")
                return False
        except Exception as e:
            print(f"❌ Erro ao baixar {numero_nota}: {e}")
            return False


# ============================================
# FUNÇÕES DE FACTORY (APENAS UMA VEZ!)
# ============================================

def criar_sessao_navegador(thumbprint, senha):
    """
    Factory function para criar uma sessão do navegador
    Usa a implementação local (EmissorNacionalSession)
    """
    print(f"📌 Criando sessão navegador para thumbprint: {thumbprint[:10]}...")
    navegador = EmissorNacionalSession(thumbprint, senha)
    navegador.criar_sessao()
    
    if navegador.verificar_acesso():
        print("✅ Navegador autenticado com sucesso!")
        return navegador
    else:
        raise Exception("Não foi possível estabelecer sessão autenticada. Verifique a senha do certificado.")

# ============================================
# TESTE DIRETO
# ============================================

if __name__ == "__main__":
    print("="*60)
    print("🚀 TESTE DO NAVEGADOR")
    print("="*60)
    
    thumbprint = input("Thumbprint: ").strip()
    senha = input("Senha: ").strip()
    
    try:
        navegador = criar_sessao_navegador(thumbprint, senha)
        
        tipo = input("\nTipo (emitidas/recebidas): ").strip() or "recebidas"
        data_inicio = input("Data início (YYYY-MM-DD): ").strip() or "2026-02-01"
        data_fim = input("Data fim (YYYY-MM-DD): ").strip() or "2026-02-28"
        
        resp = navegador.buscar_notas(tipo, data_inicio, data_fim)
        print(f"Status: {resp.status_code}")
        print(f"URL final: {resp.url}")
        
        links = navegador.extrair_links_notas(resp.text)
        print(f"\nTotal de links encontrados: {len(links)}")
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()