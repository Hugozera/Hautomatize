#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script rápido para testar conversão PFX com -provider-path
"""

import subprocess
import os
import tempfile

openssl_exe = r"C:\Hautomatize\OpenSSL-Win64\bin\openssl.exe"
modules_path = r"C:\Hautomatize\OpenSSL-Win64\lib\ossl-modules"
pfx_file = r"C:\Hautomatize\media\certificados\JL_XAVIER__CIA_LTDA_2026_senha_Jlx2026_fjhL47E.pfx"
senha = "Jlx@2026"

print("="*70)
print("TESTE DIRETO DE CONVERSÃO PFX PARA PEM")
print("="*70)
print(f"\nOpenSSL: {openssl_exe}")
print(f"Módulos: {modules_path}")
print(f"PFX: {pfx_file}")

# Verifica se tudo existe
print("\n[1] Verificando arquivos...")
print(f"  OpenSSL existe: {os.path.exists(openssl_exe)}")
print(f"  Módulos existem: {os.path.exists(modules_path)}")
print(f"  legacy.dll existe: {os.path.exists(os.path.join(modules_path, 'legacy.dll'))}")
print(f"  PFX existe: {os.path.exists(pfx_file)}")

# Cria arquivo PEM temporário
fd, pem_temp = tempfile.mkstemp(suffix='.pem')
os.close(fd)

print(f"\n[2] Criando arquivo PEM temporário: {pem_temp}")

# Comando com -provider-path + -nomacver
cmd = [
    openssl_exe, 'pkcs12',
    '-in', pfx_file,
    '-out', pem_temp,
    '-nodes',
    '-passin', 'stdin',
    '-nomacver',  # Pula verificação de MAC (que usa SHA1)
    '-provider-path', modules_path,
    '-provider', 'legacy',
    '-legacy'
]

print(f"\n[3] Executando comando...")
print(f"Comando: {' '.join(cmd[:6])}...")

result = subprocess.run(
    cmd,
    input=senha,
    capture_output=True,
    text=True,
    timeout=30
)

print(f"\n[4] Resultado:")
print(f"  Código de retorno: {result.returncode}")

if result.returncode == 0:
    print(f"  ✅ SUCESSO!")
    print(f"  Arquivo PEM criado: {pem_temp}")
    print(f"  Tamanho: {os.path.getsize(pem_temp)} bytes")
    
    # Mostra primeiras linhas
    with open(pem_temp, 'r') as f:
        lines = f.read().split('\n')[:3]
        print(f"\n  Primeiras linhas:")
        for line in lines:
            if line:
                print(f"    {line[:80]}")
else:
    print(f"  ❌ FALHA")
    print(f"  STDERR: {result.stderr[:300]}")
    print(f"  STDOUT: {result.stdout[:300]}")

# Limpa
if os.path.exists(pem_temp):
    os.remove(pem_temp)
    print(f"\n[5] Arquivo temporário removido")

print("\n" + "="*70)
