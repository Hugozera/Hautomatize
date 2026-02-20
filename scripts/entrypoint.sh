#!/usr/bin/env bash
set -e

# default settings module may already be set by Dockerfile or compose
if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
  export DJANGO_SETTINGS_MODULE=nfse_downloader.settings_prod
fi

echo "Entrypoint: usando settings $DJANGO_SETTINGS_MODULE"

# wait for DB to be ready (simple loop)
echo "Aguardando banco de dados ficar pronto..."
retries=0
until python -c "import django; from django.db import connections; connections['default'].cursor();" >/dev/null 2>&1; do
  retries=$((retries+1))
  if [ $retries -gt 30 ]; then
    echo "Banco não ficou pronto após várias tentativas" >&2
    break
  fi
  sleep 2
done

echo "Executando migrations..."
python manage.py migrate --noinput

echo "Coletando static files..."
python manage.py collectstatic --noinput

# Optional: create production superuser if env var provided
if [ ! -z "$CREATE_PROD_SUPERUSER" ] && [ ! -z "$PROD_SUPERUSER_USERNAME" ]; then
  echo "Criando/atualizando superuser $PROD_SUPERUSER_USERNAME..."
  if [ ! -z "$PROD_SUPERUSER_PASSWORD" ]; then
    python manage.py create_prod_superuser --username "$PROD_SUPERUSER_USERNAME" --email "${PROD_SUPERUSER_EMAIL:-}" --password "$PROD_SUPERUSER_PASSWORD"
  else
    python manage.py create_prod_superuser --username "$PROD_SUPERUSER_USERNAME" --email "${PROD_SUPERUSER_EMAIL:-}"
  fi
fi

echo "Executando comando final: $@"
exec "$@"
