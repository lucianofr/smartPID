# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: build the React/Vite SPA (packages/smart_pid_web).
# Node 20 matches .github/workflows/ci.yml's pinned toolchain.
# ---------------------------------------------------------------------------
FROM node:25-slim AS web-builder

WORKDIR /web

COPY packages/smart_pid_web/package.json packages/smart_pid_web/package-lock.json ./
RUN npm ci

COPY packages/smart_pid_web/ ./

# Single-origin production build: the backend mounts its routers at root
# (no /api prefix — see app.py), so the SPA must call them unprefixed too.
# Empty string keeps dev (vite.config.ts's server.proxy) and `vite preview`
# on the default '/api' + rewrite behaviour; only this production build
# flips it. See client.ts's VITE_API_BASE fallback.
ENV VITE_API_BASE=""

# `npm run build` runs `tsc -b && vite build`. tsc -b previously failed on a
# clean `npm ci` here (missing @types/node devDependency, fixed upstream in
# package.json — see the deploy report's defect timeline); the canonical
# build script is used as-is now that the fix has landed.
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: install the backend daemon with uv (workspace-aware, frozen lock)
# and serve the SPA built above. This stage IS the runtime image.
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS runtime

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Only the uv workspace members needed to run the daemon: the root workspace
# manifest/lock, smart_pid_domain, and smart_pid_core. smart_pid_web is
# excluded from the uv workspace (see pyproject.toml) and is npm-managed —
# its build output is copied in separately below, never its source.
COPY pyproject.toml uv.lock ./
COPY packages/smart_pid_domain packages/smart_pid_domain
COPY packages/smart_pid_core packages/smart_pid_core

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy

# --frozen: install exactly what uv.lock pins, no re-resolution.
# --no-dev: skip the workspace's [dependency-groups] dev group (pytest, ruff,
# mypy, httpx) — none of it is imported by the running daemon.
# --package smart-pid-core: the root pyproject.toml is a virtual workspace
# root with no dependencies of its own, so a plain `uv sync` resolves
# nothing to install; naming the package pulls it in plus its workspace
# dependency (smart-pid-domain, via [tool.uv.sources]) and installs the
# `smart-pid-core` console script into .venv/bin.
RUN uv sync --frozen --no-dev --package smart-pid-core

COPY --from=web-builder /web/dist ./web/dist

ENV PATH="/app/.venv/bin:${PATH}"

# Non-root: create the user and pre-create /data owned by it. Docker
# populates a fresh named volume from the image's mount-point content on
# first run (ownership included), so mounting the (empty) /data volume here
# lands it owned by appuser without an entrypoint chown step.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

# Persistence contract of the image: every mutable path lives under /data,
# the volume mount point above. Unset, these default to $HOME/.smart-pid
# and ./project.spid — both inside the container's writable layer, which a
# redeploy discards. Declaring them here means any compose/k8s/`docker run`
# that mounts a volume at /data keeps its data, instead of each deployment
# file having to remember all five (docker-compose.vps.yml remembered none).
# A compose `environment:` block still overrides these.
ENV SPID_DB_PATH=/data/project.spid \
    SPID_USERS_DB_PATH=/data/users.db \
    SPID_PROJECTS_DIR=/data/projects \
    SPID_DAEMON_STATE_PATH=/data/daemon_state.json \
    SPID_LOG_DIR=/data/logs

USER appuser

EXPOSE 8000

CMD ["smart-pid-core"]
