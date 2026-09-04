# syntax=docker/dockerfile:1

# Stage 1: Build the Python application using uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS python-builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /code

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY . .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Stage 2: Build the frontend files
FROM node:22-bookworm-slim AS node-builder
WORKDIR /code

# Esta camada só é invalidada quando os manifests mudam. O cache do BuildKit
# evita baixar novamente os mesmos pacotes entre deploys.
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --no-audit --no-fund

COPY . .
RUN npm run build


# Stage 3: Final image
FROM python:3.12-slim-bookworm

ENV PATH="/code/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV DEBUG=0
ENV DJANGO_SETTINGS_MODULE=core.settings_production

RUN apt-get update \
    && apt-get install -y curl libpq-dev \
    && apt-get purge -y --auto-remove \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY --from=python-builder /code /code
COPY --from=node-builder /code/frontend/dist /code/frontend/dist
COPY . /code

RUN mkdir -p media logs static

COPY docker_startup.sh /start
RUN chmod +x /start

CMD ["/start"]
