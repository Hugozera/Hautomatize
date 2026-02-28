"""
Serviço de automação com Playwright para o Emissor Nacional
Usa certificado mTLS extraído do PFX da empresa
Download automático de NFSe - VERSÃO ULTRA OTIMIZADA (MUITO MAIS RÁPIDA)
"""

import os
import sys
import time
import tempfile
import subprocess
import pickle
import asyncio
import concurrent.futures
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Tuple, Optional

import requests

# Configuração silenciosa
sys.stdout.reconfigure(line_buffering=True)

# Pool de sessões HTTP para reutilização
_SESSION_POOL = {}

class EmissorNacionalPlaywright:
    __slots__ = ('empresa', 'cert_path', 'senha', 'base_url', 'headless',
                 'playwright', 'browser', 'context', 'page', 'download_path',
                 'cert_pem', 'key_pem', 'cookies_path', '_session')

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

    def extrair_certificado(self):
        """Extrai certificado do PFX para PEM (otimizado)"""
        if not os.path.exists(self.cert_path):
            raise Exception("Certificado não encontrado")

        # Usar arquivos temporários com contexto gerenciado
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as cert_f:
            cert_pem = cert_f.name
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as key_f:
            key_pem = key_f.name

        # Executar comandos em paralelo? Não, dependem um do outro
        subprocess.run([
            "openssl", "pkcs12",
            "-in", self.cert_path,
            "-clcerts", "-nokeys",
            "-out", cert_pem,
            "-passin", f"pass:{self.senha}"
        ], check=True, capture_output=True)

        subprocess.run([
            "openssl", "pkcs12",
            "-in", self.cert_path,
            "-nocerts", "-nodes",
            "-out", key_pem,
            "-passin", f"pass:{self.senha}"
        ], check=True, capture_output=True)

        self.cert_pem = cert_pem
        self.key_pem = key_pem

    def salvar_cookies(self):
        """Salva cookies para reuso futuro"""
        if not self.cookies_path or not self.context:
            return
        try:
            with open(self.cookies_path, 'wb') as f:
                pickle.dump(self.context.cookies(), f)
        except:
            pass

    def carregar_cookies(self) -> bool:
        """Carrega cookies salvos anteriormente"""
        if not self.cookies_path or not os.path.exists(self.cookies_path):
            return False
        try:
            with open(self.cookies_path, 'rb') as f:
                cookies = pickle.load(f)
            if cookies and self.context:
                self.context.add_cookies(cookies)
                return True
        except:
            pass
        return False

    def iniciar(self, usar_cookies=True):
        """Inicia navegador com configurações otimizadas"""
        self.extrair_certificado()
        # Import Playwright lazily to avoid import-time errors when Playwright
        # is not installed (lightweight venvs / CI). This keeps the module
        # importable for web requests that don't need Playwright.
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            raise
        self.playwright = sync_playwright().start()

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
                '--disable-features=VizDisplayCompositor',
                '--disable-accelerated-2d-canvas',
                '--disable-accelerated-jpeg-decoding',
                '--disable-accelerated-mjpeg-decode',
                '--disable-accelerated-video-decode',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
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
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "device_scale_factor": 1,
            "has_touch": False,
            "is_mobile": False
        }

        self.context = self.browser.new_context(**context_options)
        
        # Configurar timeout reduzido
        self.context.set_default_timeout(15000)

        if usar_cookies and self.cookies_path:
            self.carregar_cookies()

        self.page = self.context.new_page()
        self.page.set_default_timeout(15000)
        return True

    def _verificar_autenticado(self) -> bool:
        """Verifica rapidamente se já está autenticado"""
        try:
            # Verificação rápida - se tem link de Notas, está autenticado
            return self.page.locator("a[href*='/Notas/']").count() > 0
        except:
            return False

    def fazer_login(self) -> bool:
        """Login ultra rápido"""
        # Tentativa 1: Verificar se já está autenticado
        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Dashboard", timeout=5000)
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            if self._verificar_autenticado():
                self.salvar_cookies()
                return True
        except:
            pass

        # Tentativa 2: Login com certificado
        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Login", timeout=10000)
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            
            # Clicar no botão de certificado (seletor mais rápido)
            self.page.locator("a[href*='Certificado']").first.click(timeout=5000)
            
            # Aguardar redirecionamento (sem loop, com timeout)
            try:
                self.page.wait_for_url("**/Dashboard**", timeout=10000)
                if self._verificar_autenticado():
                    self.salvar_cookies()
                    return True
            except:
                pass
                
        except:
            pass

        return False

    def acessar_notas(self, tipo: str) -> str:
        """Acessa página de notas"""
        url = f"{self.base_url}/EmissorNacional/Notas/{'Emitidas' if tipo == 'emitidas' else 'Recebidas'}"
        self.page.goto(url, timeout=10000)
        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        return self.page.url

    def aplicar_filtro(self, data_inicio: str, data_fim: str) -> str:
        """Aplica filtro de datas - versão otimizada"""
        data_inicio_fmt = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
        data_fim_fmt = datetime.strptime(data_fim, "%Y-%m-%d").strftime("%d/%m/%Y")

        base_url = self.page.url.split("?")[0]
        url_busca = f"{base_url}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"

        self.page.goto(url_busca, timeout=10000)
        self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        return self.page.url

    def extrair_links(self) -> List[Dict]:
        """Extrai links de PDF e XML - versão otimizada"""
        links = []
        
        # Extrair todos os links de uma vez (seletores mais específicos)
        pdf_links = self.page.locator("a[href*='/Notas/Download/DANFSe/']").all()
        xml_links = self.page.locator("a[href*='/Notas/Download/NFSe/']").all()
        
        # Processar PDFs
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

        # Processar XMLs
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
        if self._session is None:
            cookies = {c['name']: c['value'] for c in self.context.cookies()}
            
            session = requests.Session()
            session.cert = (self.cert_pem, self.key_pem)
            session.verify = False
            session.cookies.update(cookies)
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            })
            self._session = session
        
        return self._session

    def _baixar_arquivo(self, link: Dict) -> Tuple[bool, str]:
        """Baixa um único arquivo (para execução paralela)"""
        try:
            session = self._get_session()
            resp = session.get(link["url"], timeout=10)
            
            if resp.status_code == 200:
                filename = f"{link['numero']}.{link['tipo'].lower()}"
                caminho = os.path.join(self.download_path, filename)
                
                with open(caminho, 'wb') as f:
                    f.write(resp.content)
                
                return True, filename
            return False, f"HTTP {resp.status_code}"
        except Exception as e:
            return False, str(e)

    def baixar_notas_paralelo(self, links: List[Dict], max_workers: int = 5) -> int:
        """
        Download paralelo de notas usando ThreadPoolExecutor
        MUITO MAIS RÁPIDO que download sequencial
        """
        if not links:
            return 0

        sucessos = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submeter todos os downloads
            future_to_link = {
                executor.submit(self._baixar_arquivo, link): link 
                for link in links
            }
            
            # Coletar resultados à medida que completam
            for future in concurrent.futures.as_completed(future_to_link):
                try:
                    sucesso, _ = future.result(timeout=15)
                    if sucesso:
                        sucessos += 1
                except:
                    pass

        return sucessos

    def fechar(self):
        """Fecha recursos de forma ordenada"""
        if self._session:
            self._session.close()
            self._session = None
            
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
            
        # Limpar arquivos temporários
        for f in [self.cert_pem, self.key_pem]:
            if f and os.path.exists(f):
                try:
                    os.remove(f)
                except:
                    pass


def baixar_com_playwright_otimizado(empresa, tipo, data_inicio, data_fim, 
                                   pasta_destino=None, headless=True, 
                                   max_workers=5) -> Tuple[int, int, str]:
    """
    Versão ULTRA OTIMIZADA do download com Playwright
    
    Args:
        empresa: Objeto Empresa
        tipo: 'emitidas' ou 'recebidas'
        data_inicio: Data inicial (YYYY-MM-DD)
        data_fim: Data final (YYYY-MM-DD)
        pasta_destino: Pasta para salvar os arquivos
        headless: Executar em modo headless
        max_workers: Número de downloads paralelos
    
    Returns:
        Tuple[int, int, str]: (total_notas, sucessos, pasta_destino)
    """
    if not pasta_destino:
        pasta_destino = os.path.join('media', 'nfse', tipo, data_inicio[:4], data_inicio[5:7])
    pasta_destino = os.path.abspath(pasta_destino)
    os.makedirs(pasta_destino, exist_ok=True)

    cliente = None
    # validações antecipadas para evitar erros confusos durante a inicialização
    if not empresa.certificado_arquivo:
        raise Exception("Empresa não possui certificado. Faça upload antes de tentar o download.")
    if not empresa.certificado_senha:
        raise Exception("Senha do certificado não está configurada para esta empresa.")

    try:
        # Tentativa 1: Com cookies
        cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
        if not cliente.iniciar(usar_cookies=True) or not cliente.fazer_login():
            # Se falhou, tenta sem cookies (apenas uma vez)
            if cliente:
                cliente.fechar()
            cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
            if not cliente.iniciar(usar_cookies=False) or not cliente.fazer_login():
                raise Exception("Falha no login após 2 tentativas")

        # Acessar notas e aplicar filtro
        cliente.acessar_notas(tipo)
        cliente.aplicar_filtro(data_inicio, data_fim)
        
        # Extrair links
        links = cliente.extrair_links()
        
        if not links:
            # Diagnóstico rápido
            try:
                html_path = os.path.join(pasta_destino, f'pagina_notas_{tipo}.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(cliente.page.content())
                screenshot_path = os.path.join(pasta_destino, f'pagina_notas_{tipo}.png')
                cliente.page.screenshot(path=screenshot_path, timeout=5000)
            except:
                pass
            return 0, 0, pasta_destino

        # Download paralelo dos arquivos
        sucessos = cliente.baixar_notas_paralelo(links, max_workers=max_workers)
        
        return len(links), sucessos, pasta_destino

    except Exception as e:
        raise
    finally:
        if cliente:
            cliente.fechar()


# Manter função original para compatibilidade (agora usando a otimizada)
def baixar_com_playwright(empresa, tipo, data_inicio, data_fim, pasta_destino=None, headless=True):
    """Função original mantida para compatibilidade - agora usa versão otimizada"""
    return baixar_com_playwright_otimizado(
        empresa, tipo, data_inicio, data_fim, 
        pasta_destino=pasta_destino, 
        headless=headless,
        max_workers=5
    )