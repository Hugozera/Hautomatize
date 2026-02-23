"""
Serviço de certificados digitais para Windows
HDowloader - Download Automático de NFSe
"""

import requests
import subprocess
import tempfile
import os
import hashlib
import random
import string
import time
import ssl
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def gerar_senha_temporaria(tamanho=8):
    """Gera uma senha aleatória para exportação temporária"""
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choice(caracteres) for _ in range(tamanho))

def limpar_arquivo_temporario(caminho):
    """Remove arquivo temporário com segurança"""
    try:
        if caminho and os.path.exists(caminho):
            os.remove(caminho)
            print(f"Arquivo temporário removido: {caminho}")
    except Exception as e:
        print(f"Erro ao remover arquivo temporário: {e}")

def verificar_openssl_instalado():
    """Verifica se o OpenSSL está instalado no sistema"""
    try:
        # Tenta encontrar o openssl em locais comuns
        openssl_paths = [
            'openssl',
            'C:\\Program Files\\OpenSSL-Win64\\bin\\openssl.exe',
            'C:\\Program Files (x86)\\OpenSSL-Win32\\bin\\openssl.exe',
            'C:\\OpenSSL-Win64\\bin\\openssl.exe',
            'C:\\OpenSSL-Win32\\bin\\openssl.exe',
        ]
        
        for path in openssl_paths:
            try:
                result = subprocess.run([path, 'version'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=5)
                if result.returncode == 0:
                    print(f"✅ OpenSSL encontrado: {path}")
                    print(f"Versão: {result.stdout.strip()}")
                    return path
            except:
                continue
        
        print("⚠️ OpenSSL não encontrado")
        return None
        
    except Exception as e:
        print(f"Erro ao verificar OpenSSL: {e}")
        return None

# ============================================
# EXPORTAÇÃO VIA POWERSHELL (CORRIGIDA)
# ============================================

def exportar_certificado_powershell(thumbprint, senha):
    """
    Exporta certificado da loja do Windows usando PowerShell
    
    Args:
        thumbprint (str): Thumbprint do certificado
        senha (str): Senha para proteger o PFX
    
    Returns:
        str: Caminho do arquivo PFX temporário
    """
    # Se a senha estiver vazia, usa 123456 como fallback
    if not senha:
        print("⚠️ Senha vazia, usando 123456 como fallback")
        senha = "123456"
    
    # Criar arquivo temporário
    fd, temp_path = tempfile.mkstemp(suffix='.pfx')
    os.close(fd)
    
    print(f"\n{'='*50}")
    print(f"EXPORTANDO CERTIFICADO VIA POWERSHELL")
    print(f"Thumbprint: {thumbprint}")
    print(f"Arquivo temporário: {temp_path}")
    
    # Escapa a senha para o PowerShell
    senha_escaped = senha.replace("'", "''")
    
    # Script PowerShell para exportar o certificado
    ps_script = f'''
    $ErrorActionPreference = "Stop"
    
    try {{
        $cert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }}
        
        if (-not $cert) {{
            Write-Error "Certificado não encontrado"
            exit 1
        }}
        
        Write-Host "Certificado encontrado: $($cert.Subject)"
        
        $securePassword = ConvertTo-SecureString -String '{senha_escaped}' -Force -AsPlainText
        Export-PfxCertificate -Cert $cert -FilePath '{temp_path}' -Password $securePassword
        
        if (Test-Path '{temp_path}') {{
            Write-Host "Certificado exportado com sucesso"
            exit 0
        }} else {{
            Write-Error "Arquivo não foi criado"
            exit 1
        }}
    }}
    catch {{
        Write-Error $_.Exception.Message
        exit 1
    }}
    '''
    
    try:
        # Executar PowerShell
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command', ps_script],
            capture_output=True,
            text=True,
            shell=False,
            timeout=30
        )
        
        print(f"Saída PowerShell: {result.stdout}")
        
        if result.stderr:
            print(f"Erros PowerShell: {result.stderr}")
        
        if result.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print("✅ Certificado exportado com sucesso via PowerShell")
            return temp_path
        else:
            print(f"❌ PowerShell retornou código {result.returncode}")
            print(f"STDERR: {result.stderr}")
            limpar_arquivo_temporario(temp_path)
            raise Exception("Falha na exportação via PowerShell")
            
    except subprocess.TimeoutExpired:
        print("❌ Timeout na execução do PowerShell")
        limpar_arquivo_temporario(temp_path)
        raise
    except Exception as e:
        print(f"❌ Erro no PowerShell: {e}")
        limpar_arquivo_temporario(temp_path)
        raise


def exportar_certificado_pfx(thumbprint):
    """
    Wrapper que exporta um certificado PFX gerando uma senha temporária.
    Retorna tupla (pfx_path, senha)
    """
    senha = gerar_senha_temporaria(12)
    pfx_path = exportar_certificado_powershell(thumbprint, senha)
    return pfx_path, senha

# ============================================
# CONVERSÃO PFX PARA PEM (COM OPENSSL)
# ============================================

openssl_path = None  # Variável global para cache do caminho do OpenSSL

def converter_pfx_para_pem(pfx_path, senha, pem_path):
    """
    Converte arquivo PFX para formato PEM usando OpenSSL
    
    Returns:
        str: Caminho do arquivo PEM ou None se falhar
    """
    global openssl_path
    
    if openssl_path is None:
        openssl_path = verificar_openssl_instalado()
    
    if not openssl_path:
        print("⚠️ OpenSSL não disponível para conversão")
        return None
    
    try:
        # Converte PFX para PEM
        cmd = [
            openssl_path, 'pkcs12',
            '-in', pfx_path,
            '-out', pem_path,
            '-nodes',  # Não criptografar a chave privada
            '-password', f'pass:{senha}'
        ]
        
        print(f"Convertendo PFX para PEM com OpenSSL...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.getsize(pem_path) > 0:
            print("✅ Conversão para PEM bem-sucedida")
            return pem_path
        else:
            print(f"❌ Falha na conversão: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"Erro na conversão OpenSSL: {e}")
        return None

# ============================================
# CRIAÇÃO DE SESSÃO COM PEM (MÉTODO PRINCIPAL)
# ============================================

def criar_sessao_certificado(thumbprint, senha):
    """
    Cria uma sessão usando o certificado convertido para PEM
    """
    pfx_path = None
    pem_path = None
    
    try:
        print(f"\n{'='*50}")
        print("CRIANDO SESSÃO COM CERTIFICADO (MÉTODO PEM)")
        print(f"Thumbprint: {thumbprint}")
        print(f"Senha: {'*' * len(senha)}")
        
        # Exporta o certificado via PowerShell
        pfx_path = exportar_certificado_powershell(thumbprint, senha)
        
        # Verifica se OpenSSL está disponível
        if not verificar_openssl_instalado():
            raise Exception("OpenSSL não está instalado. Necessário para conversão para PEM.")
        
        # Cria arquivo PEM temporário
        fd, pem_path = tempfile.mkstemp(suffix='.pem')
        os.close(fd)
        
        # Converte para PEM
        pem_result = converter_pfx_para_pem(pfx_path, senha, pem_path)
        
        if not pem_result:
            raise Exception("Falha na conversão para PEM")
        
        print("✅ PEM gerado com sucesso")
        
        # Cria sessão com o PEM
        session = requests.Session()
        session.cert = pem_result
        session.verify = False
        
        # Headers para simular navegador
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        session.timeout = 30
        
        # Armazena caminhos para limpeza
        session._pfx_path = pfx_path
        session._pem_path = pem_path
        original_close = session.close
        
        def close_with_cleanup():
            if hasattr(session, '_pfx_path'):
                limpar_arquivo_temporario(session._pfx_path)
            if hasattr(session, '_pem_path'):
                limpar_arquivo_temporario(session._pem_path)
            original_close()
        
        session.close = close_with_cleanup
        
        print("✅ Sessão criada com sucesso")
        return session
        
    except Exception as e:
        if pfx_path:
            limpar_arquivo_temporario(pfx_path)
        if pem_path:
            limpar_arquivo_temporario(pem_path)
        print(f"❌ Erro ao criar sessão: {e}")
        raise

# ============================================
# FUNÇÃO PARA USAR ARQUIVO SALVO
# ============================================

def criar_sessao_com_arquivo(cert_path, senha):
    """
    Cria sessão usando arquivo .pfx salvo no sistema
    """
    print(f"\n{'='*50}")
    print("CRIANDO SESSÃO COM ARQUIVO PFX")
    print(f"Arquivo: {cert_path}")
    
    pem_path = None
    
    try:
        # Verifica se OpenSSL está disponível
        if not verificar_openssl_instalado():
            raise Exception("OpenSSL não está instalado. Necessário para conversão para PEM.")
        
        # Cria arquivo PEM temporário
        fd, pem_path = tempfile.mkstemp(suffix='.pem')
        os.close(fd)
        
        # Converte para PEM
        pem_result = converter_pfx_para_pem(cert_path, senha, pem_path)
        
        if not pem_result:
            raise Exception("Falha na conversão para PEM")
        
        print("✅ PEM gerado com sucesso")
        
        # Cria sessão com o PEM
        session = requests.Session()
        session.cert = pem_result
        session.verify = False
        
        # Headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        })
        
        session.timeout = 30
        
        # Armazena caminho para limpeza
        session._pem_path = pem_path
        original_close = session.close
        
        def close_with_cleanup():
            if hasattr(session, '_pem_path'):
                limpar_arquivo_temporario(session._pem_path)
            original_close()
        
        session.close = close_with_cleanup
        
        print("✅ Sessão com arquivo criada com sucesso")
        return session
        
    except Exception as e:
        if pem_path:
            limpar_arquivo_temporario(pem_path)
        print(f"❌ Erro ao criar sessão com arquivo: {e}")
        raise

# ============================================
# LISTAR CERTIFICADOS (fallback seguro)
# ============================================

def listar_certificados_windows():
    """Retorna lista de certificados disponíveis no repositório do usuário.
    Implementação resiliente: tenta usar PowerShell/Win32, mas em ambiente sem Windows
    retorna lista vazia em vez de lançar exceção.

    Returns: list of dict { 'thumbprint': str, 'subject': str }
    """
    try:
        # Tenta usar PowerShell para listar em JSON (Windows)
        ps = r"Get-ChildItem Cert:\CurrentUser\My | Select-Object Thumbprint, Subject | ConvertTo-Json"
        result = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and result.stdout.strip():
            import json as _json
            try:
                data = _json.loads(result.stdout)
            except Exception:
                # Se vier um único objeto, normaliza para lista
                try:
                    obj = result.stdout.strip()
                    # tentar extrair Thumbprint/Subject via regex
                    matches = re.findall(r"Thumbprint\s*:\s*([A-F0-9]+)\s*Subject\s*:\s*(.+)", result.stdout, flags=re.I)
                    certs = []
                    for m in matches:
                        certs.append({'thumbprint': m[0].strip(), 'subject': m[1].strip()})
                    return certs
                except Exception:
                    return []

            # Normalize to list
            if isinstance(data, dict):
                data = [data]
            certs = []
            for item in data:
                thumb = item.get('Thumbprint') or item.get('thumbprint')
                subj = item.get('Subject') or item.get('subject')
                if thumb:
                    certs.append({'thumbprint': thumb.strip(), 'subject': subj or ''})
            return certs
    except Exception:
        pass

    # Fallback genérico: retorna lista vazia
    return []


# ============================================
# TESTE DE CERTIFICADO
# ============================================

def testar_certificado(thumbprint, senha):
    """
    Testa se o certificado funciona fazendo uma requisição simples
    """
    session = None
    try:
        print(f"\n{'='*50}")
        print("TESTANDO CERTIFICADO")
        print(f"Thumbprint: {thumbprint}")
        
        session = criar_sessao_certificado(thumbprint, senha)
        
        # Tenta acessar o site
        print("Acessando https://www.nfse.gov.br/EmissorNacional...")
        resp = session.get(
            'https://www.nfse.gov.br/EmissorNacional', 
            timeout=30, 
            verify=False,
            allow_redirects=True
        )
        
        print(f"Status code: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ Certificado funciona!")
            return True
        else:
            print(f"❌ Certificado retornou status {resp.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro no teste: {e}")
        return False
    finally:
        if session:
            session.close()

# ============================================
# EXEMPLO DE USO
# ============================================

if __name__ == "__main__":
    print("="*60)
    print("TESTE DE CERTIFICADO - HDOWLOADER")
    print("="*60)
    
    thumbprint = input("Digite o thumbprint do certificado: ").strip()
    senha = input("Digite a senha do certificado: ").strip()
    
    if not thumbprint or not senha:
        print("❌ Thumbprint e senha são obrigatórios!")
        exit(1)
    
    try:
        # Testa o certificado
        if testar_certificado(thumbprint, senha):
            print("\n✅ Certificado funcionando!")
        else:
            print("\n❌ Certificado não funciona")
            
    except Exception as e:
        print(f"\n❌ Erro: {e}")