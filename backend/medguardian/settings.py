import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file at workspace root
env_path = BASE_DIR.parent / '.env'
if env_path.exists():
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key, val = stripped.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())

SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third Party
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'django_celery_results',   # Stage 2: persist Celery task results in DB

    # Project Apps
    'accounts',
    'patients',
    'prescriptions',
    'evidence',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'medguardian.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'medguardian.wsgi.application'

DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL.startswith('postgres://'):
    import urllib.parse as urlparse
    import socket
    url = urlparse.urlparse(DATABASE_URL)
    
    # Check if host is resolvable. If not, fallback to SQLite for local development
    postgres_resolvable = False
    try:
        socket.gethostbyname(url.hostname)
        postgres_resolvable = True
    except Exception:
        pass

    if postgres_resolvable:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.postgresql',
                'NAME': url.path[1:],
                'USER': url.username,
                'PASSWORD': url.password,
                'HOST': url.hostname,
                'PORT': url.port,
            }
        }
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '10000/day'
    }
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

CHROMA_DB_PATH = os.path.join(BASE_DIR, 'chroma_db')

# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Celery Configuration
# ─────────────────────────────────────────────────────────────────────────────
_REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Probe Redis connectivity once at startup
_redis_available = False
try:
    import redis as _redis_client
    _r = _redis_client.from_url(_REDIS_URL, socket_connect_timeout=1)
    _r.ping()
    _redis_available = True
except Exception:
    import logging as _logging
    _logging.getLogger('django').warning(
        "[MedGuardian] Redis not reachable at %s. "
        "Celery will use the in-memory broker (single-process only). "
        "Install Redis to enable full async background tasks.",
        _REDIS_URL
    )

if _redis_available:
    CELERY_BROKER_URL = _REDIS_URL
    CELERY_RESULT_BACKEND = 'django-db'          # Stored via django_celery_results
else:
    # ── No-Redis fallback: tasks run in-process (great for local dev / tests)
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = 'cache+memory://'    # In-process result store

CELERY_CACHE_BACKEND = 'default'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Run tasks synchronously when Redis is not active or during unit tests
CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', str(not _redis_available)).lower() == 'true'
CELERY_TASK_EAGER_PROPAGATES = True


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Cache Framework (used for debounce locks)
# ─────────────────────────────────────────────────────────────────────────────
if _redis_available:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _REDIS_URL,
        }
    }
else:
    # Fallback for local dev without Docker Redis running
    # WARNING: LocMemCache is NOT shared across processes. The debounce lock
    # in tasks.py will NOT work correctly with multiple Celery workers in this mode.
    # This fallback is safe ONLY for single-process local development.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'medguardian-debounce',
        }
    }

