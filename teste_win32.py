import win32com.client
import pythoncom
import tempfile
import os
import subprocess

def testar_certificado_alternativo(thumbprint):
    """
    Testa o certificado usando win32com para exportar e depois usar
    """
    print("="*50)
    print("TESTANDO CERTIFICADO - MÉTODO ALTERNATIVO")
    print(f"Thumbprint: {thumbprint}")
    
    try:
        pythoncom.CoInitialize()
        
        # Método 1: Tentar exportar via PowerShell primeiro
        print("\n1. Exportando via PowerShell...")
        fd, temp_path = tempfile.mkstemp(suffix='.pfx')
        os.close(fd)
        
        ps_script = f'''
        $cert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object {{ $_.Thumbprint -eq '{thumbprint}' }}
        if ($cert) {{
            $securePassword = ConvertTo-SecureString -String "123456" -Force -AsPlainText
            Export-PfxCertificate -Cert $cert -FilePath '{temp_path}' -Password $securePassword
            Write-Host "OK"
        }}
        '''
        
        result = subprocess.run(['powershell', '-Command', ps_script], capture_output=True, text=True)
        
        if os.path.exists(temp_path) and os.path.getsize(temp_path) > 0:
            print(f"✅ Certificado exportado via PowerShell: {temp_path}")
            print(f"   Tamanho: {os.path.getsize(temp_path)} bytes")
        else:
            print("❌ Falha na exportação via PowerShell")
            return
        
        # Método 2: Tentar ler o certificado com cryptography
        print("\n2. Tentando ler o certificado com cryptography...")
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.hazmat.backends import default_backend
        
        with open(temp_path, 'rb') as f:
            pfx_data = f.read()
        
        # Testar com senha 123456
        try:
            cert = pkcs12.load_key_and_certificates(pfx_data, b"123456", default_backend())
            if cert and cert[1]:
                print("✅ Certificado lido com sucesso (senha 123456)")
                print(f"   Subject: {cert[1].subject.rfc4514_string()}")
        except Exception as e:
            print(f"❌ Erro com senha 123456: {e}")
        
        # Testar com senha vazia
        try:
            cert = pkcs12.load_key_and_certificates(pfx_data, None, default_backend())
            if cert and cert[1]:
                print("✅ Certificado lido com sucesso (senha vazia)")
                print(f"   Subject: {cert[1].subject.rfc4514_string()}")
        except Exception as e:
            print(f"❌ Erro com senha vazia: {e}")
        
        # Método 3: Tentar converter para PEM
        print("\n3. Convertendo para PEM...")
        pem_path = temp_path.replace('.pfx', '.pem')
        
        # Tenta converter com openssl
        try:
            cmd = ['openssl', 'pkcs12', '-in', temp_path, '-out', pem_path, '-nodes', '-password', 'pass:123456']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if os.path.exists(pem_path) and os.path.getsize(pem_path) > 0:
                print("✅ Convertido para PEM com sucesso")
                with open(pem_path, 'r') as f:
                    print(f"Primeiras linhas do PEM: {f.read(200)}...")
            else:
                print("❌ Falha na conversão para PEM")
        except Exception as e:
            print(f"❌ Erro na conversão: {e}")
        
        # Método 4: Tentar criar sessão requests com o PEM
        print("\n4. Testando requisição com PEM...")
        if os.path.exists(pem_path):
            import requests
            import ssl
            
            try:
                session = requests.Session()
                session.cert = pem_path
                session.verify = False
                
                response = session.get('https://www.nfse.gov.br/EmissorNacional', timeout=10)
                print(f"✅ Resposta: {response.status_code}")
            except Exception as e:
                print(f"❌ Erro na requisição: {e}")
        
        # Limpeza
        os.remove(temp_path)
        if os.path.exists(pem_path):
            os.remove(pem_path)
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    thumbprint = "30BD94A507A8B767FF9CE8ADAFE73EF357327171"
    testar_certificado_alternativo(thumbprint)