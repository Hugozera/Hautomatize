import os
import sys
import subprocess
import platform

print("=" * 50)
print("DIAGNÓSTICO DO SISTEMA")
print("=" * 50)

# Python info
print(f"\n📊 Python: {sys.version}")
print(f"📊 Plataforma: {platform.platform()}")
print(f"📊 Arquitetura: {platform.architecture()}")

# Diretórios
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
poppler_path = os.path.join(project_root, 'poppler-25.12.0', 'Library', 'bin')
tesseract_path = os.path.join(project_root, 'Tesseract-OCR', 'tesseract.exe')

print(f"\n📁 Diretório do projeto: {project_root}")

# Verifica Poppler
print(f"\n🔍 VERIFICANDO POPPLER:")
print(f"  Caminho: {poppler_path}")
print(f"  Existe: {os.path.exists(poppler_path)}")

if os.path.exists(poppler_path):
    # Lista arquivos importantes
    arquivos = os.listdir(poppler_path)
    print(f"  Arquivos no diretório: {len(arquivos)}")
    
    # Procura por DLLs
    dlls = [f for f in arquivos if f.endswith('.dll')]
    print(f"  DLLs encontradas: {len(dlls)}")
    if dlls:
        print("  Primeiras 10 DLLs:")
        for dll in sorted(dlls)[:10]:
            tamanho = os.path.getsize(os.path.join(poppler_path, dll))
            print(f"    - {dll} ({tamanho} bytes)")
    
    # Verifica executáveis
    exe_pdftotext = os.path.join(poppler_path, 'pdftotext.exe')
    exe_pdftoppm = os.path.join(poppler_path, 'pdftoppm.exe')
    
    print(f"\n  pdftotext.exe: {'✅' if os.path.exists(exe_pdftotext) else '❌'}")
    print(f"  pdftoppm.exe: {'✅' if os.path.exists(exe_pdftoppm) else '❌'}")

# Verifica Tesseract
print(f"\n🔍 VERIFICANDO TESSERACT:")
print(f"  Caminho: {tesseract_path}")
print(f"  Existe: {os.path.exists(tesseract_path)}")

if os.path.exists(tesseract_path):
    try:
        result = subprocess.run([tesseract_path, '--version'], 
                               capture_output=True, text=True, timeout=5)
        print(f"  Versão: {result.stdout[:100]}")
    except Exception as e:
        print(f"  Erro ao executar: {e}")

# Testa PATH
print(f"\n🔍 VERIFICANDO PATH:")
paths = os.environ.get('PATH', '').split(os.pathsep)
poppler_no_path = [p for p in paths if 'poppler' in p.lower()]
print(f"  Pastas Poppler no PATH: {len(poppler_no_path)}")
for p in poppler_no_path:
    print(f"    - {p}")

print("\n" + "=" * 50)