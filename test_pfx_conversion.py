#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para testar conversão de PFX para PEM
Use: python test_pfx_conversion.py
"""

import os
import sys

# Adiciona core ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.certificado_service import (
    configurar_ambiente_openssl, 
    verificar_openssl_instalado,
    testar_conversao_pfx
)

def main():
    print("="*70)
    print("TESTE DE CONVERSÃO PFX PARA PEM - HDOWLOADER")
    print("="*70)
    
    # Configura ambiente
    print("\n[1] Configurando ambiente OpenSSL...")
    configurar_ambiente_openssl()
    
    # Verifica OpenSSL
    print("\n[2] Verificando OpenSSL...")
    openssl_path = verificar_openssl_instalado()
    
    if not openssl_path:
        print("❌ OpenSSL não foi encontrado!")
        print("\nLocais procurados:")
        PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
        print(f"  - {os.path.join(PROJECT_ROOT, 'OpenSSL-Win64', 'bin', 'openssl.exe')}")
        print(f"  - {os.path.join(PROJECT_ROOT, 'lib', 'OpenSSL-Win64', 'bin', 'openssl.exe')}")
        print(f"  - C:\\Program Files\\OpenSSL-Win64\\bin\\openssl.exe")
        sys.exit(1)
    
    print(f"✅ OpenSSL encontrado: {openssl_path}")
    
    # Pede dados do certificado
    print("\n[3] Usando certificado padrão...")
    pfx_path = r"C:\Hautomatize\media\certificados\JL_XAVIER__CIA_LTDA_2026_senha_Jlx2026_fjhL47E.pfx"
    print(f"📄 PFX: {pfx_path}")
    
    if not os.path.exists(pfx_path):
        print(f"❌ Arquivo não encontrado: {pfx_path}")
        sys.exit(1)
    
    senha = "Jlx@2026"
    print(f"🔐 Senha: (usando credencial padrão)")
    
    # Testa conversão
    print("\n[4] Testando conversão...")
    resultado = testar_conversao_pfx(pfx_path, senha)
    
    if resultado:
        print("\n" + "="*70)
        print("✅ SUCESSO! Conversão funcionando corretamente.")
        print("="*70)
        sys.exit(0)
    else:
        print("\n" + "="*70)
        print("❌ FALHA! Verifique os erros acima.")
        print("="*70)
        sys.exit(1)

if __name__ == "__main__":
    main()
