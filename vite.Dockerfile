# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS base

WORKDIR /app

# Dependências ficam em uma camada própria e só são reinstaladas quando os
# manifests mudam. O cache do npm é preservado pelo BuildKit entre builds.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

# O código-fonte muda com frequência e deve ser copiado depois das dependências.
COPY . .
