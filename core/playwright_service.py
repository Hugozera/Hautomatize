"""
Serviço de automação com Playwright para o Emissor Nacional
VERSÃO COM THREAD ÚNICA - Resolve problemas de greenlet
"""

import os
import sys
import time
import tempfile
import pickle
import asyncio
import threading
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Tuple, Optional
import traceback

import requests

# Importações do projeto
from .certificado_service import (
    converter_pfx_para_cert_e_key
)

# Configuração do event loop para Windows (UMA VEZ, no início)
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        # Cria um loop principal
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except Exception as e:
        print(f"⚠️ Aviso ao configurar event loop: {e}")


class EmissorNacionalPlaywright:
    """Classe principal para automação com Playwright - OTIMIZADA"""
    
    __slots__ = ('empresa', 'cert_path', 'senha', 'base_url', 'headless',
                 'playwright', 'browser', 'context', 'page', 'download_path',
                 'cert_pem', 'key_pem', 'cookies_path', '_session', '_thread_id')

    def __init__(self, empresa, download_path=None, headless=True):
        self.empresa = empresa
        if not empresa.certificado_arquivo:
            raise Exception("Objeto Empresa sem arquivo de certificado")
        if not empresa.certificado_senha:
            raise Exception("Objeto Empresa sem senha de certificado")
        self.cert_path = empresa.certificado_arquivo.path
        self.senha = empresa.certificado_senha
        self.base_url = "https://www.nfse.gov.br"
        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self._session = None
        self._thread_id = threading.get_ident()  # Armazena ID da thread

        self.download_path = download_path or os.path.join(tempfile.gettempdir(), "nfse_downloads")
        os.makedirs(self.download_path, exist_ok=True)

        self.cert_pem = None
        self.key_pem = None
        self.cookies_path = None

        if empresa.certificado_thumbprint:
            self.cookies_path = os.path.join(
                tempfile.gettempdir(),
                f"cookies_{empresa.certificado_thumbprint[:8]}.pkl"
            )

    def _verificar_thread(self):
        """Verifica se está na mesma thread"""
        if threading.get_ident() != self._thread_id:
            raise RuntimeError(
                f"Playwright não pode ser usado em threads diferentes. "
                f"Criado na thread {self._thread_id}, usado na {threading.get_ident()}"
            )

    def extrair_certificado(self):
        """Extrai certificado do PFX para PEM"""
        self._verificar_thread()
        if not os.path.exists(self.cert_path):
            raise Exception("Certificado não encontrado")

        cert_pem, key_pem = converter_pfx_para_cert_e_key(self.cert_path, self.senha)
        
        if not cert_pem or not key_pem:
            raise Exception("Falha ao extrair certificado")
        
        self.cert_pem = cert_pem
        self.key_pem = key_pem

    def salvar_cookies(self):
        """Salva cookies para reuso futuro"""
        self._verificar_thread()
        if not self.cookies_path or not self.context:
            return
        try:
            with open(self.cookies_path, 'wb') as f:
                pickle.dump(self.context.cookies(), f)
        except Exception as e:
            print(f"⚠️ Erro ao salvar cookies: {e}")

    def carregar_cookies(self) -> bool:
        """Carrega cookies salvos anteriormente"""
        self._verificar_thread()
        if not self.cookies_path or not os.path.exists(self.cookies_path):
            return False
        try:
            with open(self.cookies_path, 'rb') as f:
                cookies = pickle.load(f)
            if cookies and self.context:
                self.context.add_cookies(cookies)
                return True
        except Exception as e:
            print(f"⚠️ Erro ao carregar cookies: {e}")
        return False

    def iniciar(self, usar_cookies=True):
        """Inicia navegador com configurações otimizadas"""
        self._verificar_thread()
        self.extrair_certificado()
        
        # Import Playwright aqui para evitar problemas de importação
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise Exception("Playwright não instalado. Execute: pip install playwright && playwright install chromium")

        try:
            self.playwright = sync_playwright().start()
        except Exception as e:
            print(f"❌ Erro ao iniciar Playwright: {e}")
            raise

        # Otimizações de performance
        launch_options = {
            "headless": self.headless,
            "args": [
                '--disable-gpu',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--no-first-run',
                '--no-sandbox',
                '--no-zygote',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        }
        
        self.browser = self.playwright.chromium.launch(**launch_options)

        context_options = {
            "accept_downloads": True,
            "ignore_https_errors": True,
            "client_certificates": [{
                "origin": self.base_url,
                "certPath": self.cert_pem,
                "keyPath": self.key_pem
            }],
            "viewport": {"width": 1280, "height": 800},
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        self.context = self.browser.new_context(**context_options)
        self.context.set_default_timeout(15000)

        if usar_cookies and self.cookies_path:
            self.carregar_cookies()

        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        return True

    def fazer_login(self) -> bool:
        """Login ultra rápido"""
        self._verificar_thread()
        
        # Tentativa 1: Verificar se já está autenticado
        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Dashboard", timeout=5000)
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            if self._verificar_autenticado():
                self.salvar_cookies()
                return True
        except Exception as e:
            print(f"⚠️ Erro na verificação inicial: {e}")

        # Tentativa 2: Login com certificado
        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Login", timeout=10000)
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            # Clicar no botão de certificado
            self.page.locator("a[href*='Certificado']").first.click(timeout=5000)
            
            # Aguardar redirecionamento
            try:
                self.page.wait_for_url("**/Dashboard**", timeout=10000)
                if self._verificar_autenticado():
                    self.salvar_cookies()
                    return True
            except Exception as e:
                print(f"⚠️ Erro no redirecionamento: {e}")
                
        except Exception as e:
            print(f"⚠️ Erro no login: {e}")

        return False

    def _verificar_autenticado(self) -> bool:
        """Verifica se já está autenticado"""
        self._verificar_thread()
        try:
            return self.page.locator("a[href*='/Notas/']").count() > 0
        except:
            return False

    def acessar_notas(self, tipo: str) -> str:
        """Acessa página de notas"""
        self._verificar_thread()
        url = f"{self.base_url}/EmissorNacional/Notas/{'Emitidas' if tipo == 'emitidas' else 'Recebidas'}"
        self.page.goto(url, timeout=10000)
        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        return self.page.url

    def aplicar_filtro(self, data_inicio: str, data_fim: str) -> str:
        """Aplica filtro de datas"""
        self._verificar_thread()
        data_inicio_fmt = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
        data_fim_fmt = datetime.strptime(data_fim, "%Y-%m-%d").strftime("%d/%m/%Y")

        base_url = self.page.url.split("?")[0]
        url_busca = f"{base_url}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"

        self.page.goto(url_busca, timeout=10000)
        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        return self.page.url

    def extrair_links(self) -> List[Dict]:
        """Extrai links de PDF e XML"""
        self._verificar_thread()
        links = []
        
        # Extrair PDFs
        pdf_links = self.page.locator("a[href*='/Notas/Download/DANFSe/']").all()
        for link in pdf_links:
            try:
                href = link.get_attribute("href")
                if href:
                    if not href.startswith('http'):
                        href = f"https://www.nfse.gov.br{href}"
                    numero = href.split('/')[-1]
                    links.append({"numero": numero, "url": href, "tipo": "PDF"})
            except:
                continue

        # Extrair XMLs
        xml_links = self.page.locator("a[href*='/Notas/Download/NFSe/']").all()
        for link in xml_links:
            try:
                href = link.get_attribute("href")
                if href:
                    if not href.startswith('http'):
                        href = f"https://www.nfse.gov.br{href}"
                    numero = href.split('/')[-1]
                    links.append({"numero": numero, "url": href, "tipo": "XML"})
            except:
                continue

        return links

    def _get_session(self) -> requests.Session:
        """Obtém ou cria sessão HTTP reutilizável"""
        self._verificar_thread()
        if self._session is None:
            cookies = {c['name']: c['value'] for c in self.context.cookies()}
            
            session = requests.Session()
            session.cert = (self.cert_pem, self.key_pem)
            session.verify = False
            session.cookies.update(cookies)
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Connection': 'keep-alive',
            })
            self._session = session
        
        return self._session

    def baixar_notas(self, links: List[Dict]) -> int:
        """Download sequencial (mais estável que paralelo)"""
        self._verificar_thread()
        if not links:
            return 0

        sucessos = 0
        session = self._get_session()
        
        for link in links:
            try:
                resp = session.get(link["url"], timeout=30)
                if resp.status_code == 200:
                    filename = f"{link['numero']}.{link['tipo'].lower()}"
                    caminho = os.path.join(self.download_path, filename)
                    
                    with open(caminho, 'wb') as f:
                        f.write(resp.content)
                    
                    sucessos += 1
                    print(f"✅ Baixado: {filename}")
                else:
                    print(f"❌ Falha {link['url']}: HTTP {resp.status_code}")
            except Exception as e:
                print(f"❌ Erro ao baixar {link.get('numero', 'desconhecido')}: {e}")

        return sucessos

    def fechar(self):
        """Fecha recursos de forma ordenada"""
        self._verificar_thread()
        if self._session:
            self._session.close()
            self._session = None
            
        if self.page:
            try:
                self.page.close()
            except:
                pass
            
        if self.context:
            try:
                self.context.close()
            except:
                pass
            
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
            
        if self.playwright:
            try:
                self.playwright.stop()
            except:
                pass
            
        # Limpar arquivos temporários
        for f in [self.cert_pem, self.key_pem]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass


# ==================== FUNÇÃO PRINCIPAL ====================

def baixar_com_playwright(empresa, tipo, data_inicio, data_fim, pasta_destino=None, headless=True):
    """
    Função principal que executa o download com Playwright
    Versão estável - SEM threads, SEM paralelismo nos downloads
    """
    
    if not pasta_destino:
        pasta_destino = os.path.join('media', 'nfse', tipo, data_inicio[:4], data_inicio[5:7])
    pasta_destino = os.path.abspath(pasta_destino)
    os.makedirs(pasta_destino, exist_ok=True)
    
    # Validações
    if not empresa.certificado_arquivo:
        raise Exception("Empresa não possui certificado. Faça upload antes de tentar o download.")
    if not empresa.certificado_senha:
        raise Exception("Senha do certificado não está configurada para esta empresa.")
    
    cliente = None
    try:
        print(f"\n{'='*60}")
        print(f"🚀 Iniciando download para empresa {empresa.id if hasattr(empresa, 'id') else 'desconhecida'}")
        print(f"📅 Período: {data_inicio} a {data_fim}")
        print(f"📁 Pasta: {pasta_destino}")
        print(f"{'='*60}\n")
        
        # Criar cliente
        cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
        
        # Iniciar navegador
        print("🔄 Iniciando navegador...")
        if not cliente.iniciar(usar_cookies=True):
            cliente.fechar()
            cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
            if not cliente.iniciar(usar_cookies=False):
                raise Exception("Falha ao iniciar Playwright após 2 tentativas")
        print("✅ Navegador iniciado")
        
        # Fazer login
        print("🔄 Fazendo login...")
        if not cliente.fazer_login():
            raise Exception("Falha no login")
        print("✅ Login realizado")
        
        # Acessar notas
        print(f"🔄 Acessando notas {tipo}...")
        cliente.acessar_notas(tipo)
        print("✅ Página de notas acessada")
        
        # Aplicar filtro
        print(f"🔄 Aplicando filtro de {data_inicio} a {data_fim}...")
        cliente.aplicar_filtro(data_inicio, data_fim)
        print("✅ Filtro aplicado")
        
        # Extrair links
        print("🔄 Extraindo links de notas...")
        links = cliente.extrair_links()
        print(f"✅ Encontradas {len(links)} notas para download")
        
        if not links:
            print("⚠️ Nenhuma nota encontrada no período")
            return 0, 0, pasta_destino
        
        # Download sequencial (mais estável)
        print(f"🔄 Iniciando download de {len(links)} arquivos...")
        sucessos = cliente.baixar_notas(links)
        print(f"✅ Download concluído: {sucessos}/{len(links)} sucessos")
        
        return len(links), sucessos, pasta_destino
        
    except Exception as e:
        print(f"❌ Erro durante o download: {e}")
        traceback.print_exc()
        raise
    finally:
        if cliente:
            print("🔄 Fechando navegador...")
            cliente.fechar()
            print("✅ Navegador fechado")


# ==================== VERSÃO COM THREAD (SE NECESSÁRIO) ====================

def baixar_com_playwright_em_thread(empresa, tipo, data_inicio, data_fim, pasta_destino=None, headless=True):
    """
    Executa o download em uma thread separada com seu próprio event loop
    Útil se precisar rodar em background sem bloquear o Django
    """
    
    def _worker():
        # Configura event loop na thread filha
        if sys.platform == "win32":
            try:
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            except Exception as e:
                print(f"⚠️ Erro configurando loop na thread: {e}")
        
        # Executa o download
        return baixar_com_playwright(empresa, tipo, data_inicio, data_fim, pasta_destino, headless)
    
    # Executa em thread
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_worker)
        try:
            return future.result(timeout=600)  # 10 minutos timeout
        except concurrent.futures.TimeoutError:
            raise Exception("Download excedeu o tempo limite de 10 minutos")