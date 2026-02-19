"""
Serviço de automação com Playwright para o Emissor Nacional
Usa certificado mTLS extraído do PFX da empresa
Download automático de NFSe - VERSÃO HÍBRIDA (Playwright + Requests)
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

# Força saída imediata no console
try:
    sys.stdout.reconfigure(line_buffering=True)
except:
    class Unbuffered:
        def __init__(self, stream):
            self.stream = stream
        def write(self, data):
            self.stream.write(data)
            self.stream.flush()
        def __getattr__(self, attr):
            return getattr(self.stream, attr)
    sys.stdout = Unbuffered(sys.stdout)

print("\n" + "="*80)
print("🔵 PLAYWRIGHT_SERVICE.PY CARREGADO")
print("="*80)
sys.stdout.flush()


class EmissorNacionalPlaywright:
    """
    Automação NFSe usando Playwright (para navegação) + Requests (para download)
    """

    def __init__(self, empresa, download_path=None, headless=True):
        """
        Args:
            empresa: Objeto Empresa do Django
            download_path: Pasta para salvar arquivos
            headless: True roda sem interface, False mostra navegador
        """
        self.empresa = empresa
        self.cert_path = empresa.certificado_arquivo.path
        self.senha = empresa.certificado_senha
        self.base_url = "https://www.nfse.gov.br"
        self.headless = headless

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

        # Configura pasta de download
        if download_path:
            self.download_path = download_path
        else:
            self.download_path = os.path.join(tempfile.gettempdir(), "nfse_downloads")

        os.makedirs(self.download_path, exist_ok=True)
        print(f"📁 Pasta de download: {self.download_path}")
        sys.stdout.flush()

        # Arquivos temporários para certificado
        self.cert_pem = None
        self.key_pem = None
        self.cookies_path = None

        # Caminho para cookies
        if empresa.certificado_thumbprint:
            self.cookies_path = os.path.join(
                tempfile.gettempdir(), 
                f"cookies_{empresa.certificado_thumbprint[:8]}.pkl"
            )
            print(f"📌 Arquivo de cookies: {self.cookies_path}")
            sys.stdout.flush()

    # ==========================================
    # CONVERSÃO PFX → CERT + KEY
    # ==========================================
    def extrair_certificado(self):
        """Converte o arquivo .pfx em certificado .pem e chave .pem usando openssl"""
        print("\n🔐 Extraindo certificado do PFX...")
        sys.stdout.flush()

        if not os.path.exists(self.cert_path):
            raise Exception(f"❌ Certificado não encontrado: {self.cert_path}")

        # Cria arquivos temporários
        cert_fd, cert_pem = tempfile.mkstemp(suffix=".pem")
        key_fd, key_pem = tempfile.mkstemp(suffix=".pem")
        os.close(cert_fd)
        os.close(key_fd)

        print(f"   Certificado temporário: {cert_pem}")
        print(f"   Chave temporária: {key_pem}")
        sys.stdout.flush()

        try:
            # Extrai certificado (apenas a parte pública)
            subprocess.run([
                "openssl", "pkcs12",
                "-in", self.cert_path,
                "-clcerts",
                "-nokeys",
                "-out", cert_pem,
                "-passin", f"pass:{self.senha}"
            ], check=True, capture_output=True, text=True)

            # Extrai chave privada
            subprocess.run([
                "openssl", "pkcs12",
                "-in", self.cert_path,
                "-nocerts",
                "-nodes",
                "-out", key_pem,
                "-passin", f"pass:{self.senha}"
            ], check=True, capture_output=True, text=True)

            self.cert_pem = cert_pem
            self.key_pem = key_pem
            print("✅ Certificado extraído com sucesso!")
            sys.stdout.flush()

        except subprocess.CalledProcessError as e:
            print(f"❌ Erro na extração: {e.stderr}")
            sys.stdout.flush()
            raise

    # ==========================================
    # GERENCIAMENTO DE COOKIES
    # ==========================================
    def salvar_cookies(self):
        """Salva cookies para uso futuro"""
        if not self.cookies_path or not self.context:
            return False
        try:
            cookies = self.context.cookies()
            with open(self.cookies_path, 'wb') as f:
                pickle.dump(cookies, f)
            print(f"✅ Cookies salvos em: {self.cookies_path}")
            sys.stdout.flush()
            return True
        except Exception as e:
            print(f"⚠️ Erro ao salvar cookies: {e}")
            return False

    def carregar_cookies(self):
        """Carrega cookies salvos"""
        if not self.cookies_path or not os.path.exists(self.cookies_path):
            print("   📂 Nenhum cookie encontrado")
            return False
        try:
            with open(self.cookies_path, 'rb') as f:
                cookies = pickle.load(f)
            if cookies and self.context:
                self.context.add_cookies(cookies)
                print(f"✅ {len(cookies)} cookies carregados")
                return True
        except Exception as e:
            print(f"⚠️ Erro ao carregar cookies: {e}")
        return False

    # ==========================================
    # INICIALIZAÇÃO DO PLAYWRIGHT (APENAS PARA NAVEGAÇÃO)
    # ==========================================
    def iniciar(self, usar_cookies=True):
        """Inicia o Playwright e configura o contexto com certificado"""
        print("\n🚀 Iniciando Playwright...")
        sys.stdout.flush()

        self.extrair_certificado()
        self.playwright = sync_playwright().start()

        launch_options = {"headless": self.headless}
        if not self.headless:
            launch_options["slow_mo"] = 500

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
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        self.context = self.browser.new_context(**context_options)
        
        if usar_cookies and self.cookies_path:
            self.carregar_cookies()

        self.page = self.context.new_page()
        self.page.set_default_timeout(60000)

        print("✅ Playwright iniciado com sucesso!")
        sys.stdout.flush()
        return True

    # ==========================================
    # LOGIN AUTOMÁTICO
    # ==========================================
    def fazer_login(self):
        """Tenta fazer login. Se já estiver logado, retorna True."""
        print("\n🔐 Verificando login...")
        sys.stdout.flush()

        try:
            print("   Acessando página de Notas...")
            self.page.goto(f"{self.base_url}/EmissorNacional/Notas/Recebidas", timeout=30000)
            
            if "Login" not in self.page.url and "Acesso" not in self.page.url:
                print(f"✅ Já está logado! URL: {self.page.url}")
                sys.stdout.flush()
                return True
        except Exception as e:
            print(f"   ⚠️ Não está logado ({e})")
            sys.stdout.flush()

        print("\n🔑 Executando login com certificado...")
        sys.stdout.flush()

        try:
            self.page.goto(f"{self.base_url}/EmissorNacional/Certificado", timeout=30000)
            self.page.wait_for_load_state("networkidle")

            for i in range(30):
                time.sleep(1)
                if "Dashboard" in self.page.url or "Notas" in self.page.url:
                    print(f"✅ Login bem-sucedido após {i+1} segundos! URL: {self.page.url}")
                    sys.stdout.flush()
                    self.salvar_cookies()
                    return True
                if i % 5 == 0:
                    print(f"   ⏳ Aguardando... {30-i} segundos restantes")
                    sys.stdout.flush()

            print("❌ Tempo esgotado - login não confirmado")
            screenshot_path = os.path.join(self.download_path, 'erro_login.png')
            self.page.screenshot(path=screenshot_path)
            print(f"   Screenshot salvo: {screenshot_path}")
            return False

        except Exception as e:
            print(f"❌ Erro no login: {e}")
            sys.stdout.flush()
            traceback.print_exc()
            return False

    # ==========================================
    # BUSCAR NOTAS (Playwright)
    # ==========================================
    def buscar_notas(self, tipo, data_inicio, data_fim):
        """Busca notas no período especificado"""
        print(f"\n🔍 Buscando notas {tipo} de {data_inicio} a {data_fim}...")
        sys.stdout.flush()

        try:
            data_inicio_fmt = datetime.strptime(data_inicio, "%Y-%m-%d").strftime("%d/%m/%Y")
            data_fim_fmt = datetime.strptime(data_fim, "%Y-%m-%d").strftime("%d/%m/%Y")

            print(f"   Datas convertidas: {data_inicio_fmt} a {data_fim_fmt}")
            sys.stdout.flush()

            if tipo == "emitidas":
                url_base = f"{self.base_url}/EmissorNacional/Notas/Emitidas"
            else:
                url_base = f"{self.base_url}/EmissorNacional/Notas/Recebidas"

            url_busca = (
                f"{url_base}?executar=1&busca="
                f"&datainicio={quote(data_inicio_fmt)}"
                f"&datafim={quote(data_fim_fmt)}"
            )

            print(f"   URL: {url_busca}")
            sys.stdout.flush()

            self.page.goto(url_busca, timeout=60000)
            self.page.wait_for_load_state("networkidle")
            time.sleep(2)

        except Exception as e:
            print(f"❌ Erro ao buscar notas: {e}")
            sys.stdout.flush()
            traceback.print_exc()
            raise

    # ==========================================
    # EXTRAIR LINKS DE DOWNLOAD
    # ==========================================
    def extrair_links(self):
        """Extrai todos os links de PDF e XML da página"""
        print("\n📎 Extraindo links de download...")
        sys.stdout.flush()

        links = []

        try:
            # Links de PDF
            pdf_links = self.page.locator("a[href*='/Notas/Download/DANFSe/']")
            count_pdf = pdf_links.count()
            
            for i in range(count_pdf):
                try:
                    href = pdf_links.nth(i).get_attribute("href")
                    if href:
                        if not href.startswith('http'):
                            href = f"https://www.nfse.gov.br{href}"
                        numero = href.split('/')[-1]
                        links.append({"numero": numero, "url": href, "tipo": "PDF"})
                        print(f"   📄 PDF: {numero}")
                        sys.stdout.flush()
                except Exception as e:
                    print(f"      ⚠️ Erro ao processar PDF: {e}")

            # Links de XML
            xml_links = self.page.locator("a[href*='/Notas/Download/NFSe/']")
            count_xml = xml_links.count()
            
            for i in range(count_xml):
                try:
                    href = xml_links.nth(i).get_attribute("href")
                    if href:
                        if not href.startswith('http'):
                            href = f"https://www.nfse.gov.br{href}"
                        numero = href.split('/')[-1]
                        links.append({"numero": numero, "url": href, "tipo": "XML"})
                        print(f"   📄 XML: {numero}")
                        sys.stdout.flush()
                except Exception as e:
                    print(f"      ⚠️ Erro ao processar XML: {e}")

            print(f"✅ Total de links: {len(links)}")
            sys.stdout.flush()

        except Exception as e:
            print(f"❌ Erro ao extrair links: {e}")
            sys.stdout.flush()
            traceback.print_exc()

        return links

    # ==========================================
    # DOWNLOAD DAS NOTAS (REQUESTS) - MAIS RÁPIDO
    # ==========================================
    def baixar_notas(self, links):
        """
        Baixa todas as notas usando requests com o certificado extraído
        MUITO MAIS RÁPIDO que Playwright para download
        """
        print(f"\n⬇️ Baixando {len(links)} notas com requests...")
        sys.stdout.flush()

        # Cria sessão com o certificado
        session = requests.Session()
        session.cert = (self.cert_pem, self.key_pem)
        session.verify = False  # Ignora SSL em desenvolvimento
        
        # Headers para simular navegador
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
        })

        # Conta arquivos antes
        antes = len([f for f in os.listdir(self.download_path) if f.endswith(('.pdf', '.xml'))]) if os.path.exists(self.download_path) else 0
        print(f"   Arquivos antes: {antes}")
        sys.stdout.flush()

        sucessos = 0
        erros = []

        for i, link in enumerate(links, 1):
            try:
                print(f"   {i}/{len(links)} - {link['tipo']}: {link['numero']}")
                sys.stdout.flush()

                # Faz a requisição
                resp = session.get(link["url"], timeout=30)
                
                if resp.status_code == 200:
                    # Determina o nome do arquivo
                    if link['tipo'] == 'PDF':
                        filename = f"{link['numero']}.pdf"
                    else:
                        filename = f"{link['numero']}.xml"
                    
                    caminho = os.path.join(self.download_path, filename)
                    
                    # Salva o arquivo
                    with open(caminho, 'wb') as f:
                        f.write(resp.content)
                    
                    tamanho = len(resp.content)
                    print(f"      ✅ Salvo: {filename} ({tamanho} bytes)")
                    sys.stdout.flush()
                    
                    sucessos += 1
                else:
                    erro_msg = f"Status {resp.status_code}"
                    print(f"      ❌ {erro_msg}")
                    sys.stdout.flush()
                    erros.append(f"{link['numero']}: {erro_msg}")

                # Pequena pausa entre requisições
                time.sleep(0.5)

            except Exception as e:
                erro_msg = str(e)
                print(f"      ❌ Erro: {erro_msg[:100]}")
                sys.stdout.flush()
                erros.append(f"{link['numero']}: {erro_msg}")

        # Conta arquivos depois
        depois = len([f for f in os.listdir(self.download_path) if f.endswith(('.pdf', '.xml'))]) if os.path.exists(self.download_path) else 0
        novos = depois - antes
        
        print(f"\n   Arquivos depois: {depois}")
        print(f"   Novos arquivos: {novos}")
        
        if novos > 0:
            print(f"\n📁 Arquivos baixados nesta sessão:")
            arquivos = os.listdir(self.download_path)
            for arquivo in sorted(arquivos)[-novos:]:
                tamanho = os.path.getsize(os.path.join(self.download_path, arquivo))
                print(f"   📄 {arquivo} - {tamanho:,} bytes".replace(',', '.'))
                sys.stdout.flush()
        
        if erros:
            print(f"\n⚠️ Erros encontrados: {len(erros)}")
            for erro in erros[:5]:
                print(f"   • {erro}")
            sys.stdout.flush()

        return sucessos

    # ==========================================
    # FECHAR RECURSOS
    # ==========================================
    def fechar(self):
        """Fecha navegador e limpa arquivos temporários"""
        print("\n🔒 Finalizando...")
        sys.stdout.flush()

        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

        # Remove arquivos temporários
        if self.cert_pem and os.path.exists(self.cert_pem):
            os.remove(self.cert_pem)
            print("🧹 Certificado temporário removido")
        if self.key_pem and os.path.exists(self.key_pem):
            os.remove(self.key_pem)
            print("🧹 Chave temporária removida")

        print("🔒 Finalizado!")
        sys.stdout.flush()


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def baixar_com_playwright(empresa, tipo, data_inicio, data_fim, pasta_destino=None, headless=True):
    """
    Função principal para baixar notas usando Playwright (navegação) + Requests (download)
    """
    print("\n" + "="*80)
    print("🚀 DOWNLOAD COM PLAYWRIGHT + REQUESTS")
    print("="*80)
    print(f"🏢 Empresa: {empresa.nome_fantasia}")
    print(f"📋 Tipo: {tipo}")
    print(f"📅 Período: {data_inicio} a {data_fim}")
    print(f"🔐 Certificado: {empresa.certificado_arquivo.path if empresa.certificado_arquivo else 'Nenhum'}")
    print(f"👁️ Modo: {'AUTOMÁTICO' if headless else 'VISÍVEL'}")
    sys.stdout.flush()

    if not pasta_destino:
        pasta_destino = os.path.join(
            'media', 'nfse', tipo,
            data_inicio[:4], data_inicio[5:7]
        )

    pasta_destino = os.path.abspath(pasta_destino)
    print(f"📁 Pasta destino: {pasta_destino}")
    sys.stdout.flush()

    try:
        os.makedirs(pasta_destino, exist_ok=True)
        teste_path = os.path.join(pasta_destino, 'teste.txt')
        with open(teste_path, 'w') as f:
            f.write('teste')
        os.remove(teste_path)
        print("✅ Pasta com permissão de escrita")
        sys.stdout.flush()
    except Exception as e:
        print(f"❌ Erro na pasta: {e}")
        raise

    cliente = None
    try:
        cliente = EmissorNacionalPlaywright(empresa, pasta_destino, headless=headless)
        cliente.iniciar(usar_cookies=True)

        if not cliente.fazer_login():
            raise Exception("Falha no login")

        cliente.buscar_notas(tipo, data_inicio, data_fim)
        links = cliente.extrair_links()

        if not links:
            print("\nℹ️ Nenhuma nota encontrada no período")
            return 0, 0, pasta_destino

        print(f"\n📊 Total de notas: {len(links)}")
        print(f"   PDFs: {len([l for l in links if l['tipo'] == 'PDF'])}")
        print(f"   XMLs: {len([l for l in links if l['tipo'] == 'XML'])}")
        sys.stdout.flush()

        sucessos = cliente.baixar_notas(links)

        print("\n" + "="*80)
        print(f"✅ DOWNLOAD CONCLUÍDO!")
        print(f"📊 Total: {len(links)}")
        print(f"✅ Baixadas: {sucessos}")
        print(f"❌ Falhas: {len(links) - sucessos}")
        print(f"📁 Pasta: {pasta_destino}")
        print("="*80)
        sys.stdout.flush()

        return len(links), sucessos, pasta_destino

    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        traceback.print_exc()
        raise
    finally:
        if cliente:
            cliente.fechar()


if __name__ == "__main__":
    print("="*80)
    print("🚀 TESTE DIRETO DO PLAYWRIGHT SERVICE")
    print("="*80)
    print("Este arquivo deve ser usado através do Django.")
    print("Execute: python manage.py runserver")
    print("="*80)