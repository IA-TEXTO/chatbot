#!/bin/sh
set -eu

: "${DEPLOY_PATH:?Defina a variável DEPLOY_PATH com o diretório no servidor.}"
: "${DEPLOY_SHA:?Defina o commit a publicar.}"

cd "$DEPLOY_PATH"
build_archive="chatbot-${DEPLOY_SHA}.tar.gz"

# Valide e extraia antes do build, sem depender do descompressor do Docker.
build_tmp="$(mktemp -d)"
trap 'rm -rf -- "$build_tmp"' EXIT
trap 'exit 1' HUP INT TERM
mkdir "$build_tmp/context"
gzip -dc -- "$build_archive" > "$build_tmp/context.tar"
tar -xf "$build_tmp/context.tar" -C "$build_tmp/context"
rm -- "$build_tmp/context.tar"

compose() {
  sudo -n docker compose -f docker-compose.prod.yaml "$@"
}

sudo -n docker network inspect proxy >/dev/null
compose config --quiet
sudo -n docker build --file "$build_tmp/context/prod.Dockerfile" \
  --tag chatbot-integracar:latest \
  --label "org.opencontainers.image.revision=$DEPLOY_SHA" "$build_tmp/context"
rm -rf -- "$build_tmp"
rm -- "$build_archive"

compose run --rm --no-deps chatbot-integracar python manage.py check --deploy --fail-level ERROR
compose up --wait --wait-timeout 120 db redeneuralbert

# /start aplica migrations e coleta estáticos antes de iniciar o Gunicorn.
# Pare os consumidores antigos antes de permitir alterações no banco.
compose stop qcluster chatbot-integracar
if ! compose up --no-deps --no-build --wait --wait-timeout 180 chatbot-integracar; then
  compose logs --tail=100 chatbot-integracar qcluster
  exit 1
fi
if ! compose up --no-deps --no-build --wait --wait-timeout 120 qcluster; then
  compose logs --tail=100 chatbot-integracar qcluster
  exit 1
fi
compose ps
