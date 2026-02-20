<#
Script para subir Postgres via Docker Compose e executar bootstrap do Django
Uso: execute este script em PowerShell (executar como administrador se necessário).
Certifique-se de ter o Docker Desktop instalado antes de rodar.
#>

param(
    [string]$EnvFile = ".env",
    [int]$Retries = 20,
    [int]$DelaySec = 3
)

Set-Location -Path (Resolve-Path "$(Split-Path -Parent $MyInvocation.MyCommand.Definition)") | Out-Null
Set-Location ..

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker não encontrado. Instale o Docker Desktop e tente novamente."
    exit 1
}

Write-Host "Subindo containers com docker compose..."
docker compose up -d

Write-Host "Aguardando o Postgres ficar disponível (tentando migrations)..."
$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

for ($i = 0; $i -lt $Retries; $i++) {
    try {
        & $python manage.py migrate --settings=nfse_downloader.settings_prod --noinput
        Write-Host "Migrations executadas com sucesso."
        break
    } catch {
        Write-Host "Tentativa $($i+1)/$Retries: Postgres ainda indisponível. Aguardando $DelaySec segundos..."
        Start-Sleep -Seconds $DelaySec
    }
}

if ($i -ge $Retries) {
    Write-Error "Postgres não ficou pronto após $Retries tentativas. Verifique os containers e logs do Docker."
    exit 1
}

Write-Host "Executando bootstrap: setup_prod e criação de superuser 'Sferna123'..."
& $python manage.py setup_prod
& $python manage.py create_prod_superuser --username Sferna123 --email sferna@example.com

Write-Host "Concluído. Se desejar iniciar o servidor de desenvolvimento para produção (não recomendado em produção real), execute:"
Write-Host "    .\.venv\Scripts\python.exe manage.py runprodserver"
