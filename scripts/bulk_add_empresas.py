"""Utility script to bulk-create Empresas from a list of CNPJs/CPFs.

This script can be run from the workspace root with the virtualenv active:

    python scripts/bulk_add_empresas.py

It uses the same helper functions as the web UI (consulta BrasilAPI, Receita etc.)
and writes to the database via Django's ORM.  No login or CSRF tokens are required.

Change the ``cpns`` list below or load from a file if desired.
"""

import os
import sys
import django
import re

# ensure project root is on sys.path (in case script is invoked from elsewhere)
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)

# bootstrap Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nfse_downloader.settings')
try:
    django.setup()
except ModuleNotFoundError as e:
    print('Failed to import Django or project settings. Are you using the virtualenv?')
    print('Error:', e)
    sys.exit(1)
except Exception as e:
    print('failed to configure Django:', e)
    sys.exit(1)

from core.models import Empresa
from core.views import consultar_cnpj_receita

# raw CNPJs/CPFs obtained from the user request
cpns_raw = [
    "30.250.868/0001-00",
    "11.502.112/0001-67",
    "62.753.355/0001-09",
    "37.665.991/0001-31",
    "37.665.991/0002-12",
    "21.082.444/0001-93",
    "21.082.444/0002-74",
    "21.082.444/0003-55",
    "22.154.330/0001-74",
    "08.932.753/0001-47",
    "21.784.054/0001-65",
    "24.786.703/0001-55",
    "35.723.176/0001-56",
    "35.723.176/0002-37",
    "05.321.529/0001-20",
    "10.777.413/0001-30",
    "43.292.670/0001-31",
    "36.124.903/0001-21",
    "11.129.196/0001-35",
    "44.573.454/0001-27",
    "05.064.736/0001-47",
    "01.457.452/0001-60",
    "41.173.706/0001-32",
    "24.378.390/0001-04",
    "60.796.517/0001-60",
    "26.992.662/0001-89",
    "26.992.662/0002-60",
    "03.054.393/0001-04",
    "43.683.464/0001-52",
    "61.062.695/0001-20",
    "52.687.564/0001-48",
    "29.808.801/0001-60",
    "29.808.801/0002-40",
    "29.808.801/0003-21",
    "66.418.849/0001-98",
    "66.418.849/0002-79",
    "04.286.217/0001-60",
    "37.284.307/0001-71",
    "07.404.760/0001-03",
    "07.404.760/0002-94",
    "07.404.760/0003-75",
    "07.404.760/0004-56",
    "07.404.760/0005-37",
    "12.498.535/0001-13",
    "12.498.535/0002-02",
    "45.463.464/0001-72",
    "03.746.920/0001-41",
    "84.042.027/0001-37",
    "84.042.027/0004-80",
    "28.563.090/0001-48",
    "47.734.859/0001-98",
    "47.468.096/0001-80",
    "38.475.820/0001-02",
    "51.756.427/0001-55",
    "27.960.067/0001-24",
    "38.100.816/0001-60",
    "62.957.035/0001-70",
    "41.739.998/0001-28",
    "26.439.067/0001-10",
    "43.581.307/0001-36",
    "08.463.473/0001-37",
    "37.219.867/0001-42",
    "22.901.396/0001-80",
    "13.052.523/0001-23",
    "45.239.883/0001-25",
    "45.239.883/0002-06",
    "33.659.604/0001-01",
    "22.183.946/0001-73",
    "48.821.740/0001-15",
    "24.566.206/0001-41",
    "55.490.350/0001-75",
    "69.555.175/0001-61",
    "20.014.798/0001-38",
    "20.014.798/0002-19",
    "890.322.761-15",
    "14.040.300/0001-09",
    "54.748.370/0001-30",
    "09.416.557/0001-82",
    "63.293.821/0001-83",
    "51.740.096/0001-65",
    "61.326.731/0001-16",
    "51.030.665/0001-89",
    "07.823.856/0001-06",
    "13.159.448/0001-02",
    "13.159.448/0002-85",
    "13.159.448/0003-66",
    "62.031.474/0001-58",
    "15.097.658/0001-30",
    "11.734.842/0001-93",
    "40.401.197/0001-95",
    "08.366.044/0001-41",
    "69.558.401/0001-68",
    "21.363.830/0001-53",
    "21.195.558/0002-20",
    "21.195.558/0001-40",
    "23.672.509/0001-86",
    "46.374.699/0001-50",
    "20.116.303/0001-81",
    "20.116.303/0002-62",
    "59.426.823/0001-26",
    "44.597.244/0001-79",
    "43.151.427/0001-01",
    "11.352.545/0001-83",
    "46.657.124/0001-45",
    "07.961.413/0001-81",
    "40.689.487/0001-86",
    "41.091.885/0001-69",
    "41.091.885/0002-40",
    "81.435.125/0001-46",
    "04.438.166/0001-45",
    "33.023.826/0001-25",
    "49.824.215/0001-16",
    "55.297.992/0001-52",
    "50.208.617/0001-75",
    "15.024.904/0001-24",
    "15.024.904/0002-05",
    "26.456.995/0001-93",
    "06.188.525/0001-89",
    "86.513.959/0001-46",
    "09.495.338/0001-36",
    "72.076.318/0001-67",
    "18.115.482/0001-90",
    "28.318.325/0001-36",
    "22.691.807/0001-50",
    "14.585.053/0001-26",
    "14.585.053/0002-07",
    "15.941.305/0001-75",
    "22.934.526/0001-81",
    "00.825.364/0001-00",
    "12.966.068/0001-09",
    "12.966.068/0002-90",
    "12.966.068/0003-70",
    "15.910.375/0001-66",
    "72.855.430/0001-04",
    "22.505.044/0001-06",
    "60.979.577/0001-19",
    "38.440.141/0001-06",
    "03.109.768/0001-96",
    "03.109.768/0002-77",
    "03.109.768/0003-58", ]


def normalize(cnpj):
    return re.sub(r"[^0-9]", "", cnpj)


def main():
    failures = []
    for raw in cpns_raw:
        num = normalize(raw)
        if len(num) not in (11, 14):
            print(f"skipping invalid {raw}")
            continue
        obj, created = Empresa.objects.get_or_create(cnpj=num)
        if created or not obj.razao_social:
            dados = consultar_cnpj_receita(num)
            if dados.get('status') == 'OK':
                obj.razao_social = dados.get('nome', '')
                obj.nome_fantasia = dados.get('fantasia', '') or ''
                obj.cep = dados.get('cep', '')
                obj.logradouro = dados.get('logradouro', '')
                obj.numero = dados.get('numero', '')
                obj.bairro = dados.get('bairro', '')
                obj.municipio = dados.get('municipio', '')
                obj.uf = dados.get('uf', '')
                obj.save()
                print(f"created {num} -> {obj.razao_social}")
            else:
                print(f"lookup failed {num}: {dados.get('msg')}")
                failures.append(num)
        else:
            print(f"already exists {num}")
    if failures:
        print("\nFailed lookups:")
        for f in failures:
            print(f)
    # report any identifiers that still aren't in the database
    missing = []
    for raw in cpns_raw:
        num = normalize(raw)
        if not Empresa.objects.filter(cnpj=num).exists():
            missing.append(raw)
    if missing:
        print("\nStill missing (not added):")
        for m in missing:
            print(m)


if __name__ == '__main__':
    main()
