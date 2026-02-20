"""
Production Django settings overrides.

To use: set environment variable `DJANGO_SETTINGS_MODULE=nfse_downloader.settings_prod`
and provide a `.env` file with the DB and secret values (see `.env.production.example`).
"""
from .settings import *  # noqa: F401,F403
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(env_path)

DEBUG = False

# ALLOWED_HOSTS from comma-separated env var, default empty list
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',') if os.getenv('ALLOWED_HOSTS') else []

# Secret key must be set in production env
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', SECRET_KEY)

# Database: default to Postgres in production; configure via env vars
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DB_NAME', 'nfse_prod'),
        'USER': os.getenv('DB_USER', 'nfse_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Static/media should be served by the webserver in production
STATIC_ROOT = os.getenv('STATIC_ROOT', str(BASE_DIR / 'staticfiles'))
MEDIA_ROOT = os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media'))
