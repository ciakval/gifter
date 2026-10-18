# Deploying Gifter

Short operating manual for future-you. The infrastructure conventions come from the
`bombur-infra` skill; the reference app is `~/GIT/plachtis`.

## Overview

| Thing | Value |
|---|---|
| Domain | https://gifter.remesh.cz (CNAME to `bombur.remesh.cz`) |
| Deploy dir on Bombur | `/home/plachtis/DOCKER/gifter` (default deploy user `plachtis`; the same path appears in `.github/workflows/deploy.yml`) |
| Container | `gifter-web`, listens on port 8000, joined to the external `proxy` network (no published host ports) |
| Image | `ghcr.io/ciakval/gifter` (the repo is private, so the package is private) |
| Data | `./data` next to `compose.yaml` (`db.sqlite3` plus `-wal` and `-shm`), bind-mounted at `/app/data` |
| Pipeline | push to `main` -> test -> build and push to GHCR -> deploy over SSH |

CI pulls the image with the job's `GITHUB_TOKEN`. A manual `docker compose pull` on the
server needs `docker login ghcr.io` with a personal access token that has `read:packages`.

## Local development

```sh
uv sync
# Create a gitignored .env in the repo root with at least:
#   DEBUG=1
#   GOOGLE_CLIENT_ID=<the DEV client id>
#   GOOGLE_CLIENT_SECRET=<the DEV client secret>
DEBUG=1 uv run python manage.py migrate
uv run python manage.py runserver 127.0.0.1:8000
```

Always browse via `http://127.0.0.1:8000/` (never the machine name): that is the redirect
URI registered for the dev Google client.

- Tests: `DEBUG=1 uv run python manage.py test`
- Production image check (build, run behind a simulated proxy, restart on the same data):
  `bash scripts/container-smoke.sh`
- Live check of a running site: `bash scripts/smoke.sh https://gifter.remesh.cz`

## One-time setup (in this order)

Order matters: Let's Encrypt needs DNS first, the Google redirect URI needs the domain,
and the first push needs the GitHub secrets.

### 1. DNS

Create a CNAME record `gifter.remesh.cz` -> `bombur.remesh.cz`.

### 2. Deploy user, directory and `.env`

```sh
ssh -p 10022 plachtis@bombur.remesh.cz     # plachtis is the default; use another deploy user if you prefer
id -u                                      # must print 1000 (the container runs as uid 1000)
mkdir -p ~/DOCKER/gifter/data && cd ~/DOCKER/gifter
```

If `id -u` is not 1000, the container cannot write the SQLite files; fix it once:

```sh
sudo chown 1000:1000 ~/DOCKER/gifter/data
```

Create `.env` from `.env.example` in the repo (copy the file contents, or `scp` it):

```sh
nano .env                    # fill SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET (see step 6)
openssl rand -base64 48      # value for SECRET_KEY
chmod 600 .env
```

Never use Django's own key generator for `SECRET_KEY` (its alphabet contains `$`, which
Compose may interpolate). Never reuse the old key that is in the git history.

### 3. Deploy key

```sh
ssh-keygen -t ed25519 -f gifter-deploy -N ''
# append the public key to the deploy user's authorized_keys on Bombur:
ssh -p 10022 plachtis@bombur.remesh.cz 'cat >> ~/.ssh/authorized_keys' < gifter-deploy.pub
```

### 4. GitHub secrets

```sh
gh secret set VPS_HOST --body bombur.remesh.cz
gh secret set VPS_SSH_PORT --body 10022
gh secret set VPS_USER --body plachtis
gh secret set VPS_SSH_KEY < gifter-deploy
rm gifter-deploy gifter-deploy.pub          # delete the local copies once the secret is set
```

### 5. Caddy (as `ciakval`; shared by every site on Bombur, so confirm before editing)

Add this block to `/home/ciakval/DOCKER/web/Caddyfile`:

```caddy
gifter.remesh.cz {
	reverse_proxy gifter-web:8000
}
```

Then validate and reload without touching the other sites:

```sh
docker exec caddy caddy validate --config /etc/caddy/Caddyfile
docker exec caddy caddy reload --config /etc/caddy/Caddyfile
```

The Caddyfile is a single-file bind mount. If `docker exec caddy cat /etc/caddy/Caddyfile`
does not show your edit (the editor wrote a new inode), restart the caddy compose project
in `~/DOCKER/web` instead (a brief blip for all sites). A 502 before the first deploy is
expected: the upstream container does not exist yet.

### 6. Google Cloud Console

1. Create a fresh project named "Gifter" (publishing is per project; do not reuse another app's).
2. OAuth consent screen (now called Google Auth Platform): user type **External**, app name
   and support email, scopes **only** `openid`, `email`, `profile`.
3. **Publish app** so the publishing status reads **In production**. In Testing mode only
   listed test users (max 100) can sign in; relatives would be locked out. With basic scopes
   only, publishing needs no Google verification.
4. Create an OAuth client of type **Web application** (production) with the authorized
   redirect URI exactly:

   `https://gifter.remesh.cz/accounts/google/login/callback/`

   (https, trailing slash; JavaScript origins are not needed).
5. Create a second Web application client for local development with the redirect URI
   `http://127.0.0.1:8000/accounts/google/login/callback/`.
6. Put the production client id and secret into the server `.env`
   (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`); the dev pair goes into your local `.env`.

### 7. First deploy

Push `main` and watch the Actions run (`gh run watch`). Then:

```sh
bash scripts/smoke.sh https://gifter.remesh.cz
```

Sign in with your own Google account, then make yourself staff (see Day-2).

## Deploys and rollback

- Every push to `main` runs test -> build -> deploy. Tests, `makemigrations --check` and
  `check --deploy --fail-level WARNING` must pass before an image is built.
- Re-run manually: `gh workflow run deploy.yml --ref main`.
- Rollback: set `IMAGE_TAG` in the server `.env` to an older commit SHA, then
  `docker compose up -d` in the deploy dir. Images from the last 72 hours are kept.
- Every deploy log starts with a listing of `./data`, so you can see that the database
  from earlier deploys is still there.

## Day-2 operations

```sh
ssh -p 10022 plachtis@bombur.remesh.cz && cd ~/DOCKER/gifter
docker compose ps
docker compose logs -f
docker compose restart
docker exec -ti gifter-web sh                          # shell in the container
```

Make yourself staff after your first Google sign-in (there are no passwords, so there is
no `createsuperuser`):

```sh
docker exec -ti gifter-web python manage.py promote_staff you@example.com
```

The admin lives at `/gifter-admin/` (its own login redirects to Google sign-in).

## Rules and gotchas

- Never tear the compose project down before `up`, and never prune anything but images:
  Bombur is a shared host (other apps live there).
- Caddy only proxies; WhiteNoise serves the static files from the app.
- **Never add a "Social application" row in the Django admin.** The Google credentials come
  from settings (environment); having a database row as well breaks sign-in.
- Rotating `SECRET_KEY` signs everyone out.
- HSTS starts at 3600 s (`SECURE_HSTS_SECONDS`); raise it after a week of working HTTPS.
- Backups of `./data` are planned for Phase 4. Until then, copy all three SQLite files
  (`db.sqlite3`, `-wal`, `-shm`) together, or use `sqlite3 db.sqlite3 ".backup copy.sqlite3"`.
