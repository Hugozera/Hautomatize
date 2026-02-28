"""
Serviço de download de NFSe - Versão Otimizada
"""
import sys
import os
import traceback

sys.stdout.reconfigure(line_buffering=True)

try:
    from .playwright_service import baixar_com_playwright
except ImportError as e:
    raise

def download_em_massa(empresa, tipo, data_inicio, data_fim, pasta_destino, url_base=None, senha=None):
    try:
        if not empresa.certificado_arquivo:
            raise Exception("Empresa não possui arquivo de certificado!")
        if not empresa.certificado_senha:
            raise Exception("Senha do certificado não informada para esta empresa.")

        cert_path = empresa.certificado_arquivo.path
        if not os.path.exists(cert_path):
            raise Exception(f"Arquivo de certificado não encontrado")

        resultado = baixar_com_playwright(
            empresa=empresa,
            tipo=tipo,
            data_inicio=data_inicio,
            data_fim=data_fim,
            pasta_destino=pasta_destino,
            headless=True
        )

        if isinstance(resultado, tuple) and len(resultado) >= 2:
            return resultado[0], resultado[1]
        return 0, 0

    except Exception as e:
        traceback.print_exc()
        raise