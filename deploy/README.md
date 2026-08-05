# smartPID VPS deployment

Single Docker container on `76.13.172.133`, published on host port `8032`,
built and run via `docker-compose.vps.yml` at the repo root. The image is
built directly on the VPS from a synced copy of this working tree — there is
no registry push and no `git clone` on the VPS (no deploy key there).

## Layout on the VPS

- Source: `/opt/smartpid` (rsynced working tree, built there with `docker
  compose build`).
- Runtime env: `/opt/smartpid/.env`, mode `0600`, never committed to git.
- Persisted data: named Docker volume `smartpid-data`, mounted at `/data`
  inside the container — holds `project.spid`, `users.db`, and the
  `projects/` directory. `docker volume inspect smartpid-data` shows the
  physical path on the VPS host filesystem
  (`/var/lib/docker/volumes/smartpid-data/_data`).
- Container: name `smartpid`, image `smartpid:latest`, restart policy
  `unless-stopped`, port mapping `0.0.0.0:8032->8000/tcp`. Runs as non-root
  `appuser` (uid 1000) — see the Dockerfile.

## First-time deploy

```bash
# From the local working tree, on a clean synced `main`:
rsync -az --delete \
  --exclude=.git --exclude=node_modules --exclude=.venv \
  --exclude=dist --exclude=__pycache__ --exclude='*.spid' \
  ./ root@76.13.172.133:/opt/smartpid/

# On the VPS: write the runtime .env once (mode 0600), then build and start.
ssh root@76.13.172.133
cd /opt/smartpid
# .env is authored separately (see "Runtime .env" below) — never rsynced.
docker compose -f docker-compose.vps.yml build
docker compose -f docker-compose.vps.yml up -d
docker compose logs --tail=50 smartpid
```

## Redeploy (code change on `main`)

```bash
# Local:
rsync -az --delete \
  --exclude=.git --exclude=node_modules --exclude=.venv \
  --exclude=dist --exclude=__pycache__ --exclude='*.spid' \
  ./ root@76.13.172.133:/opt/smartpid/

# VPS:
ssh root@76.13.172.133 'cd /opt/smartpid && docker compose -f docker-compose.vps.yml build && docker compose -f docker-compose.vps.yml up -d'
```

`docker compose up -d` recreates the `smartpid` container against the new
image while leaving the `smartpid-data` volume untouched — users, projects,
and process history all survive a redeploy. The `.env` file is never touched
by rsync (excluded via `.dockerignore` from the build context and never part
of the source tree), so an existing deployment's secret and host config
survive redeploys unless deliberately edited.

## Runtime `.env` (`/opt/smartpid/.env`, mode 0600)

Required keys (values are deployment-specific; `SPID_JWT_SECRET` must be a
fresh secret per deployment — see `.env.example` at the repo root for the
full field reference):

```
SPID_JWT_SECRET=<openssl rand -hex 32>
SPID_API_HOST=0.0.0.0
SPID_API_PORT=8000
SPID_TRUSTED_HOSTS=["76.13.172.133","localhost","127.0.0.1"]
SPID_ALLOWED_WS_ORIGINS=["http://76.13.172.133:8032"]
SPID_CORS_ALLOW_ORIGINS=["http://76.13.172.133:8032"]
SPID_DB_PATH=/data/project.spid
SPID_USERS_DB_PATH=/data/users.db
SPID_PROJECTS_DIR=/data/projects
SPID_WEB_DIST_DIR=/app/web/dist
SPID_LOG_LEVEL=INFO
```

`SPID_WEB_DIST_DIR=/app/web/dist` matches where the Dockerfile's `runtime`
stage copies the built SPA (`COPY --from=web-builder /web/dist ./web/dist`
under `WORKDIR /app`).

## Rotating the JWT secret

```bash
ssh root@76.13.172.133 "openssl rand -hex 32"
# paste the result into SPID_JWT_SECRET in /opt/smartpid/.env, then:
ssh root@76.13.172.133 'cd /opt/smartpid && docker compose -f docker-compose.vps.yml up -d'
```

All existing sessions are invalidated (tokens are HMAC-signed with the old
secret); users must log in again.

## Verifying a deploy

```bash
docker ps --filter name=smartpid
docker logs smartpid --tail=100
curl -sS -o /dev/null -w '%{http_code}\n' http://76.13.172.133:8032/system/status
curl -sS http://76.13.172.133:8032/ | head -c 200
```

## Rollback

There is no registry, so rollback means rebuilding a prior commit:

```bash
ssh root@76.13.172.133
cd /opt/smartpid
git -C /path/to/local/checkout ... # N/A — /opt/smartpid is not a git checkout
```

Because `/opt/smartpid` is a plain rsynced copy (not a git checkout — no
deploy key on the VPS), rollback is: from the local working tree, `git
checkout <previous-good-sha>`, rsync as above, then `docker compose -f
docker-compose.vps.yml build && docker compose -f docker-compose.vps.yml up -d`
on the VPS. The `smartpid-data` volume is untouched by
any of this, so rollback does not lose users or projects.
