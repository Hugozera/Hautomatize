import os
import re
import sys
from typing import List, Dict

# Garantir que o diretório do repositório esteja no sys.path para importar o pacote `core`
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import conversor_service


def parse_ofx_simple(ofx_path: str) -> List[Dict]:
    """Parse minimal OFX STMTTRN blocks into list of transactions."""
    txs = []
    try:
        with open(ofx_path, 'r', encoding='utf-8', errors='ignore') as f:
            data = f.read()
    except Exception:
        return txs

    blocks = re.findall(r'<STMTTRN>(.*?)</STMTTRN>', data, flags=re.DOTALL | re.IGNORECASE)
    for blk in blocks:
        tx = {}
        def tag(name):
            m = re.search(rf'<{name}>([^<\r\n]+)', blk, flags=re.IGNORECASE)
            return m.group(1).strip() if m else ''

        tx['tipo'] = tag('TRNTYPE')
        tx['data'] = tag('DTPOSTED')
        trnamt = tag('TRNAMT').replace('.', '').replace(',', '.')
        try:
            tx['valor'] = float(trnamt)
        except Exception:
            try:
                tx['valor'] = float(trnamt.replace(',', '.'))
            except Exception:
                tx['valor'] = 0.0

        tx['fitid'] = tag('FITID')
        tx['checknum'] = tag('CHECKNUM')
        tx['descricao'] = tag('MEMO')
        txs.append(tx)

    return txs


def compare_transactions(txt_txs: List[Dict], ofx_txs: List[Dict]) -> Dict:
    """Compare two lists of transactions; return summary dict."""
    summary = {
        'txt_count': len(txt_txs),
        'ofx_count': len(ofx_txs),
        'matches': 0,
        'mismatches': []
    }

    # Build index of OFX by (date, rounded valor, first 12 chars of desc) and by fitid
    ofx_index = {}
    for o in ofx_txs:
        key = (o.get('data', ''), round(o.get('valor', 0.0), 2), (o.get('descricao') or '')[:12].upper())
        ofx_index.setdefault(key, []).append(o)
        if o.get('fitid'):
            ofx_index.setdefault(('FITID', o.get('fitid')), []).append(o)

    for t in txt_txs:
        key = (t.get('data', ''), round(t.get('valor', 0.0), 2), (t.get('descricao') or '')[:12].upper())
        found = False
        if ('FITID', t.get('fitid')) in ofx_index:
            found = True
        elif key in ofx_index:
            found = True

        if found:
            summary['matches'] += 1
        else:
            summary['mismatches'].append(t)

    return summary


def run(folder: str = 'PDFS', output_dir: str = None, usar_ocr: bool = False, dpi: int = 300):
    cwd = os.getcwd()
    folder_path = os.path.join(cwd, folder)
    if not os.path.exists(folder_path):
        print(f"Pasta não encontrada: {folder_path}")
        return

    if not output_dir:
        output_dir = os.path.join(folder_path, 'convertidos')
    os.makedirs(output_dir, exist_ok=True)

    resultados = conversor_service.processar_pasta(folder_path, formato_destino='ofx', output_dir=output_dir, usar_ocr=usar_ocr, dpi=dpi)

    rel_report = []
    for nome, resultado, erro in resultados:
        nome_base = os.path.splitext(nome)[0]
        ofx_path = resultado if resultado and resultado.lower().endswith('.ofx') else None
        txt_universal = os.path.join(output_dir, f"{nome_base}_texto_universal.txt")

        print(f"Arquivo: {nome}")
        if erro:
            print(f"  Erro: {erro}")

        if not ofx_path or not os.path.exists(ofx_path):
            print("  OFX não gerado.")
            rel_report.append((nome, False, 'OFX não gerado', None))
            continue

        ofx_txs = parse_ofx_simple(ofx_path)

        texto = ''
        if os.path.exists(txt_universal):
            with open(txt_universal, 'r', encoding='utf-8', errors='ignore') as f:
                texto = f.read()
        else:
            # fallback: find original converted txt
            txt_fallback = os.path.join(output_dir, f"{nome_base}.txt")
            if os.path.exists(txt_fallback):
                with open(txt_fallback, 'r', encoding='utf-8', errors='ignore') as f:
                    texto = f.read()

        texto_limpo = conversor_service.ConversorService._limpar_texto_corrompido_hibrido(texto, 'CAIXA')
        texto_limpo = conversor_service.ConversorService._corrigir_espacos_e_caracteres(texto_limpo)
        txt_txs = conversor_service.ConversorService.extrair_transacoes_avancado(texto_limpo)

        summary = compare_transactions(txt_txs, ofx_txs)

        ok = (summary['txt_count'] == summary['ofx_count'] == summary['matches'])

        print(f"  TXT transações: {summary['txt_count']}; OFX transações: {summary['ofx_count']}; Matches: {summary['matches']}")
        if not ok:
            print(f"  Mismatches: {len(summary['mismatches'])}")
        else:
            print("  OK: OFX bate com TXT (counts e correspondências).")

        rel_report.append((nome, ok, None, summary))

    # Salvar relatório simples
    rpt_path = os.path.join(output_dir, 'relatorio_ofx_check.csv')
    try:
        import csv
        with open(rpt_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['arquivo', 'ok', 'erro', 'txt_count', 'ofx_count', 'matches'])
            for item in rel_report:
                nome, ok, erro, summary = item
                if summary:
                    writer.writerow([nome, ok, erro or '', summary.get('txt_count', 0), summary.get('ofx_count', 0), summary.get('matches', 0)])
                else:
                    writer.writerow([nome, ok, erro or '', '', '', ''])
        print(f"Relatório salvo: {rpt_path}")
    except Exception as e:
        print(f"Falha ao salvar relatório: {e}")


if __name__ == '__main__':
    folder = sys.argv[1] if len(sys.argv) > 1 else 'PDFS'
    usar_ocr = False
    if len(sys.argv) > 2 and sys.argv[2].lower() in ('1', 'true', 'ocr'):
        usar_ocr = True
    run(folder=folder, usar_ocr=usar_ocr)
