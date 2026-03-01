# PowerShell helper to run MVP locally (development)
Write-Host "Installing (if needed) and starting MVP..."
python -m pip install -r requirements.txt
python -m pip install channels uvicorn daphne
python manage.py migrate
if (-not (Test-Path env:USERNAME)) { }
Write-Host "Create a superuser if you haven't yet: python manage.py createsuperuser"
Write-Host "Starting ASGI server (uvicorn nfse_downloader.asgi:application)"
uvicorn nfse_downloader.asgi:application --reload
