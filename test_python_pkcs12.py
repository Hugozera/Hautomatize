#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste de conversão PFX para PEM usando Python puro (cryptography)
Mais robusto para certificados legacy
"""

import os
import tempfile
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.backends import default_backend

pfx_file = r"C:\Hautomatize\media\certificados\JL_XAVIER__CIA_LTDA_2026_senha_Jlx2026_fjhL47E.pfx"
senha = "Jlx@2026"

print("="*70)
print("TESTE DE CONVERSÃO PFX para PEM - PYTHON PURO (cryptography)")
print("="*70)

print(f"\nPFX: {pfx_file}")
print(f"Existe: {os.path.exists(pfx_file)}")
print(f"Tamanho: {os.path.getsize(pfx_file)} bytes")

# Cria arquivo PEM temporário
fd, pem_temp = tempfile.mkstemp(suffix='.pem')
os.close(fd)

print(f"\nArquivo PEM temporário: {pem_temp}")

try:
    print("\n[1] Lendo arquivo PFX...")
    with open(pfx_file, 'rb') as f:
        pfx_data = f.read()
    print(f"✅ PFX lido: {len(pfx_data)} bytes")
    
    print("\n[2] Carregando PKCS12...")
    private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
        pfx_data,
        senha.encode(),
        backend=default_backend()
    )
    print(f"✅ PKCS12 carregado")
    print(f"  - Certificado: {certificate is not None}")
    print(f"  - Chave privada: {private_key is not None}")
    print(f"  - Certificados adicionais: {len(additional_certs) if additional_certs else 0}")
    
    print("\n[3] Convertendo para PEM...")
    from cryptography.hazmat.primitives import serialization
    
    pem_data = b''
    
    # Adiciona certificado
    if certificate:
        pem_data += certificate.public_bytes(serialization.Encoding.PEM)
        print(f"  - Certificado adicionado")
    
    # Adiciona chave privada
    if private_key:
        pem_data += private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        )
        print(f"  - Chave privada adicionada")
    
    # Adiciona certificados adicionais
    if additional_certs:
        for i, cert in enumerate(additional_certs):
            pem_data += cert.public_bytes(serialization.Encoding.PEM)
        print(f"  - {len(additional_certs)} certificado(s) adicional(is) adicionado(s)")
    
    print("\n[4] Escrevendo arquivo PEM...")
    with open(pem_temp, 'wb') as f:
        f.write(pem_data)
    
    file_size = os.path.getsize(pem_temp)
    print(f"✅ PEM escrito com sucesso!")
    print(f"  - Tamanho: {file_size} bytes")
    print(f"  - Arquivo: {pem_temp}")
    
    print("\n[5] Mostrando primeiras linhas do PEM:")
    with open(pem_temp, 'r') as f:
        lines = f.read().split('\n')
    for i, line in enumerate(lines[:5]):
        if line.strip():
            print(f"  {line[:80]}")
    
    print("\n" + "="*70)
    print("✅ SUCESSO! Conversão feita com Python puro")
    print("="*70)
    
except Exception as e:
    print(f"\n❌ ERRO: {e}")
    import traceback
    traceback.print_exc()

finally:
    # Limpa
    if os.path.exists(pem_temp):
        os.remove(pem_temp)
        print("\nArquivo temporário removido")
