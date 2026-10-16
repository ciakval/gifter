# Phase 1: Google Sign-in Live - Context

**Gathered:** 2026-10-16
**Status:** Ready for planning

<domain>
## Phase Boundary

A cleaned-up Django 6.1 Gifter app, live at https://gifter.remesh.cz on Bombur, where anyone with a Google account can sign in (Google is the only login method), stay signed in across browser restarts, and sign out. Every push to `main` redeploys automatically (GitHub Actions → GHCR → Docker Compose) without losing `./data`. Signed-out visitors to any non-landing page are sent to sign in and returned afterwards. Messenger/Instagram in-app browsers get an "open in your browser" hint instead of Google's error.

Requirements: OPS-01, OPS-02, OPS-03, OPS-04, AUTH-01, AUTH-02, AUTH-03.

Not in this phase: events, invites, wishlists, claims (Phases 2–3); Czech catalogue and language switcher (Phase 4); backups (Phase 4).

</domain>

<decisions>
## Implementation Decisions

### Landing page (signed-out `/`)
- **D-01:** Minimal landing page: app name/logo, one sentence explaining what Gifter is, and a prominent "Sign in with Google" button. No multi-step explainer, no marketing content.

### First screen after sign-in
- **D-02:** Signed-in users land on a placeholder home ("Hi <name>, you're signed in" + sign-out). This page lives at the URL/view that Phase 2 will turn into "My events", so it is not throwaway routing. Signed-in users hitting `/` should get this home (or be redirected to it) rather than the sign-in pitch.

### Sign-in flow
- **D-03:** The landing button starts the Google OAuth flow directly — a `<form method="post">` to allauth's Google provider login URL (keeps `SOCIALACCOUNT_LOGIN_ON_GET = False`). No intermediate allauth login page in the normal path.
- **D-04:** `LOGIN_URL` points at the landing page; protected pages (AUTH-03) redirect there with `next` preserved, and the landing button carries `next` through the OAuth round trip so the user returns to the original page. allauth's own `/accounts/login/` may still exist as a fallback but should be styled consistently or redirect to the landing page — planner's choice.

### Language
- **D-05:** Phase 1 ships English text only. All strings are wrapped for translation (`{% translate %}`, `gettext_lazy`), `LocaleMiddleware` and `LANGUAGES = [en, cs]` are configured now, but the Czech catalogue and the language switcher are Phase 4.

### Claude's Discretion
The user chose not to discuss the following. Follow the research recommendations in `.planning/research/` and `.claude/CLAUDE.md`:
- **In-app browser hint (OPS-04):** detection scope (at least Messenger/FB, Instagram; others such as TikTok/LinkedIn if cheap), banner vs blocking interstitial, copy-link button and/or Android intent deep link. It must replace the Google button (or precede it) so users never hit Google's `disallowed_useragent` error.
- **Accounts & admin:** custom user model (`AbstractUser` subclass) before the first prod migration; display name sourced from Google profile; session length long enough that relatives effectively stay signed in (AUTH-02); admin moved off `/admin/` with only the author as staff.
- **Dev & deploy setup:** repo layout (`pyproject.toml` + `uv`, keep or flatten `src/`), how local dev signs in (separate Google OAuth dev client with `127.0.0.1` redirect is the default), whether a staging environment is worth it, CI gates (tests + `manage.py check --deploy` + `makemigrations --check` block deploy). Follow bombur-infra conventions and the `~/GIT/plachtis` reference app.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project scope & requirements
- `.planning/PROJECT.md` — core value, constraints, Key Decisions table (Bombur hosting, SQLite in `./data`, Django 6.1, custom user model)
- `.planning/REQUIREMENTS.md` — OPS-01..04, AUTH-01..03 definitions
- `.planning/ROADMAP.md` §"Phase 1: Google Sign-in Live" — success criteria, notes (consent screen publishing, redirect URI, proxy SSL header, WAL mode, user-side steps), standing rules

### Research
- `.planning/research/STACK.md` — pinned versions, allauth configuration notes (settings-based `APPS`, `ALLAUTH_TRUSTED_PROXY_COUNT`, `SECURE_PROXY_SSL_HEADER`), production settings list
- `.planning/research/PITFALLS.md` — OAuth / in-app browser / deploy pitfalls
- `.planning/research/ARCHITECTURE.md` — app structure guidance
- `.planning/research/SUMMARY.md` — research synthesis
- `.claude/CLAUDE.md` — technology stack recommendations (note: its Fly/Neon/Postgres hosting advice is superseded by the Bombur + SQLite decision in PROJECT.md)

### Infrastructure
- `bombur-infra` skill — Dockerfile, `compose.yaml`, `deploy.yml`, `.env.example`, `DEPLOYMENT.md`, Caddy block conventions
- `~/GIT/plachtis` — reference app already deployed on Bombur (external to this repo)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Essentially none worth keeping as-is. `src/gifter/models.py` `Wish` model (uses `auth.User` directly, has `claimed_by`) will be reshaped in Phase 2; in Phase 1 it must at least be repointed to the custom user model before migrations are regenerated.

### Established Patterns
- Django project `src/web` (settings/urls/wsgi), app `src/gifter`. No base template, no static files, no tests of substance.
- `src/web/settings.py` has a hard-coded (compromised) `SECRET_KEY` and `DEBUG = True` — both must move to env.
- `src/gifter/settings.py` exists but is empty — likely removable.
- `requirements.txt` is a data-science env dump — replace with a minimal pinned set.

### Integration Points
- `src/web/urls.py`: remove `login/` (`LoginView`) route and `templates/registration/login.html`; add `accounts/` (allauth), landing `/`, home view, relocated admin.
- `src/gifter/urls.py`: existing `add` route (broken `CreateWishView`, no login check) — either protect it or drop it for now; Phase 2 rebuilds wishes anyway.
- `src/gifter/migrations/0001_initial.py`: regenerate after custom user model lands (no prod data exists).

</code_context>

<specifics>
## Specific Ideas

- The audience is non-technical relatives arriving from a chat-app link on a phone: the landing page should be one clear sentence and one obvious button.
- The placeholder home should prove the full round trip (sign in → named greeting → sign out → sign back in).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-google-sign-in-live*
*Context gathered: 2026-10-16*
