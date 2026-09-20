import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

# Fail closed in production: an insecure fallback key is only allowed in dev.
SECRET_KEY = os.getenv('SECRET_KEY') or ('dev-insecure-key-change-in-production' if DEBUG else '')
if not SECRET_KEY:
    raise ImproperlyConfigured('SECRET_KEY environment variable is required when DEBUG is off.')

_allowed = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()]
ALLOWED_HOSTS = _allowed or (['*'] if DEBUG else [])

# Comma-separated list of full origins (https://example.com) for prod CSRF.
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'tree',

    # Thumbnails for Person.photo (Django ImageField) — avoids serving full originals
    'easy_thumbnails',
]

# easy-thumbnails: small cropped thumbnails for person photos (tree nodes + avatars)
THUMBNAIL_ALIASES = {
    '': {
        'node': {'size': (96, 96), 'crop': True},
        'avatar': {'size': (128, 128), 'crop': True},
    },
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# WhiteNoise: serve static files efficiently in production
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

ROOT_URLCONF = 'familytree_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'tree.context_processors.site_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'familytree_project.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL', '')
if DATABASE_URL:
    import re
    # Port is optional (defaults to 5432). A set-but-unparseable URL is an error,
    # not a silent fall-through to sqlite (that footgun could write prod to a file).
    m = re.match(
        r'^postgres(?:ql)?://(?P<user>[^:]+):(?P<password>[^@]+)@'
        r'(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<name>.+)$',
        DATABASE_URL,
    )
    if not m:
        raise ImproperlyConfigured('DATABASE_URL is set but is not a valid postgres:// URL.')
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': m.group('name'),
            'USER': m.group('user'),
            'PASSWORD': m.group('password'),
            'HOST': m.group('host'),
            'PORT': m.group('port') or '5432',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

LANGUAGE_CODE = 'ar'
TIME_ZONE = 'Asia/Muscat'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Public site name used across the UI. Rebrand freely via the SITE_NAME env var.
SITE_NAME = os.getenv('SITE_NAME', 'شجرة العائلة')


# --- Production hardening ---------------------------------------------------
# Toggled explicitly via env (decoupled from DEBUG, so tests/dev are unaffected).
# Set SECURE_HARDENING=True in production once it's served over HTTPS.
SECURE_HARDENING = os.getenv('SECURE_HARDENING', 'False').lower() in ('true', '1', 'yes')

CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True

if SECURE_HARDENING:
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Behind a reverse proxy terminating TLS, trust its forwarded-proto header.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# --- Logging ---------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '{levelname} {asctime} {name} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': os.getenv('LOG_LEVEL', 'INFO')},
    'loggers': {
        'django.request': {'handlers': ['console'], 'level': 'ERROR', 'propagate': False},
        'tree': {'handlers': ['console'], 'level': os.getenv('LOG_LEVEL', 'INFO'), 'propagate': False},
    },
}


# --- Error tracking (Sentry) -----------------------------------------------
# No-op unless SENTRY_DSN is set AND sentry-sdk is installed.
SENTRY_DSN = os.getenv('SENTRY_DSN', '')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0')),
            send_default_pii=False,
        )
    except ImportError:
        pass
