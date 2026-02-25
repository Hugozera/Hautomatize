# Instalação — HDownloder

Instruções para instalar dependências Python e binários necessários.

1) Instalar dependências Python
```
pip install -r requirements.txt
```

Observação: algumas dependências (por ex. `psycopg2-binary`, `greenlet`, `lxml`, `pymupdf`, `Pillow` em versões antigas) podem requerer o compilador C no Windows (Microsoft Visual C++ Build Tools) ou ser instaladas via `conda` para evitar compilação.

2) Instalar navegador para Playwright
```
playwright install chromium
```

3) Tesseract OCR (OBRIGATÓRIO para conversor de PDFs escaneados)
- Baixar: https://github.com/UB-Mannheim/tesseract/wiki
- Instalar e copiar `tesseract.exe` para a raiz do projeto
- Baixar `por.traineddata` de https://github.com/tesseract-ocr/tessdata
- Colocar `por.traineddata` em `tessdata/` na raiz do projeto

Estrutura esperada:

```
D:\Hautomatize\
├── tesseract.exe
└── tessdata/
    └── por.traineddata
```

4) Poppler utils (para processamento de PDFs)
- Baixar de: https://github.com/oschwartz10612/poppler-windows/releases/
- Extrair a pasta `poppler-xx.xx.xx` para a raiz do projeto

Estrutura esperada:

```
D:\Hautomatize\
└── poppler-xx.xx.xx/
    └── Library/
        └── bin/
            ├── pdftotext.exe
            ├── pdftoppm.exe
            └── (outras DLLs)
```

3.a) Observação sobre nomes de pastas e organização (recomendado)

- É recomendado manter as ferramentas em pastas com nomes explícitos na raiz do projeto:
  - `tesseract-ocr/` — contém `tesseract.exe` e a pasta `tessdata/` (ex.: `tesseract-ocr/tesseract.exe`, `tesseract-ocr/tessdata/por.traineddata`).
  - `poppler-<versao>/` — pasta do Poppler extraída (ex.: `poppler-25.12.0/Library/bin/pdftotext.exe`).

  Exemplo (recomendado):

  ```
  D:\Hautomatize\
  ├── tesseract-ocr/
  │   ├── tesseract.exe
  │   └── tessdata/
  │       └── por.traineddata
  └── poppler-25.12.0/
      └── Library/
          └── bin/
              ├── pdftotext.exe
              └── pdftoppm.exe
  ```

 - Manter essa organização facilita apontar caminhos no código ou adicionar as pastas ao `PATH` do sistema.
 - Se preferir colocar os executáveis fora da raiz, garanta que as pastas/executáveis estejam no `PATH`.

Verificação rápida (PowerShell):

```powershell
# Verificar Tesseract
tesseract --version

# Verificar pdftotext (poppler)
pdftotext -v
```

Se os comandos acima funcionarem, o conversor de PDFs deverá localizar as ferramentas corretamente.

5) Visual C++ Build Tools (recomendado para Windows)

Instale o Build Tools do Visual Studio e marque "Desktop development with C++" e o Windows SDK.

Exemplo via winget:
```
winget install --id Microsoft.VisualStudio.2022.BuildTools -e
```

6) Verificação final
```
python manage.py check
python manage.py runserver
```

Se preferir evitar compilar extensões no Windows, crie um ambiente conda com Python 3.11 e instale os pacotes via conda/pip a partir do `requirements.txt`.

---
Arquivo gerado automaticamente a partir das instruções originais do projeto.
