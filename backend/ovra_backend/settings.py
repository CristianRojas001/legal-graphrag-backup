"""
Legal GraphRAG Django Settings
Configuration for Legal GraphRAG system.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from corsheaders.defaults import default_headers

# Load environment variables
load_dotenv()

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-CHANGE-THIS-IN-PRODUCTION')
DEBUG = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'corsheaders',

    # Legal GraphRAG app
    'apps.legal_graphrag',
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

ROOT_URLCONF = 'ovra_backend.urls'

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

WSGI_APPLICATION = 'ovra_backend.wsgi.application'

# Database - PostgreSQL with pgvector
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('LEGAL_DB_NAME', 'postgres'),
        'USER': os.getenv('LEGAL_DB_USER', 'postgres'),
        'PASSWORD': os.getenv('LEGAL_DB_PASSWORD', ''),
        'HOST': os.getenv('LEGAL_DB_HOST', 'localhost'),
        'PORT': os.getenv('LEGAL_DB_PORT', '5432'),
        'OPTIONS': {
            'client_encoding': 'UTF8',
        },
        'TEST': {
            'NAME': os.getenv('LEGAL_DB_TEST_NAME', f"test_{os.getenv('LEGAL_DB_NAME', 'postgres')}"),
            'CHARSET': 'UTF8',
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# URL Configuration
APPEND_SLASH = True  # Use canonical URLs in local/dev

# Internationalization
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS settings
CORS_ALLOW_ALL_ORIGINS = DEBUG
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://localhost:3001').split(',')
CORS_ALLOW_HEADERS = list(default_headers) + [
    'x-developer-debug',
]

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
    ],
    # Ensure UTF-8 encoding for JSON responses
    'UNICODE_JSON': True,
    'STRICT_JSON': False,
}

# Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
# Using gemini-2.0-flash-exp (fastest available, 2-3x faster than deprecated 1.5-flash-8b)
GEMINI_CHAT_MODEL = os.getenv('GEMINI_CHAT_MODEL', 'gemini-2.0-flash-exp')
GEMINI_EMBEDDING_MODEL = 'text-embedding-004'
# RAG gating thresholds
RAG_MIN_STRICT_MATCHES = int(os.getenv('RAG_MIN_STRICT_MATCHES', '0'))
RAG_MIN_TOKEN_MATCHES = int(os.getenv('RAG_MIN_TOKEN_MATCHES', '1'))
RAG_SEMANTIC_THRESHOLD = float(os.getenv('RAG_SEMANTIC_THRESHOLD', '0.7'))
RAG_SEMANTIC_MATCH_ENABLED = os.getenv('RAG_SEMANTIC_MATCH_ENABLED', 'false').lower() == 'true'
RAG_MAX_CHUNKS_PER_DOC = int(os.getenv('RAG_MAX_CHUNKS_PER_DOC', '2'))
RAG_RERANK_ENABLED = os.getenv('RAG_RERANK_ENABLED', 'false').lower() == 'true'
RAG_RERANK_MODEL = os.getenv('RAG_RERANK_MODEL', '')
RAG_RERANK_TOP_K = int(os.getenv('RAG_RERANK_TOP_K', '30'))
RAG_ADAPTIVE_RRF = os.getenv('RAG_ADAPTIVE_RRF', 'true').lower() == 'true'
RAG_HYBRID_VECTOR_WEIGHT = float(os.getenv('RAG_HYBRID_VECTOR_WEIGHT', '0.6'))
RAG_HYBRID_LEXICAL_WEIGHT = float(os.getenv('RAG_HYBRID_LEXICAL_WEIGHT', '0.4'))
_NON_TAX_PERCENT_DEFAULTS = [100]
_non_tax_percent_raw = os.getenv("RAG_NON_TAX_PERCENT_ALLOWLIST", "")
_non_tax_percent_env = [
    int(value)
    for value in _non_tax_percent_raw.split(",")
    if value.strip().isdigit()
]
RAG_NON_TAX_PERCENT_ALLOWLIST = sorted({*(_NON_TAX_PERCENT_DEFAULTS), *(_non_tax_percent_env)})

# Performance optimizations (V1.1)
RAG_AREA_FILTER_ENABLED = os.getenv('RAG_AREA_FILTER_ENABLED', 'true').lower() == 'true'  # Filter by area BEFORE retrieval
RAG_JUDGE_ENABLED = os.getenv('RAG_JUDGE_ENABLED', 'false').lower() == 'true'  # Disable judge to reduce latency (saves 15-25s)

# Redis
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Celery
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'ingestion_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'ingestion.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',  # Fix CP1252 encoding errors
        },
    },
    'loggers': {
        'apps.legal_graphrag.ingestion': {
            'handlers': ['console', 'ingestion_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}
