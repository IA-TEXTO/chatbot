#!/bin/sh
set -eu

: "${DEPLOY_SHA:?Defina o commit a publicar.}"

# Lista explícita: somente fontes do build, sem .env, mídia ou dados locais.
git archive --format=tar.gz --output="chatbot-${DEPLOY_SHA}.tar.gz" "$DEPLOY_SHA" \
  prod.Dockerfile .dockerignore pyproject.toml uv.lock manage.py README.md \
  package.json package-lock.json tailwind.config.js tsconfig.json vite.config.js \
  docker_startup.sh apps core frontend
gzip -t -- "chatbot-${DEPLOY_SHA}.tar.gz"
