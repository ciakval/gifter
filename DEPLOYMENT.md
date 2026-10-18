# Deploying Gifter

Short operating manual for future-you. The infrastructure conventions come from the
`bombur-infra` skill; the deploy tooling is `ciakval/bombur-deploy` (local clone
`~/GIT/bombur-deploy`, its README is the source of truth).

## Overview

| Thing | Value |
|---|---|
| Domain | https://gifter.remesh.cz (covered by the `*.remesh.cz` wildcard CNAME to `bombur.remesh.cz`, no DNS work) |
| Deploy dir on Bombur | `/home/deploy/DOCKER/gifter` (owned by the `deploy` user) |
| Container | `gifter-web`, listens on port 8000, joined to the external `proxy` network (no published host ports) |
| Server-owned files | `compose.yaml` (sent by `bombur-onboard`, not by CI) and `.env` (secrets by hand, `IMAGE_TAG` by `bombur-deploy`) |
| Image | `ghcr.io/ciakval/gifter` |
| Data | `./data` next to `compose.yaml` (`db.sqlite3` plus `-wal` and `-shm`), bind-mounted at `/app/data` |
| Caddy | `/home/ciakval/DOCKER/web/sites/gifter.caddy`, written by `bombur-add-app` |
| Pipeline | push to `main` -> test -> build and push to GHCR -> reusable `ciakval/bombur-deploy` workflow (`ssh deploy@bombur "deploy <sha>"`) |

CI holds exactly one secret for Bombur: `DEPLOY_SSH_KEY` in the GitHub `production`
environment. It is a per-app key with a forced command, so it can only say "deploy SHA x
of gifter". CI cannot copy files or open a shell on the server.

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

Run `bombur-onboard` only after the deploy files are committed: it sends the working tree's
`compose.yaml` and `.env.example` to the server.

### 1. Protect `main`

Protect `main` on `ciakval/gifter` (at least no force-push, no deletion): Settings ->
Branches, or `gh api`. The `production` environment that `bombur-onboard` creates only
accepts protected branches.

### 2. Google Cloud Console

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
6. The production client id and secret go into the server `.env` (step 4 below); the dev
   pair goes into your local `.env`.

### 3. Onboard the app on Bombur

From the repo root of this checkout:

```sh
~/GIT/bombur-deploy/bin/bombur-onboard gifter 8000
```

This creates `/home/deploy/DOCKER/gifter` with `.env` (from `.env.example`; `SECRET_KEY` is
generated from `CHANGE_ME`) and `data/`, installs the `gh-gifter` forced-command key, adds
`sites/gifter.caddy` and reloads Caddy, creates the GitHub `production` environment and
sets `DEPLOY_SSH_KEY`.

The container runs as uid 1000 and must be able to write `./data`. Check the deploy user:

```sh
ssh -p 10022 ciakval@bombur.remesh.cz 'id -u deploy'
```

If it does not print `1000`, fix it once:

```sh
ssh -p 10022 ciakval@bombur.remesh.cz sudo chown 1000:1000 /home/deploy/DOCKER/gifter/data
```

### 4. Fill the Google credentials

```sh
ssh -p 10022 ciakval@bombur.remesh.cz sudo -u deploy nano /home/deploy/DOCKER/gifter/.env
```

Type `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` there (never into chat, the repo or
GitHub). The app refuses to start while they are empty.

### 5. First deploy

Push `main` and watch the Actions run (`gh run watch`). Caddy answers 502 until the
container exists. Then:

```sh
bash scripts/smoke.sh https://gifter.remesh.cz
```

Sign in with your own Google account, then make yourself staff (see Day-2).

Changing `compose.yaml` later means re-running `bombur-onboard` (it also rotates the key;
`BOMBUR_KEY_ONLY=1 ~/GIT/bombur-deploy/bin/bombur-onboard gifter 8000` rotates only the key).

## Deploys and rollback

- Every push to `main` runs test -> build -> deploy. Tests, `makemigrations --check` and
  `check --deploy --fail-level WARNING` must pass before an image is built.
- Re-run manually: `gh workflow run deploy.yml --ref main`.
- Deploy history on the server (including rejected attempts):
  `ssh -p 10022 ciakval@bombur.remesh.cz sudo journalctl -t bombur-deploy`
- Rollback: re-run an older successful Actions run, or set `IMAGE_TAG` in the server `.env`
  to an older commit SHA and bring the project up as `deploy`:

  ```sh
  sudo -u deploy sh -c 'cd /home/deploy/DOCKER/gifter && docker compose up -d'
  ```

  Images from the last 72 hours are kept on the server.

## Day-2 operations

```sh
ssh -p 10022 ciakval@bombur.remesh.cz
sudo -u deploy sh -c 'cd /home/deploy/DOCKER/gifter && docker compose ps'
sudo -u deploy sh -c 'cd /home/deploy/DOCKER/gifter && docker compose logs -f'
sudo -u deploy sh -c 'cd /home/deploy/DOCKER/gifter && docker compose restart'
docker exec -ti gifter-web sh                          # shell in the container
sudo journalctl -t bombur-deploy                       # deploy history
```

Make yourself staff after your first Google sign-in (there are no passwords, so there is
no `createsuperuser`):

```sh
docker exec -ti gifter-web python manage.py promote_staff you@example.com
```

The admin lives at `/gifter-admin/` (its own login redirects to Google sign-in).

Revoke CI's deploy access: delete the `gh-gifter` line in `/home/deploy/.ssh/authorized_keys`.

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
