# API Coverage — Google Sign-In (OAuth 2.0 / OpenID Connect via django-allauth)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.
> Phase 1 integrates Google only as an identity provider through allauth's Google provider (server-side authorization-code flow). The browser Clipboard API used by the in-app hint's Copy link button is listed in the second table.

| capability | decision | reason |
|---|---|---|
| oauth2-authorization-code-sign-in (server-side, allauth Google provider) | INTEGRATE | |
| pkce-s256 (OAUTH_PKCE_ENABLED) | INTEGRATE | |
| state-parameter-csrf-protection | INTEGRATE | |
| scope-openid | INTEGRATE | |
| scope-email (email claim stored on gifter.User) | INTEGRATE | |
| scope-profile (given_name/family_name to first/last name) | INTEGRATE | |
| prompt-select-account (AUTH_PARAMS) | INTEGRATE | |
| next-return-url-through-oauth-state | INTEGRATE | |
| login-cancelled-and-error-callbacks (friendly pages) | INTEGRATE | |
| consent-screen-published-in-production (External, basic scopes) | INTEGRATE | |
| profile-picture-claim | OPT-OUT | not needed yet — no avatars anywhere in the v1 UI |
| offline-access-refresh-tokens | OPT-OUT | not needed — Gifter never calls Google APIs after sign-in |
| token-storage (SOCIALACCOUNT_STORE_TOKENS) | OPT-OUT | not needed — data minimisation; no Google API calls to make |
| google-apis-beyond-identity (Calendar, Drive, Contacts, People) | OPT-OUT | explicitly out of scope — basic scopes only, so no Google app verification is required |
| incremental-authorization | OPT-OUT | not needed — the scope set is fixed at openid, email, profile |
| google-one-tap-or-fedcm-button | OPT-OUT | not needed yet — extra JS and CSP work; revisit only if sign-in friction is observed (STACK.md) |
| client-side-id-token-flow (Google Identity Services JS) | OPT-OUT | explicitly out of scope — server-side code flow only, no client-side token handling |
| hosted-domain-restriction (hd parameter) | OPT-OUT | explicitly out of scope — any Google account may sign in (success criterion 2) |
| login-hint-parameter | OPT-OUT | not needed yet — relatives pick their account via prompt=select_account |
| token-revocation-and-disconnect-ui | OPT-OUT | not needed — Google is the only sign-in method and there is no connected-accounts page in v1 |
| additional-identity-providers-and-account-linking | OPT-OUT | explicitly out of scope — Google is the only login method (AUTH-01) |

## Browser API — Clipboard (in-app hint Copy link)

| capability | decision | reason |
|---|---|---|
| clipboard-writeText (Copy link button) | INTEGRATE | |
| clipboard-fallback-select-readonly-input | INTEGRATE | |
| clipboard-read | OPT-OUT | not needed — the hint only writes the page URL |
