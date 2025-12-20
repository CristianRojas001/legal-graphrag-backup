# Legal GraphRAG System - Deployment Guide

## Document Information
- **Version**: 1.0 (MVP)
- **Last Updated**: 2025-12-11
- **Status**: Planning Phase
- **Related**: [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) | [05_API_SPECIFICATION.md](./05_API_SPECIFICATION.md)

---

## 1. Deployment Overview

### Infrastructure Stack

```
Digital Ocean App Platform
├── Backend (Django 5)
│   ├── App: api.artisting.es
│   ├── Gunicorn workers
│   └── Celery workers
├── Frontend (Next.js 15)
│   ├── App: legal.artisting.es
│   └── Static assets on CDN
├── Managed PostgreSQL
│   ├── Version: 15
│   ├── Extensions: pgvector
│   └── Connection pool: 25
└── Managed Redis
    ├── Celery broker
    └── Cache backend
```

### External Services

- **Gemini API** (Google AI): Embeddings + Chat LLM
- **Stripe API**: Billing (shared with existing system)
- **Let's Encrypt**: SSL certificates (auto-managed by DO)

---

## 2. Prerequisites

### 2.1 Digital Ocean Setup

**Required Resources**:
- App Platform account
- PostgreSQL database (existing or new)
- Redis instance (existing or new)
- Domain configured: `legal.artisting.es`, `api.artisting.es`

**Access**:
```bash
# Database credentials (from Digital Ocean control panel)
HOST=db-postgresql-fra1-39785-do-user-23421971-0.f.db.ondigitalocean.com
PORT=25060
DATABASE=defaultdb
USER=doadmin
PASSWORD=<your-password>
```

### 2.2 API Keys

**Gemini API**:
```bash
# Get from: https://aistudio.google.com/app/apikey
GEMINI_API_KEY=AIzaSy...
```

**Stripe** (shared with existing system):
```bash
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
```

---

## 3. Database Setup

### 3.1 Enable pgvector Extension

```bash
# Connect to database
psql "postgresql://doadmin:<password>@db-postgresql-fra1-39785-do-user-23421971-0.f.db.ondigitalocean.com:25060/defaultdb?sslmode=require"
```

```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Exit
\q
```

### 3.2 Run Migrations

```bash
# In backend directory
cd backend

# Create migrations
python manage.py makemigrations legal_graphrag

# Apply migrations
python manage.py migrate legal_graphrag

# Verify tables created
python manage.py dbshell
```

```sql
\dt legal_*

-- Should show:
-- legal_corpus_sources
-- legal_documents
-- legal_document_chunks
-- legal_chat_sessions
-- legal_chat_messages
```

### 3.3 Import Corpus Sources

```bash
# Import from Excel file
python manage.py import_corpus_from_excel \
  "D:/IT workspace/Legal GraphRAG/corpus_normativo_artisting_enriched.xlsx"

# Verify import
python manage.py shell
```

```python
from apps.legal_graphrag.models import CorpusSource
print(f"Total sources: {CorpusSource.objects.count()}")
print(f"P1 sources: {CorpusSource.objects.filter(prioridad='P1').count()}")
```

---

## 4. Environment Variables

### 4.1 Backend (.env)

Create `backend/.env`:

```bash
# Django
SECRET_KEY=<django-secret-key>
DEBUG=False
ALLOWED_HOSTS=api.artisting.es,localhost

# Database
DATABASE_URL=postgresql://doadmin:<password>@db-postgresql-fra1-39785-do-user-23421971-0.f.db.ondigitalocean.com:25060/defaultdb?sslmode=require

# Redis
REDIS_URL=redis://<redis-host>:25061
CELERY_BROKER_URL=redis://<redis-host>:25061/0

# Gemini API
GEMINI_API_KEY=AIzaSy...
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# Stripe (shared)
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# CORS
CORS_ALLOWED_ORIGINS=https://legal.artisting.es,http://localhost:3001

# Security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
```

### 4.2 Frontend (.env.local)

Create `frontend/.env.local`:

```bash
NEXT_PUBLIC_API_URL=https://api.artisting.es
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

---

## 5. Digital Ocean App Platform Deployment

### 5.1 Backend Deployment

**App Spec** (`.do/app.yaml`):

```yaml
name: artisting-legal-backend
region: fra

services:
  - name: api
    github:
      repo: your-org/artisting-backend
      branch: main
      deploy_on_push: true

    build_command: pip install -r requirements.txt

    run_command: |
      python manage.py migrate --noinput && \
      python manage.py collectstatic --noinput && \
      gunicorn ovra_backend.wsgi:application \
        --bind 0.0.0.0:8080 \
        --workers 3 \
        --timeout 300

    environment_slug: python
    instance_count: 1
    instance_size_slug: basic-xs

    envs:
      - key: DATABASE_URL
        value: ${DATABASE_URL}
      - key: REDIS_URL
        value: ${REDIS_URL}
      - key: GEMINI_API_KEY
        value: ${GEMINI_API_KEY}
        type: SECRET
      - key: SECRET_KEY
        value: ${SECRET_KEY}
        type: SECRET

    routes:
      - path: /

    health_check:
      http_path: /api/v1/health/

  - name: celery-worker
    github:
      repo: your-org/artisting-backend
      branch: main

    build_command: pip install -r requirements.txt

    run_command: |
      celery -A ovra_backend worker \
        --loglevel=info \
        --concurrency=2

    environment_slug: python
    instance_count: 1
    instance_size_slug: basic-xs

    envs:
      - key: DATABASE_URL
        value: ${DATABASE_URL}
      - key: REDIS_URL
        value: ${REDIS_URL}
      - key: GEMINI_API_KEY
        value: ${GEMINI_API_KEY}
        type: SECRET

databases:
  - name: postgres
    engine: PG
    version: "15"
    production: true

  - name: redis
    engine: REDIS
    version: "7"
    production: true
```

### 5.2 Frontend Deployment

**App Spec**:

```yaml
name: artisting-legal-frontend
region: fra

static_sites:
  - name: web
    github:
      repo: your-org/artisting-frontend-legal
      branch: main
      deploy_on_push: true

    build_command: npm run build
    output_dir: .next

    environment_slug: node-js

    envs:
      - key: NEXT_PUBLIC_API_URL
        value: https://api.artisting.es

    routes:
      - path: /

    catchall_document: index.html
```

---

## 6. Manual Deployment Steps

### 6.1 Backend

```bash
# 1. SSH into server (if using Droplet) or use App Platform CLI
doctl apps create --spec .do/app.yaml

# 2. Or deploy via Git push
git add .
git commit -m "Deploy Legal GraphRAG backend"
git push origin main

# Digital Ocean auto-deploys on push

# 3. Verify deployment
curl https://api.artisting.es/api/v1/health/

# Expected response:
# {"status": "ok", "database": "connected", "redis": "connected"}
```

### 6.2 Frontend

```bash
# 1. Build locally to test
npm run build

# 2. Deploy via Git push
git add .
git commit -m "Deploy Legal GraphRAG frontend"
git push origin main

# 3. Verify
curl https://legal.artisting.es
```

---

## 7. Post-Deployment Setup

### 7.1 Ingest P1 Sources

```bash
# SSH into backend app or use DO console
python manage.py shell

from apps.legal_graphrag.tasks import ingest_all_p1_sources
ingest_all_p1_sources.delay()
```

**Monitor Progress**:

```bash
# View Celery logs
doctl apps logs <app-id> --component celery-worker --follow

# Check ingestion status
python manage.py shell

from apps.legal_graphrag.models import CorpusSource
for s in CorpusSource.objects.filter(prioridad='P1'):
    print(f"{s.estado:12} | {s.titulo}")
```

### 7.2 Create Database Indexes

```sql
-- After initial ingestion, optimize indexes
VACUUM ANALYZE legal_document_chunks;
REINDEX INDEX idx_chunks_embedding;
```

### 7.3 Set Up Monitoring

```python
# backend/ovra_backend/settings.py

# Add Prometheus metrics (optional)
INSTALLED_APPS += ['django_prometheus']

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    # ... existing middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]
```

---

## 8. DNS Configuration

### 8.1 Domain Setup

**A Records**:
```
api.artisting.es     → <Digital Ocean App IP>
legal.artisting.es   → <Digital Ocean App IP>
```

**CNAME (Alternative)**:
```
api.artisting.es     → <app-name>.ondigitalocean.app
legal.artisting.es   → <app-name>.ondigitalocean.app
```

### 8.2 SSL Certificates

Digital Ocean App Platform auto-manages Let's Encrypt certificates:
- No manual setup required
- Auto-renewal every 90 days
- Verify: `https://legal.artisting.es` (padlock in browser)

---

## 9. Continuous Deployment (CI/CD)

### 9.1 GitHub Actions (Optional)

```yaml
# .github/workflows/deploy-backend.yml

name: Deploy Backend

on:
  push:
    branches: [main]
    paths:
      - 'backend/**'

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Install doctl
        uses: digitalocean/action-doctl@v2
        with:
          token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}

      - name: Trigger deployment
        run: |
          doctl apps create-deployment <app-id>
```

### 9.2 Auto-Deploy on Git Push

Digital Ocean App Platform auto-deploys when:
- Commit pushed to `main` branch
- Build succeeds
- Health check passes

**No additional CI/CD needed for MVP**.

---

## 10. Rollback Strategy

### 10.1 Via Digital Ocean Console

1. Go to App Platform → Your App
2. Click "Deployments" tab
3. Find previous successful deployment
4. Click "Redeploy"

### 10.2 Via CLI

```bash
# List deployments
doctl apps list-deployments <app-id>

# Rollback to previous deployment
doctl apps create-deployment <app-id> --deployment-id <previous-deployment-id>
```

---

## 11. Monitoring & Logging

### 11.1 Application Logs

```bash
# View real-time logs
doctl apps logs <app-id> --follow

# View logs for specific component
doctl apps logs <app-id> --component api --follow
doctl apps logs <app-id> --component celery-worker --follow
```

### 11.2 Error Tracking (Sentry)

```bash
# Install Sentry SDK
pip install sentry-sdk
```

```python
# backend/ovra_backend/settings.py

import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn="https://<your-sentry-dsn>",
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False
)
```

### 11.3 Performance Monitoring

```python
# Track query performance
import logging
import time

logger = logging.getLogger('apps.legal_graphrag.performance')

def track_query_time(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = (time.time() - start) * 1000
        logger.info(f"{func.__name__} took {duration:.2f}ms")
        return result
    return wrapper
```

---

## 12. Backup Strategy

### 12.1 Database Backups

Digital Ocean Managed PostgreSQL:
- **Auto-backups**: Daily
- **Retention**: 7 days (free tier), 30 days (paid)
- **Manual backup**:

```bash
# Create manual snapshot
doctl databases backup create <database-id>

# List backups
doctl databases backup list <database-id>

# Restore from backup
doctl databases create-from-backup --backup-id <backup-id>
```

### 12.2 Code Backups

- **Git**: Source code in GitHub (version controlled)
- **Environment variables**: Securely stored in password manager
- **Corpus Excel**: Backed up in cloud storage (Google Drive, Dropbox)

---

## 13. Scaling Strategy

### 13.1 Vertical Scaling

```yaml
# Increase instance size in app.yaml
instance_size_slug: professional-xs  # More CPU/RAM
```

### 13.2 Horizontal Scaling

```yaml
# Increase instance count
instance_count: 3  # Multiple backend instances
```

### 13.3 Auto-Scaling (Post-MVP)

```yaml
# Enable auto-scaling
autoscaling:
  min_instance_count: 1
  max_instance_count: 5
  metrics:
    cpu:
      percent: 80
```

---

## 14. Production Checklist

### Pre-Launch

- [ ] Enable pgvector in PostgreSQL
- [ ] Run migrations
- [ ] Import corpus sources (70 sources)
- [ ] Ingest P1 sources (37 sources)
- [ ] Verify embeddings generated
- [ ] Test search queries (10+ test cases)
- [ ] Set up error tracking (Sentry)
- [ ] Configure domain DNS
- [ ] Verify SSL certificates
- [ ] Set up monitoring dashboards
- [ ] Document rollback procedure

### Post-Launch

- [ ] Monitor error rates (first 24h)
- [ ] Check response times (<5s)
- [ ] Verify Gemini API quota
- [ ] Monitor database performance
- [ ] Check Celery queue length
- [ ] Set up weekly corpus updates
- [ ] Schedule ingestion of P2 sources

---

**Document End** | Next: [07_TESTING_STRATEGY.md](./07_TESTING_STRATEGY.md)
