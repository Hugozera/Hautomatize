"""
Serviço de automação com Playwright para o Emissor Nacional
Usa certificado mTLS extraído do PFX da empresa
Download automático de NFSe - VERSÃO OTIMIZADA (ULTRA RÁPIDA)
"""

import os
import sys
import time
import tempfile
import subprocess
import pickle
import traceback
import requests
from datetime import datetime
from urllib.parse import quote

from playwright.sync_api import sync_playwright

# Configuração silenciosa
sys.stdout.reconfigure(line_buffering=True)

class EmissorNacionalPlaywright:
    __slots__ = ('empresa', 'cert_path', 'senha', 'base_url', 'headless',
                 'playwright', 'browser', 'context', 'page', 'download_path',
                 'cert_pem', 'key_pem', 'cookies_path')

    def __init__(self, empresa, download_path=None, headless=True):
        self.empresa = empresa
        self.cert_path = empresa.certificado_arquivo.path
        self.senha = empresa.certificado_senha
        self.base_url = "https://www.nfse.gov.br"
        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

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
        if not os.path.exists(self.cert_path):
            raise Exception("Certificado não encontrado")

        cert_fd, cert_pem = tempfile.mkstemp(suffix=".pem")
        key_fd, key_pem = tempfile.mkstemp(suffix=".pem")
        os.close(cert_fd)
        os.close(key_fd)

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
        if not self.cookies_path or not self.context:
            return
        try:
            with open(self.cookies_path, 'wb') as f:
                pickle.dump(self.context.cookies(), f)
        except:
            pass

    def carregar_cookies(self):
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
        self.extrair_certificado()
        self.playwright = sync_playwright().start()

        launch_options = {"headless": self.headless}
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

        if usar_cookies and self.cookies_path:
            self.carregar_cookies()

        self.page = self.context.new_page()
        self.page.set_default_timeout(45000)
        return True

    def fazer_login(self):
        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Dashboard", timeout=15000)
            self.page.wait_for_load_state("networkidle")
            # Verifica presença de elemento que só existe quando autenticado
            try:
                if self.page.locator("a[href*='/Notas/']").count() > 0:
                    return True
            except:
                pass
        except:
            pass

        self.page.goto(f"{self.base_url}/EmissorNacional/Login", timeout=30000)
        self.page.wait_for_load_state("networkidle")

        seletores = [
            "a[href*='Certificado']",
            "a:has-text('Certificado')",
            "img[alt*='certificado']/.."
        ]

        for seletor in seletores:
            try:
                elem = self.page.locator(seletor).first
                if elem.count() > 0:
                    elem.click()
                    break
            except:
                continue

        for _ in range(20):
            time.sleep(0.5)
            try:
                current_url = self.page.url
            except:
                current_url = ''

            if "Dashboard" in current_url:
                # Verifica que a página autenticada contém o link de Notas
                try:
                    if self.page.locator("a[href*='/Notas/']").count() > 0:
                        self.salvar_cookies()
                        return True
                except:
                    pass

        return False

    def acessar_notas(self, tipo):
        url = f"{self.base_url}/EmissorNacional/Notas/{'Emitidas' if tipo == 'emitidas' else 'Recebidas'}"
        self.page.goto(url, timeout=30000)
        self.page.wait_for_load_state("networkidle")
        return self.page.url

    def aplicar_filtro(self, data_inicio, data_fim):
        data_inicio_fmt = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
        data_fim_fmt = datetime.strptime(data_fim, "%Y-%m-%d").strftime("%d/%m/%Y")

        base_url = self.page.url.split("?")[0]
        url_busca = f"{base_url}?executar=1&busca=&datainicio={quote(data_inicio_fmt)}&datafim={quote(data_fim_fmt)}"

        self.page.goto(url_busca, timeout=30000)
        self.page.wait_for_load_state("networkidle")
        time.sleep(1)
        return self.page.url

    def extrair_links(self):
        links = []
        try:
            for link in self.page.locator("a[href*='/Notas/Download/DANFSe/']").all():
                href = link.get_attribute("href")
                if href:
                    if not href.startswith('http'):
                        href = f"https://www.nfse.gov.br{href}"
                    numero = href.split('/')[-1]
                    links.append({"numero": numero, "url": href, "tipo": "PDF"})

            for link in self.page.locator("a[href*='/Notas/Download/NFSe/']").all():
                href = link.get_attribute("href")
                if href:
                    if not href.startswith('http'):
                        href = f"https://www.nfse.gov.br{href}"
                    numero = href.split('/')[-1]
                    links.append({"numero": numero, "url": href, "tipo": "XML"})
        except:
            pass
        return links

    def baixar_notas(self, links):
        cookies = {c['name']: c['value'] for c in self.context.cookies()}

        session = requests.Session()
        session.cert = (self.cert_pem, self.key_pem)
        session.verify = False
        session.cookies.update(cookies)
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        })

        arquivos_antes = set(os.listdir(self.download_path)) if os.path.exists(self.download_path) else set()
        sucessos = 0

        for link in links:
            try:
                resp = session.get(link["url"], timeout=20)
                if resp.status_code == 200:
                    filename = f"{link['numero']}.{link['tipo'].lower()}"
                    caminho = os.path.join(self.download_path, filename)
                    with open(caminho, 'wb') as f:
                        f.write(resp.content)
                    sucessos += 1
            except:
                continue
            time.sleep(0.3)

        return sucessos

    def fechar(self):
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        if self.cert_pem and os.path.exists(self.cert_pem):
            os.remove(self.cert_pem)
        if self.key_pem and os.path.exists(self.key_pem):
            os.remove(self.key_pem)


def baixar_com_playwright(empresa, tipo, data_inicio, data_fim, pasta_destino=None, headless=True):
    if not pasta_destino:
        pasta_destino = os.path.join('media', 'nfse', tipo, data_inicio[:4], data_inicio[5:7])
    pasta_destino = os.path.abspath(pasta_destino)
    os.makedirs(pasta_destino, exist_ok=True)

    cliente = None
    try:
        cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
        cliente.iniciar(usar_cookies=True)

        # Tenta login; se aparentemente "sucesso" mas páginas subsequentes redirecionarem,
        # tentamos novamente sem cookies antes de falhar.
        if not cliente.fazer_login():
            # tentativa sem cookies
            cliente.fechar()
            cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
            cliente.iniciar(usar_cookies=False)
            if not cliente.fazer_login():
                raise Exception("Falha no login")

        cliente.acessar_notas(tipo)
        cliente.aplicar_filtro(data_inicio, data_fim)
        links = cliente.extrair_links()

        if not links:
            # Salva HTML e screenshot para diagnóstico
            try:
                html_path = os.path.join(pasta_destino, f'pagina_notas_{tipo}.html')
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(cliente.page.content())
                screenshot_path = os.path.join(pasta_destino, f'pagina_notas_{tipo}.png')
                cliente.page.screenshot(path=screenshot_path)
            except Exception:
                pass
            return 0, 0, pasta_destino

        sucessos = cliente.baixar_notas(links)
        return len(links), sucessos, pasta_destino

    except Exception as e:
        raise
    finally:
        if cliente:
            cliente.fechar()