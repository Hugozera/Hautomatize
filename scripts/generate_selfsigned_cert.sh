#!/usr/bin/env bash
set -e

OUT_DIR=$(pwd)/certs
mkdir -p "$OUT_DIR"

echo "Gerando certificado self-signed em $OUT_DIR (fullchain.pem, privkey.pem)..."

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$OUT_DIR/privkey.pem" \
  -out "$OUT_DIR/fullchain.pem" \
  -subj "/C=BR/ST=SP/L=City/O=Company/OU=IT/CN=localhost"

echo "Certificado gerado. Copie para produção ou use Let's Encrypt para certificados válidos." 
