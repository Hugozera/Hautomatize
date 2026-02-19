"""
Client-side agent (Windows) — usa certificado instalado no usuário para baixar NFSe e enviar ao servidor.
Usage (example):
    python tools\client_agent.py --thumb 30BD94A5... --server http://127.0.0.1:8000 --token <TOKEN> --empresa 1 --tipo emitidas --data_inicio 2026-02-01 --data_fim 2026-02-28

Requisitos (máquina do usuário):
- Python 3.8+
- pip install requests cryptography beautifulsoup4
- certutil (Windows) disponível (padrão)

Observação: o agente exporta temporariamente o .pfx da loja via certutil e o usa para TLS client auth.
"""
import argparse
import os
import subprocess
import tempfile
import shutil
import requests
from cryptography.hazmat.primitives.serialization import pkcs12, serialization
from cryptography.hazmat.backends import default_backend
from bs4 import BeautifulSoup


def export_pfx_with_certutil(thumbprint: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pfx')
    tmp.close()
    out_path = tmp.name
    cmd = ['certutil', '-user', '-exportPFX', 'My', thumbprint, out_path, '-p', '']
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return out_path


def pfx_to_pem_pair(pfx_path: str, password: str = None):
    with open(pfx_path, 'rb') as f:
        pfx_data = f.read()
    priv_key, cert, additional = pkcs12.load_key_and_certificates(pfx_data, password.encode() if password else None, default_backend())
    if not cert or not priv_key:
        raise RuntimeError('PFX inválido')

    cert_fd = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
    key_fd = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')

    cert_fd.write(cert.public_bytes(serialization.Encoding.PEM))
    cert_fd.flush()
    key_fd.write(priv_key.private_bytes(encoding=serialization.Encoding.PEM,
                                        format=serialization.PrivateFormat.PKCS8,
                                        encryption_algorithm=serialization.NoEncryption()))
    key_fd.flush()
    cert_fd.close(); key_fd.close()
    return cert_fd.name, key_fd.name


def download_nfse_with_session(session: requests.Session, url_base: str, data_inicio: str, data_fim: str, pasta_destino: str):
    from urllib.parse import quote
    di = data_inicio.replace('-', '/')
    df = data_fim.replace('-', '/')
    url_busca = f"{url_base}?executar=1&busca=&datainicio={quote(di)}&datafim={quote(df)}"
    resp = session.get(url_busca, timeout=30, verify=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'lxml')
    links = []
    for a in soup.find_all('a', href=True):
        if '/Notas/Download/DANFSe/' in a['href']:
            numero = a['href'].split('/')[-1]
            links.append((numero, f"https://www.nfse.gov.br{a['href']}"))
    os.makedirs(pasta_destino, exist_ok=True)
    downloaded = []
    for numero, link in links:
        r = session.get(link, timeout=30, verify=True)
        if r.status_code == 200:
            ext = '.pdf' if 'pdf' in r.headers.get('Content-Type','') else '.xml'
            path = os.path.join(pasta_destino, f"{numero}{ext}")
            with open(path, 'wb') as f:
                f.write(r.content)
            downloaded.append(path)
    return downloaded


def upload_files_to_server(server_url: str, api_token: str, empresa_id: int, tipo: str, files: list):
    url = server_url.rstrip('/') + '/api/agent/upload/'
    headers = {'Authorization': f'Token {api_token}'}
    data = {'empresa': str(empresa_id), 'tipo': tipo}
    multipart = [('files', (os.path.basename(p), open(p, 'rb'))) for p in files]
    resp = requests.post(url, headers=headers, data=data, files=multipart)
    resp.raise_for_status()
    return resp.json()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--thumb', required=True, help='Thumbprint do certificado na máquina local')
    p.add_argument('--server', required=True, help='URL do servidor (ex: http://127.0.0.1:8000)')
    p.add_argument('--token', required=True, help='Token do usuário (perfil)')
    p.add_argument('--empresa', required=True, type=int)
    p.add_argument('--tipo', choices=['emitidas','recebidas'], default='emitidas')
    p.add_argument('--data_inicio', required=True)
    p.add_argument('--data_fim', required=True)
    args = p.parse_args()

    temp_files = []
    try:
        print('Exportando PFX via certutil...')
        pfx = export_pfx_with_certutil(args.thumb)
        temp_files.append(pfx)

        print('Convertendo PFX para PEM...')
        cert_pem, key_pem = pfx_to_pem_pair(pfx)
        temp_files.extend([cert_pem, key_pem])

        session = requests.Session()
        session.cert = (cert_pem, key_pem)
        session.headers.update({'User-Agent': 'Mozilla/5.0'})

        url_base = 'https://www.nfse.gov.br/EmissorNacional/Notas/Emitidas' if args.tipo == 'emitidas' else 'https://www.nfse.gov.br/EmissorNacional/Notas/Recebidas'
        dest = os.path.join(os.getcwd(), 'client_downloads')
        print('Iniciando download local...')
        downloaded = download_nfse_with_session(session, url_base, args.data_inicio, args.data_fim, dest)
        print(f'Download concluído: {len(downloaded)} arquivos')

        if downloaded:
            print('Enviando arquivos para o servidor...')
            res = upload_files_to_server(args.server, args.token, args.empresa, args.tipo, downloaded)
            print('Envio concluído:', res)
        else:
            print('Nenhum arquivo encontrado para o período informado.')

    except subprocess.CalledProcessError as cpe:
        print('Erro ao exportar certificado via certutil:', cpe)
    except Exception as e:
        print('Erro:', e)
    finally:
        # cleanup
        for f in temp_files:
            try:
                os.remove(f)
            except Exception:
                pass


if __name__ == '__main__':
    main()
