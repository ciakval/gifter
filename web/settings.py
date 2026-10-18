"""
Django settings for the Gifter project.

Everything environment-specific comes from environment variables (read with
django-environ). Production passes real environment variables via Docker
Compose; local development may use a gitignored .env file in the repo root.
Secrets fail closed: with DEBUG off, a missing SECRET_KEY or Google credential
raises ImproperlyConfigured instead of starting with a weak default.
"""

from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
# Local development convenience only; existing environment variables win.
if (BASE_DIR / ".env").exists():
    environ.Env.read_env(BASE_DIR / ".env")

DEBUG = env("DEBUG")

# Fail closed: no default in production -> ImproperlyConfigured if missing.
SECRET_KEY = env(
    "SECRET_KEY",
    default="dev-only-insecure-key-do-not-use-in-production" if DEBUG else environ.Env.NOTSET,
)

PUBLIC_HOSTS = env.list("PUBLIC_HOSTS", default=["localhost", "127.0.0.1"])
ALLOWED_HOSTS = PUBLIC_HOSTS
CSRF_TRUSTED_ORIGINS = [
    f"https://{host}" for host in PUBLIC_HOSTS if host not in ("localhost", "127.0.0.1")
]

GOOGLE_CLIENT_ID = env(
    "GOOGLE_CLIENT_ID",
    default="dev-placeholder-client-id" if DEBUG else environ.Env.NOTSET,
)
GOOGLE_CLIENT_SECRET = env(
    "GOOGLE_CLIENT_SECRET",
    default="dev-placeholder-client-secret" if DEBUG else environ.Env.NOTSET,
)
if not DEBUG and not (GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET):
    raise ImproperlyConfigured(
        "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be non-empty when DEBUG is off."
    )


# Application definition

INSTALLED_APPS = [
    "gifter",  # first, so its templates override allauth's
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
]  # deliberately no sites framework and no SITE_ID

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "web.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "web.wsgi.application"


# Database: SQLite in WAL mode under DATA_DIR (a bind-mounted volume in production).

DATA_DIR = Path(env("DATA_DIR", default=str(BASE_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}


# Authentication: Google is the only way in. No passwords exist.

AUTH_USER_MODEL = "gifter.User"
AUTHENTICATION_BACKENDS = ["allauth.account.auth_backends.AuthenticationBackend"]

LOGIN_URL = "landing"
LOGIN_REDIRECT_URL = "home"
ACCOUNT_LOGOUT_REDIRECT_URL = "landing"
ACCOUNT_EMAIL_VERIFICATION = "none"  # required by SOCIALACCOUNT_ONLY (allauth system check)
ACCOUNT_USER_DISPLAY = lambda user: user.display_name  # noqa: E731
SOCIALACCOUNT_ONLY = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"  # required by SOCIALACCOUNT_ONLY
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False  # sign-in must be a CSRF-protected POST (D-03)
SOCIALACCOUNT_PROVIDERS = {
    "google": {  # keep everything in ONE dict
        "APPS": [
            {
                "client_id": GOOGLE_CLIENT_ID,
                "secret": GOOGLE_CLIENT_SECRET,
                "key": "",
            }
        ],
        "SCOPE": ["openid", "profile", "email"],  # basic scopes only
        "OAUTH_PKCE_ENABLED": True,
        "AUTH_PARAMS": {"prompt": "select_account"},
    }
}

# 90 days: persistent cookie covering the Christmas season (ACCOUNT_SESSION_REMEMBER
# has no effect for social login).
SESSION_COOKIE_AGE = 60 * 60 * 24 * 90
ALLAUTH_TRUSTED_PROXY_COUNT = 1  # one proxy: Caddy


# Internationalization (D-05): strings are wrapped from day one; Czech catalogue is Phase 4.

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("cs", _("Čeština"))]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Prague"
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# The test runner forces settings.DEBUG to False at runtime while this module reads
# env DEBUG at import, so the manifest storage would raise "Missing staticfiles
# manifest entry" in tests and local dev that never ran collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Production security block (only when DEBUG is off; plain-HTTP tests and local dev stay usable).

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=3600)  # raise after a week of working HTTPS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# HSTS preload is deliberately not enabled.
SILENCED_SYSTEM_CHECKS = ["security.W021"]
