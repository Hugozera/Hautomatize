FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    openssl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# install pip requirements
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /app/requirements.txt

# copy project
COPY . /app

# make entrypoint executable
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENV DJANGO_SETTINGS_MODULE=nfse_downloader.settings_prod

CMD ["/app/entrypoint.sh", "gunicorn", "nfse_downloader.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
