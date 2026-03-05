#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para OpenSSL
Verifica instalação e configuração
"""

import os
import subprocess
import sys

def check_openssl_locations():
    """Verifica locais comuns do OpenSSL"""
    print("="*70)
    print("DIAGNÓSTICO DE OPENSSL")
    print("="*70)
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    locations = [
        ("Projeto (principal)", os.path.join(project_root, 'OpenSSL-Win64', 'bin', 'openssl.exe')),
        ("Projeto (lib)", os.path.join(project_root, 'lib', 'OpenSSL-Win64', 'bin', 'openssl.exe')),
        ("Projeto (tools)", os.path.join(project_root, 'tools', 'openssl.exe')),
        ("Program Files 64-bit", r"C:\Program Files\OpenSSL-Win64\bin\openssl.exe"),
        ("Program Files 32-bit", r"C:\Program Files (x86)\OpenSSL-Win32\bin\openssl.exe"),
        ("C:\\ raiz 64-bit", r"C:\OpenSSL-Win64\bin\openssl.exe"),
        ("C:\\ raiz 32-bit", r"C:\OpenSSL-Win32\bin\openssl.exe"),
    ]
    
    print("\n[1] Verificando locais do OpenSSL...\n")
    
    found = None
    for name, path in locations:
        exists = os.path.exists(path)
        status = "✅ ENCONTRADO" if exists else "❌ não encontrado"
        print(f"{status:20} {name:25} {path}")
        
        if exists and found is None:
            found = path
    
    if found:
        print(f"\n✅ OpenSSL encontrado em: {found}")
        return found
    else:
        print("\n❌ OpenSSL NÃO encontrado em nenhum local!")
        return None

def test_openssl(openssl_path):
    """Testa se o OpenSSL funciona"""
    print("\n[2] Testando OpenSSL...\n")
    
    try:
        result = subprocess.run(
            [openssl_path, 'version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print(f"✅ OpenSSL funciona!")
            print(f"Versão: {result.stdout.strip()}")
            return True
        else:
            print(f"❌ OpenSSL retornou erro:")
            print(f"Saída: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao testar OpenSSL: {e}")
        return False

def check_environment_variables():
    """Verifica variáveis de ambiente"""
    print("\n[3] Variáveis de ambiente...\n")
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    openssl_lib = os.path.join(project_root, 'OpenSSL-Win64', 'lib')
    openssl_modules = os.path.join(openssl_lib, 'ossl-modules')
    
    print(f"OPENSSL_MODULES deveria apontar para:")
    print(f"  {openssl_modules}")
    print(f"  Existe: {'✅' if os.path.exists(openssl_modules) else '❌'}")
    
    print(f"\nOPENSSL_LIB_PATH deveria apontar para:")
    print(f"  {openssl_lib}")
    print(f"  Existe: {'✅' if os.path.exists(openssl_lib) else '❌'}")
    
    print(f"\nVariáveis de ambiente atuais:")
    print(f"  OPENSSL_MODULES={os.environ.get('OPENSSL_MODULES', 'NÃO DEFINIDA')}")
    print(f"  LD_LIBRARY_PATH={os.environ.get('LD_LIBRARY_PATH', 'NÃO DEFINIDA')}")

def test_sample_pfx(openssl_path):
    """Testa com um arquivo PFX de exemplo se existir"""
    print("\n[4] Testando com arquivo PFX...\n")
    
    sample_pfx = r"C:\Hautomatize\media\certificados\JL_XAVIER__CIA_LTDA_2026_senha_Jlx2026_fjhL47E.pfx"
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    modules_path = os.path.join(project_root, 'OpenSSL-Win64', 'lib', 'ossl-modules')
    
    if os.path.exists(sample_pfx):
        print(f"✅ Arquivo PFX encontrado: {sample_pfx}")
        print(f"Tamanho: {os.path.getsize(sample_pfx)} bytes")
        
        print("\nTentativa 1: Extrair informações (com -provider-path + legacy + nomacver)...")
        try:
            result = subprocess.run(
                [openssl_path, 'pkcs12', '-info', '-in', sample_pfx, '-passin', 'pass:Jlx@2026', '-noout', 
                 '-nomacver', '-provider-path', modules_path, '-provider', 'legacy', '-legacy'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("✅ Certificado lido com -nomacver -provider-path + legacy!")
                lines = result.stdout.split('\n')
                print(f"Primeiras linhas da saída:")
                for line in lines[:5]:
                    if line.strip():
                        print(f"  {line}")
                return True
            else:
                print(f"⚠️ Estratégia 1 falhou (com -nomacver -provider-path + legacy)")
                print(f"Erro: {result.stderr[:300]}")
                
                print("\nTentativa 2: Extrair informações (com -nomacver -provider-path + default)...")
                result2 = subprocess.run(
                    [openssl_path, 'pkcs12', '-info', '-in', sample_pfx, '-passin', 'pass:Jlx@2026', '-noout',
                     '-nomacver', '-provider-path', modules_path, '-provider', 'default'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result2.returncode == 0:
                    print("✅ Certificado lido com -nomacver -provider-path + default!")
                    return True
                else:
                    print(f"⚠️ Estratégia 2 falhou também")
                    print(f"Erro: {result2.stderr[:300]}")
                    
                    print("\nTentativa 3: Extrair informações (com -nomacver -provider-path)...")
                    result3 = subprocess.run(
                        [openssl_path, 'pkcs12', '-info', '-in', sample_pfx, '-passin', 'pass:Jlx@2026', '-noout',
                         '-nomacver', '-provider-path', modules_path],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result3.returncode == 0:
                        print("✅ Certificado lido com -nomacver -provider-path!")
                        return True
                    else:
                        print(f"⚠️ Estratégia 3 também falhou")
                        print(f"Erro: {result3.stderr[:300]}")
                        
                        print("\nTentativa 4: Extrair informações (apenas -nomacver)...")
                        result4 = subprocess.run(
                            [openssl_path, 'pkcs12', '-info', '-in', sample_pfx, '-passin', 'pass:Jlx@2026', '-noout',
                             '-nomacver'],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        
                        if result4.returncode == 0:
                            print("✅ Certificado lido com apenas -nomacver!")
                            return True
                        else:
                            print(f"❌ Todas estratégias falharam")
                            print(f"Erro final: {result4.stderr[:300]}")
                            return False
                
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    else:
        print(f"⚠️ Arquivo PFX de teste não encontrado: {sample_pfx}")
        return False

def main():
    print("\n")
    
    # Verifica locais
    openssl_path = check_openssl_locations()
    
    if not openssl_path:
        print("\n" + "="*70)
        print("❌ DIAGNÓSTICO CONCLUÍDO COM FALHAS")
        print("="*70)
        print("\nAções recomendadas:")
        print("1. Extraia OpenSSL-Win64 para C:\\Hautomatize\\OpenSSL-Win64")
        print("2. Verifique se o arquivo openssl.exe existe em")
        print("   C:\\Hautomatize\\OpenSSL-Win64\\bin\\openssl.exe")
        sys.exit(1)
    
    # Testa OpenSSL
    if not test_openssl(openssl_path):
        print("\n" + "="*70)
        print("❌ DIAGNÓSTICO CONCLUÍDO COM FALHAS")
        print("="*70)
        sys.exit(1)
    
    # Verifica variáveis
    check_environment_variables()
    
    # Testa PFX
    pfx_result = test_sample_pfx(openssl_path)
    
    print("\n" + "="*70)
    if pfx_result:
        print("✅ DIAGNÓSTICO CONCLUÍDO COM SUCESSO")
        print("="*70)
        print("\nAgora você pode rodar:")
        print("  python test_pfx_conversion.py")
        sys.exit(0)
    else:
        print("⚠️ DIAGNÓSTICO COM AVISOS")
        print("="*70)
        print("\nO OpenSSL foi encontrado mas pode haver problemas com certificados legados.")
        print("Tente rodar test_pfx_conversion.py mesmo assim - ele tenta múltiplas estratégias.")
        sys.exit(0)

if __name__ == "__main__":
    main()
