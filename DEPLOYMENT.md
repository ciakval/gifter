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
- Translations: after changing user-facing text run
  `DEBUG=1 uv run python manage.py makemessages -l cs --no-obsolete --add-location=file --ignore=staticfiles --ignore=data`,
  translate in `locale/cs/LC_MESSAGES/django.po` (all entries, no fuzzy flags, three plural
  forms), run `DEBUG=1 uv run python manage.py compilemessages -l cs --ignore=.venv`, commit the
  `.po` and the `.mo` together, and check with `bash scripts/check-translations.sh` (CI runs it too).
- The family dry-run kit and the launch order are in `docs/dry-run.md`.

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
3. **Branding** (Google Auth Platform -> Branding). The privacy page must already be live
   (deploy first), because Google checks that the link works. Fill in:
   - App name: `Gifter`
   - User support email: keep yours
   - App logo: leave **empty** (uploading a logo starts Google's brand verification)
   - Application home page: `https://gifter.remesh.cz`
   - Application privacy policy link: `https://gifter.remesh.cz/privacy/`
   - Application terms of service link: leave empty
   - Authorized domain: `remesh.cz`
   - Developer contact email: yours
4. **Publish app** (Audience -> Publish app) so the publishing status reads **In production**.
   In Testing mode only listed test users (max 100) can sign in; relatives would be locked
   out. With basic scopes only and no logo, publishing needs no Google verification.
5. Create an OAuth client of type **Web application** (production) with the authorized
   redirect URI exactly:

   `https://gifter.remesh.cz/accounts/google/login/callback/`

   (https, trailing slash; JavaScript origins are not needed).
6. Create a second Web application client for local development with the redirect URI
   `http://127.0.0.1:8000/accounts/google/login/callback/`.
7. The production client id and secret go into the server `.env` (step 4 below); the dev
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

Optionally add `GIFTER_CONTACT_EMAIL=you@example.org` there too. `/privacy/` then shows it as
the address for data requests (viewing or deleting someone's data). While it is empty, the
page tells people to ask whoever invited them. Never put the address in the repo.

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
- After each deploy the workflow checks `https://gifter.remesh.cz/healthz` and fails the run
  if it does not answer 2xx within about a minute.
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
sudo journalctl -u gifter-backup                       # nightly backup runs
```

Make yourself staff after your first Google sign-in (there are no passwords, so there is
no `createsuperuser`):

```sh
docker exec -ti gifter-web python manage.py promote_staff you@example.com
```

`promote_staff` promotes only the one Google account whose email Google has verified (and
that has a verified email address row for it). It prints that account's Google uid, and
refuses, promoting nobody, for an unknown, unverified, non-Google or ambiguous match. Check the
printed uid against `/gifter-admin/socialaccount/socialaccount/`.

The admin lives at `/gifter-admin/` (its own login redirects to Google sign-in).

### Delete someone's account (data request)

`/privacy/` promises that a person's account and everything Gifter stores about them can be
deleted on request. The admin cannot do it (its deletion summary would show the author claims
on his own wishes), so use `delete_user`. Deleting a person removes their account, wishes,
claims and chip-ins, their comments, the discussions about them and on their wishes (with
everyone's comments in those discussions) and their read receipts. The command's output never
depends on claims or discussions, because the operator is also a giftee:

1. Find the person at `/gifter-admin/gifter/user/` (search by name or email) and note the
   username.
2. Dry run (it shows the account and deletes nothing):

   ```sh
   docker exec -ti gifter-web python manage.py delete_user <username>
   ```

3. Make a pre-deletion copy of the live database (outside the app directory, consistent
   while `gifter-web` runs; see "Backups and restore"). Note the path it prints:

   ```sh
   sudo -u deploy env PREFIX=pre-deletion /usr/local/bin/gifter-backup.sh
   ```

   Then repeat the dry-run command with `--yes`:

   ```sh
   docker exec -ti gifter-web python manage.py delete_user <username> --yes
   ```

   Then VACUUM the live database, so pages freed by the deletion no longer hold the person's
   rows:

   ```sh
   docker exec gifter-web sqlite3 -cmd ".timeout 20000" /app/data/db.sqlite3 "VACUUM;"
   ```

4. Verify: the dry run for the same username now fails with "Nobody was deleted", and
   `bash scripts/smoke.sh https://gifter.remesh.cz` passes. If the check fails, restore from
   the pre-deletion copy:

   ```sh
   sudo -u deploy /usr/local/bin/gifter-restore.sh <copy> --yes
   ```

5. Once the check passes, remove the pre-deletion copy (`sudo -u deploy rm <path printed in
   step 3>`), then any `pre-restore-*` copy made during the request. Reply to the person only
   after this step.

The deletion is final, and cannot be undone, only once the pre-deletion copy is removed: until
then the copy still holds the person's data. The same goes for any copy or backup of the
database made before the deletion: it still holds the person's data until it is
removed or rotated. The nightly backups made before the deletion keep the person's data until they are
deleted, at most 14 days later, as `/privacy/` says; the reply to the person may mention this.
Remove earlier manual copies too, so that the promise in `/privacy/` (the account and
everything Gifter stores about the person is deleted) holds.

Deleting a user also removes their wishes (and any claims on them), their memberships, the
claims they made (including other people's chip-ins on those claims), their own chip-ins and
their Google identity rows. Events they created stay, without a creator. `delete_user`
refuses to delete the last active staff account (promote someone else first), and its output
never depends on claims or chip-ins.

Never delete people from a Django shell or `manage.py shell`: `delete()` echoes per-model
counts, including claims, and the operator is also a giftee.

Revoke CI's deploy access: delete the `gh-gifter` line in `/home/deploy/.ssh/authorized_keys`.

## Backups and restore

What runs: `gifter-backup.timer` starts `gifter-backup.service` every night at 03:15
(Europe/Prague) as the `deploy` user. It runs `/usr/local/bin/gifter-backup.sh`, which takes an
online `sqlite3 .backup` inside the running `gifter-web` container (the app keeps running),
VACUUMs the copy, checks it with `PRAGMA integrity_check` and stores it as
`/home/deploy/backups/gifter/gifter-YYYY-MM-DD-HHMMSS.sqlite3` (directory 700, files 600),
outside the app directory. The 14 newest are kept and anything older than 14 days is deleted,
matching `/privacy/`.

The backups live on the same server. They protect against mistakes, bad deploys and bad
migrations, not against losing the server. That is an accepted risk for this phase.

### One-time install on Bombur

After the image built from this phase is deployed (it carries the `sqlite3` tool), run from the
repo checkout:

```sh
scp -P 10022 scripts/gifter-backup.sh scripts/gifter-restore.sh \
  scripts/systemd/gifter-backup.service scripts/systemd/gifter-backup.timer \
  ciakval@bombur.remesh.cz:/tmp/
ssh -p 10022 ciakval@bombur.remesh.cz '
  sudo install -m 755 /tmp/gifter-backup.sh /tmp/gifter-restore.sh /usr/local/bin/ &&
  sudo install -m 644 /tmp/gifter-backup.service /tmp/gifter-backup.timer /etc/systemd/system/ &&
  sudo systemctl daemon-reload &&
  sudo systemctl enable --now gifter-backup.timer &&
  sudo systemctl start gifter-backup.service &&
  systemctl list-timers gifter-backup.timer --no-pager &&
  sudo journalctl -u gifter-backup -n 5 --no-pager &&
  sudo -u deploy ls -l /home/deploy/backups/gifter'
```

Re-run the same commands after the scripts change.

### The privacy marker

The first successful nightly run writes `/home/deploy/DOCKER/gifter/data/nightly-backups-since`
(the app's `/app/data`), holding that day's date. From then on `/privacy/` says that Gifter is
backed up every night and that nightly backups are deleted after 14 days, and its "Last
updated" date is at least that date. Check it after the install with
`sudo -u deploy docker exec gifter-web cat /app/data/nightly-backups-since` and by opening
https://gifter.remesh.cz/privacy/. Never create or edit the marker by hand, and never copy it
into another environment. If nightly backups are ever stopped for good (timer disabled and not
coming back), delete the marker in the same step so `/privacy/` stops describing them, and ask
Claude to review the policy.

### Checking backups

```sh
systemctl list-timers gifter-backup.timer
sudo journalctl -u gifter-backup -n 20 --no-pager     # expect "BACKUP OK"
sudo -u deploy ls -l /home/deploy/backups/gifter
```

### Restore drill

Safe, never touches production. Do it once before 1 Dec 2026 and after big changes:

```sh
sudo -u deploy /usr/local/bin/gifter-restore.sh --drill /home/deploy/backups/gifter/<newest file>
```

Expect one `DRILL OK ...` line with plausible numbers (users, events and wishes only). It
starts a throwaway container from the live image on a fresh volume, restores into it, waits for
the migrations check and removes container and volume again.

#### Restore drill record

| Date | Backup file | Result line | Done by |
|---|---|---|---|
| not yet run | not yet run | not yet run | |

Replace the row with the real result and ask Claude to record it in STATE.

### Real restore (emergency only)

Dry run first, then `--yes`:

```sh
sudo -u deploy /usr/local/bin/gifter-restore.sh <file>
sudo -u deploy /usr/local/bin/gifter-restore.sh <file> --yes
```

`--yes` saves a safety copy `pre-restore-*.sqlite3` first, restores online into the live
database, restarts the container (the restart applies migrations to an older backup) and waits
until `migrate --check` passes. A corrupt or foreign file is refused and nothing changes.
Afterwards run `bash scripts/smoke.sh https://gifter.remesh.cz` and sign in to check your data,
then delete the safety copy: it keeps the data of anyone deleted since.

### Manual copies

```sh
sudo -u deploy env PREFIX=pre-deletion /usr/local/bin/gifter-backup.sh
```

Use another prefix (lowercase letters and dashes) if you like. Copies with another prefix are
never rotated and never write the marker, so remove them by hand once used.

## Rules and gotchas

- Never tear the compose project down before `up`, and never prune anything but images:
  Bombur is a shared host (other apps live there).
- Caddy only proxies; WhiteNoise serves the static files from the app.
- **The admin offers no "Social applications" or "Social tokens".** The Google credentials
  come from settings (environment); a database row as well would break sign-in. Social
  accounts and Email addresses are view only. Users cannot be deleted in the admin, and the
  user list refuses filters on related rows such as claims, because both would show the
  author claims on his own wishes. People are deleted with `delete_user` (see "Delete
  someone's account"). Wishes, claims and discussions are never in the admin: the author is
  staff and also a giftee.
- Only seven `accounts/` routes exist (Google sign-in, sign-out, cancelled, error and the
  sign-up fallback). A test pins the list; everything else under `accounts/` is 404.
- Rotating `SECRET_KEY` signs everyone out.
- `/privacy/` must stay public and truthful. It now covers Google sign-in data, sign-in times,
  events, memberships and wishes (including the soft delete: Gifter keeps a copy of deleted
  wishes), claims, chip-in notes, and the purchased and received states, and who can see them
  (the person whose wish it is never does). It also lists discussions and comments among
  what it covers: only the other members of the event can read them, and the person a
  discussion is about never can. It also covers the language cookie and one-off
  maintenance copies. Its nightly-backup sentences (copies deleted after 14 days) appear only
  while the marker `nightly-backups-since`, written by the first nightly backup, exists (see
  "Backups and restore"). Any new kind of stored data must be added to `privacy.html` before it
  ships, with `PRIVACY_POLICY_UPDATED` bumped.
- The secrecy tests (`gifter/tests/test_secrecy.py`) run in the CI test job and block the build
  and the deploy when they fail, so a change that lets a giftee see claims cannot ship. The
  suite also covers discussion data (threads, comments, read receipts), in English and Czech.
- Opening a discussion records the opener's own read receipt (a `ThreadVisit` row). It is the
  only write on a GET in the app: it is needed to clear the "New since your last visit" marker
  the moment the thread is read, it touches only the viewer's own row, and it runs only after
  the access check has passed.
- HSTS is one year (31536000 s, includeSubDomains, no preload), fixed in `web/settings.py` since
  Phase 4. A `SECURE_HSTS_SECONDS` line left in the server `.env` is ignored and may be deleted.
- Responses to signed-in users are sent with `Cache-Control: private, no-store`, so a shared
  family phone does not show the previous person's pages from the cache or the back button.
- `/healthz` is public and returns only `ok` (or 503 `unavailable` when the database does not
  answer). It has no trailing slash on purpose; the deploy health check uses that exact path.
- Backups and manual copies are described in "Backups and restore". Never copy `db.sqlite3`
  alone while the app runs (WAL). Remove manual copies once they have served their purpose:
  they keep the data of anyone deleted afterwards (see "Delete someone's account").
