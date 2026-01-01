# Legal GraphRAG Migration: Supabase → Local PostgreSQL

**Complete guide for migrating Legal GraphRAG from Supabase to local PostgreSQL**

Created: 2025-12-26
Status: Ready to execute

---

## Overview

This migration moves your Legal GraphRAG project from Supabase cloud PostgreSQL to a local Docker-based PostgreSQL instance with pgvector support.

**Current Setup:**
- Database: Supabase PostgreSQL (aws-1-eu-west-1.pooler.supabase.com:6543)
- Django Models: CorpusSource, LegalDocument, DocumentChunk, ChatSession, ChatMessage
- pgvector: 768-dimensional embeddings

**Target Setup:**
- Database: Local PostgreSQL 16 with pgvector (localhost:5434)
- Same schema, managed by Django migrations
- Docker Compose for easy management

---

## Quick Start (Recommended)

### Step 1: Start Local PostgreSQL

```bash
cd "d:\IT workspace\Legal GraphRAG"
docker-compose -f docker-compose.legal-db.yml up -d
```

This will:
- Start PostgreSQL 16 with pgvector on port 5434
- Create database `legal_graphrag_local`
- Initialize required extensions (vector, uuid-ossp, pg_trgm)
- Start pgAdmin on port 5051

**Wait 10-15 seconds** for the database to be ready.

### Step 2: Verify Database is Running

```bash
"C:\Program Files\PostgreSQL\17\bin\psql" ^
  "postgresql://postgres:localdev123@localhost:5434/legal_graphrag_local" ^
  -c "SELECT version();"
```

You should see PostgreSQL 16 version info.

### Step 3: Update Environment Variables

Update `backend\.env`:

```env
# Database - Local PostgreSQL with pgvector
LEGAL_DB_NAME=legal_graphrag_local
LEGAL_DB_USER=postgres
LEGAL_DB_PASSWORD=localdev123
LEGAL_DB_HOST=localhost
LEGAL_DB_PORT=5434
LEGAL_DB_TEST_NAME=test_legal_graphrag_local
```

**Keep your old Supabase settings commented** in case you need to reference them:

```env
# OLD SUPABASE (backup reference)
# LEGAL_DB_HOST=aws-1-eu-west-1.pooler.supabase.com
# LEGAL_DB_PORT=6543
# LEGAL_DB_USER=postgres.oerjegzospyheojqjrrd
# LEGAL_DB_PASSWORD=E:wyKn!W!xjht48
```

### Step 4: Run Django Migrations

```bash
cd backend
python manage.py migrate
```

This will create all tables according to your Django models.

### Step 5: Verify Tables Were Created

```bash
"C:\Program Files\PostgreSQL\17\bin\psql" ^
  "postgresql://postgres:localdev123@localhost:5434/legal_graphrag_local" ^
  -c "\dt public.*"
```

You should see:
- legal_corpus_sources
- legal_documents
- legal_document_chunks
- legal_chat_sessions
- legal_chat_messages
- Django admin tables

### Step 6: Test Application

```bash
cd backend
python manage.py runserver
```

Try accessing:
- Admin: http://localhost:8000/admin
- API endpoints: http://localhost:8000/api/v1/...

---

## Option: Migrate Existing Data from Supabase

If you want to preserve your existing data from Supabase:

### 1. Backup from Supabase

```bash
cd "d:\IT workspace\Legal GraphRAG\scripts"

"C:\Program Files\PostgreSQL\17\bin\pg_dump" ^
  -h aws-1-eu-west-1.pooler.supabase.com ^
  -p 6543 ^
  -U postgres.oerjegzospyheojqjrrd ^
  -d postgres ^
  -t "public.legal_*" ^
  --no-owner --no-acl ^
  > backup_supabase_legal_%date:~-4,4%%date:~-10,2%%date:~-7,2%.sql
```

You'll be prompted for password: `E:wyKn!W!xjht48`

### 2. Review Backup

Check the backup file to ensure it contains your data:

```bash
head -n 100 backup_supabase_legal_*.sql
```

### 3. Restore to Local

**IMPORTANT:** Skip Django migrations (Step 4 above) if restoring from backup.

```bash
"C:\Program Files\PostgreSQL\17\bin\psql" ^
  "postgresql://postgres:localdev123@localhost:5434/legal_graphrag_local" ^
  -f "backup_supabase_legal_*.sql"
```

### 4. Mark Migrations as Applied (Fake)

Since you restored tables directly, tell Django they're already applied:

```bash
cd backend
python manage.py migrate --fake
```

---

## Daily Operations

### Start Database

```bash
cd "d:\IT workspace\Legal GraphRAG"
docker-compose -f docker-compose.legal-db.yml up -d
```

### Stop Database

```bash
docker-compose -f docker-compose.legal-db.yml down
```

### View Database Logs

```bash
docker logs legal-graphrag-postgres
```

### Access pgAdmin

- URL: http://localhost:5051
- Email: admin@legal.dev
- Password: admin123

**To connect to database in pgAdmin:**
1. Right-click "Servers" → "Register" → "Server"
2. Name: Legal GraphRAG Local
3. Connection tab:
   - Host: postgres (use container name, not localhost)
   - Port: 5432
   - Database: legal_graphrag_local
   - Username: postgres
   - Password: localdev123

### Connect via psql

```bash
"C:\Program Files\PostgreSQL\17\bin\psql" ^
  "postgresql://postgres:localdev123@localhost:5434/legal_graphrag_local"
```

### Backup Database

```bash
cd "d:\IT workspace\Legal GraphRAG\scripts"

"C:\Program Files\PostgreSQL\17\bin\pg_dump" ^
  -h localhost -p 5434 -U postgres ^
  -d legal_graphrag_local ^
  --no-owner --no-acl ^
  > backup_local_%date:~-4,4%%date:~-10,2%%date:~-7,2%.sql
```

---

## Troubleshooting

### Port 5434 Already in Use

Change port in `docker-compose.legal-db.yml`:

```yaml
ports:
  - "5435:5432"  # Use different port
```

Then update `backend\.env`:

```env
LEGAL_DB_PORT=5435
```

### Container Won't Start

```bash
# Check logs
docker logs legal-graphrag-postgres

# Full restart
docker-compose -f docker-compose.legal-db.yml down
docker-compose -f docker-compose.legal-db.yml up -d

# Nuclear option (deletes all data!)
docker-compose -f docker-compose.legal-db.yml down -v
docker-compose -f docker-compose.legal-db.yml up -d
```

### Django Can't Connect

1. Verify database is running:
   ```bash
   docker ps | findstr legal-graphrag-postgres
   ```

2. Test connection directly:
   ```bash
   "C:\Program Files\PostgreSQL\17\bin\psql" ^
     "postgresql://postgres:localdev123@localhost:5434/legal_graphrag_local" ^
     -c "SELECT 1;"
   ```

3. Check `backend\.env` has correct values

4. Restart Django:
   ```bash
   cd backend
   python manage.py runserver
   ```

### Migrations Fail

If you get "relation already exists" errors:

```bash
# Option 1: Fake the migrations (if tables exist)
python manage.py migrate --fake

# Option 2: Drop and recreate (DESTROYS DATA!)
docker-compose -f docker-compose.legal-db.yml down -v
docker-compose -f docker-compose.legal-db.yml up -d
# Wait 15 seconds
python manage.py migrate
```

### pgvector Extension Issues

If embeddings aren't working:

```bash
"C:\Program Files\PostgreSQL\17\bin\psql" ^
  "postgresql://postgres:localdev123@localhost:5434/legal_graphrag_local" ^
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

---

## Configuration Files

### docker-compose.legal-db.yml

Located at: `d:\IT workspace\Legal GraphRAG\docker-compose.legal-db.yml`

Key settings:
- Image: `pgvector/pgvector:pg16`
- Port: `5434:5432`
- Database: `legal_graphrag_local`
- Password: `localdev123`

### scripts/init-legal-db.sql

Located at: `d:\IT workspace\Legal GraphRAG\scripts\init-legal-db.sql`

Automatically runs on first container start. Creates:
- Extensions: vector, uuid-ossp, pg_trgm
- Tables: All legal_* tables
- Indexes: Including HNSW vector index

**Note:** This is a backup. Django migrations should create tables in normal workflow.

### backend/.env

Database configuration variables:
- `LEGAL_DB_NAME`: Database name
- `LEGAL_DB_USER`: Database user
- `LEGAL_DB_PASSWORD`: Database password
- `LEGAL_DB_HOST`: Database host (localhost for local)
- `LEGAL_DB_PORT`: Database port (5434 for local)

---

## Testing the Migration

### 1. Check Database Connection

```bash
cd backend
python manage.py dbshell
```

Should connect to PostgreSQL. Type `\dt` to see tables, `\q` to exit.

### 2. Test Models

```bash
cd backend
python manage.py shell
```

```python
from apps.legal_graphrag.models import CorpusSource, LegalDocument, ChatSession

# Count records
print(f"Sources: {CorpusSource.objects.count()}")
print(f"Documents: {LegalDocument.objects.count()}")
print(f"Sessions: {ChatSession.objects.count()}")

# Test create
source = CorpusSource.objects.create(
    prioridad='P1',
    naturaleza='Test',
    titulo='Test Source',
    id_oficial='TEST-001',
    url_oficial='https://test.com'
)
print(f"Created source: {source}")
source.delete()
```

### 3. Test Vector Search

```bash
cd backend
python manage.py shell
```

```python
from apps.legal_graphrag.models import DocumentChunk
import numpy as np

# Check if pgvector is working
chunk = DocumentChunk.objects.first()
if chunk and chunk.embedding:
    print(f"Embedding dimensions: {len(chunk.embedding)}")
    print("pgvector is working!")
```

---

## Port Summary

| Service | Port | Purpose |
|---------|------|---------|
| PostgreSQL | 5434 | Legal GraphRAG database |
| pgAdmin | 5051 | Database management UI |
| Django | 8000 | Application server |
| Frontend | 3000 | React frontend (if running) |
| Redis | 6379 | Caching (if used) |

---

## Migration Complete Checklist

- [ ] Docker container running (`docker ps`)
- [ ] Database accessible via psql
- [ ] `backend\.env` updated with local settings
- [ ] Django migrations applied (`python manage.py migrate`)
- [ ] Tables created (`\dt` in psql shows legal_* tables)
- [ ] pgAdmin accessible at http://localhost:5051
- [ ] Django application runs (`python manage.py runserver`)
- [ ] Models can read/write (`python manage.py shell` tests pass)
- [ ] No Supabase references in active code

---

## Rollback to Supabase (If Needed)

If something goes wrong and you need to go back to Supabase:

1. Revert `backend\.env`:
   ```env
   LEGAL_DB_NAME=postgres
   LEGAL_DB_USER=postgres.oerjegzospyheojqjrrd
   LEGAL_DB_PASSWORD=E:wyKn!W!xjht48
   LEGAL_DB_HOST=aws-1-eu-west-1.pooler.supabase.com
   LEGAL_DB_PORT=6543
   ```

2. Restart Django:
   ```bash
   cd backend
   python manage.py runserver
   ```

3. Your data in Supabase is unchanged.

---

## Next Steps After Migration

1. **Import Corpus Data**: If you have corpus Excel files, import them
   ```bash
   python manage.py shell
   # Use your ingestion scripts
   ```

2. **Generate Embeddings**: Re-generate embeddings for existing documents
   ```bash
   # Run your embedding generation script
   ```

3. **Test Chat Flow**: End-to-end test of the chat interface

4. **Setup Regular Backups**: Schedule daily backups
   ```bash
   # Add to cron/Task Scheduler
   backup_legal.bat
   ```

5. **Monitor Performance**: Check query performance, optimize indexes if needed

---

## Support

If you encounter issues:

1. Check Docker logs: `docker logs legal-graphrag-postgres`
2. Check Django logs: Terminal where `runserver` is running
3. Test database connection: Use psql commands above
4. Verify .env file: Ensure no typos in connection strings

---

**Created: 2025-12-26**
**Migration Type: Supabase → Local PostgreSQL**
**Status: Ready to execute**
