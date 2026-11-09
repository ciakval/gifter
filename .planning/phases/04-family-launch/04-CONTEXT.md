# Phase 4: Family Launch - Context

**Gathered:** 2026-11-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Czech- and English-speaking relatives can use Gifter comfortably on their phones. The production data is backed up nightly and a restore is proven. Everything needed for a real family dry-run before the 1 Dec freeze is ready.

Delivered in code and repo: the Czech catalogue and language switcher, a phone-friendliness pass, the backup and restore tooling plus documentation, the dry-run materials, a HSTS raise and a /healthz endpoint.

The following need the user, so they become human-verification items rather than plan checkpoints:
- the restore drill on the server;
- real iPhone and Android checks;
- the dry-run with 2–3 relatives by ~22 Nov (OPS-05);
- installing the backup timer on Bombur, if it needs server access.

Not in this phase: notifications, hidden discussion, invite revoke and other v2 items.

User priority: "I want the app to start being usable asap." Phases 1–3 are live in production. Prefer the fewest plans with no checkpoints. Every phase 3 secrecy guarantee must keep passing; translations must not reintroduce a leak.

</domain>

<decisions>
## Implementation Decisions

### Czech & language switching
- **D-01:** The default language comes from the browser (Accept-Language via LocaleMiddleware). Czech phones get Czech automatically. Do not use URL prefixes (`i18n_patterns`), so invite links stay one stable URL.
- **D-02:** Language switcher: "EN / CS" in the navbar, plus the landing-page footer for signed-out visitors. It POSTs to Django's built-in `set_language` view, which stores a cookie, and redirects back to the same page via `next`.
- **D-03:** Claude writes the full `locale/cs/LC_MESSAGES/django.po`, covering every wrapped string including the privacy page. Plurals use the correct Czech three-form Plural-Forms header, checked against Django's own `cs` catalogue (1 dárek / 2 dárky / 5 dárků). A Czech-speaking relative reviews the copy during the dry-run. Add an automated check that `makemessages -l cs` leaves no untranslated or fuzzy entries, and decide whether `.mo` files are compiled in the Docker build or committed (pick one and keep to it; the Dockerfile needs gettext if compiling).
- **D-04:** The privacy page is fully translated, with the same honesty and date-gate rules as phases 2 and 3.

### Phone pass
- **D-05:** A template/CSS pass:
  - tap targets of at least 44px;
  - action buttons stack on narrow screens;
  - long links and wish names wrap;
  - no horizontal scroll at 360px width.
  Automated checks: the viewport meta tag is present on every page, and templates and CSS contain no fixed pixel widths wider than a phone.
- **D-06:** Real-device checks (iPhone Safari, Android Chrome, plus in-app browsers where Google sign-in works) become human-verification items for the dry-run.
- **D-07:** Keep stock Bootstrap (vendored) and only tidy it. No custom theme.
- **D-08:** Keep the existing in-app-browser hint. Its wording is adjusted later from real reports.

### Backups
- **D-09:** Nightly backup with `sqlite3 <db> ".backup <file>"`, which stays consistent while the app runs. It is driven by a systemd timer or cron on Bombur, following the bombur-infra conventions (load the bombur-infra skill when planning).
- **D-10:** Backups go to a directory outside the app directory on Bombur, keeping 14 daily copies (oldest removed).
- **D-11:** A restore script plus a documented restore procedure in DEPLOYMENT.md. The user runs one restore drill on the server before 1 Dec; it is recorded as a human-verification item, and its result goes into DEPLOYMENT.md / STATE.
- **D-12:** The privacy page states that backups rotate after 14 days. This ties into the `delete_user` steps: data of a deleted person stays in older backups until they rotate out. Bump `PRIVACY_POLICY_UPDATED` with the date gate.

### Family dry-run & launch hygiene
- **D-13:** Prepare a short plain-Czech "how to join" message the user can paste into the family chat, plus a 5-step checklist: sign in, join, add a wish, claim someone else's wish, report what was confusing. Store it in the repo (e.g. `docs/` or DEPLOYMENT.md).
- **D-14:** The dry-run itself (OPS-05) is a human-verification item after deploy: the user sends the invite, and 2–3 relatives try it by ~22 Nov. Fixes from it become a follow-up quick task.
- **D-15:** Feedback comes back through the family chat, and the user pastes it to Claude. There is no in-app feedback form.
- **D-16:** Raise HSTS `max-age` above 3600 (the site is stable). Add a `/healthz` endpoint (public, minimal, no data) and set `health_path` in the reusable deploy call (pending STATE todos).

### Claude's Discretion
- Plan split, file layout for the dry-run docs, and the exact HSTS value (e.g. 31536000 or a staged step up).
- Whether `.mo` files are compiled at image build time or committed (D-03; be consistent).
- How the backup timer is shipped. Repo-tracked unit and script files plus DEPLOYMENT.md install steps are fine if Claude cannot install them on the server.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- All UI strings are already wrapped (`{% translate %}`, `{% blocktranslate %}`, `gettext_lazy`, `ngettext`). `LANGUAGES = [en, cs]` and `LocaleMiddleware` have been configured since phase 1 (D-05 of phase 1).
- `base.html` (navbar, footer with the Privacy policy link), the vendored Bootstrap 5.3.8, and `landing.js`.
- `scripts/smoke.sh` and `scripts/container-smoke.sh`, the deploy workflow (test → build → deploy via bombur-deploy), and DEPLOYMENT.md (Day-2 steps, `delete_user`, `sqlite3 .backup` already named for pre-deletion copies).
- The phase 3 secrecy suite (`gifter/tests/test_secrecy.py`): byte-identical snapshots, sentinel crawl, route inventory, staff-giftee pass. Translated pages must still pass, and the snapshots should also run under `cs`.

### Established Patterns
- Never shadow `_`. Use whole-sentence `blocktranslate` (no concatenation). Use `ngettext` for counts.
- The privacy-page date gate pattern (phases 2 and 3).
- New public routes must be added to the route inventory in test_secrecy.py and to test_lockdown (`/healthz`, `/i18n/setlang/`).

### Integration Points
- `web/settings.py` (`LOCALE_PATHS`, HSTS), `web/urls.py` (`set_language`, `/healthz`), `Dockerfile` (gettext and compilemessages if compiling at build time), `.github/workflows/deploy.yml` (`health_path`), `locale/cs/LC_MESSAGES/django.po`, templates, `DEPLOYMENT.md`, new backup script and unit files.

</code_context>

<specifics>
## Specific Ideas

- Czech plural example to verify: 1 dárek / 2 dárky / 5 dárků (ROADMAP SC1).
- New msgids from phase 3, "Claim %(pk)s" and "Contribution %(pk)s", need translating too (03 verification note).
- After `delete_user`, SQLite keeps freed pages until VACUUM. Consider a periodic VACUUM, or VACUUM INTO for backups (03 verification note).

</specifics>

<deferred>
## Deferred Ideas

None. Discussion stayed within phase scope.

</deferred>
