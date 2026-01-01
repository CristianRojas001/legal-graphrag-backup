# Architecture Overview (Template)

> Document the system “shape” so contributors and assistants can reason about changes quickly. Update whenever stack or contracts change.

## 1. Stack Decisions
- **Frontend**: _Framework (e.g., Next.js 16 + TypeScript + Tailwind) + state mgmt + component kit._
- **Backend**: _Django 5 + DRF + Celery + Redis broker._
- **Database**: _PostgreSQL (prod) / SQLite (dev/tests). Mention pgvector usage if applicable._
- **Search/Retrieval**: _OpenSearch index + helper services._
- **LLM/Embeddings**: _Provider, versions, token budgets._
- **Deployment**: _Containerization, hosting platform, CI/CD pipeline._

## 2. High-level Diagram
_Describe or sketch data flow: web client → API → retrieval → LLM → response. Include billing + metrics paths._

## 3. Modules & Responsibilities
| Module | Path | Responsibility | Notes |
|--------|------|---------------|-------|
| Web UI | `frontend/app/*` | _Pages, components, contexts._ | _SSR/CSR strategy, theming._ |
| API | `backend/` | _Auth, chat, billing, ingestion._ | _List key apps and signals._ |
| Retrieval | `backend/boe`, `backend/apps/agent` | _Ingestion, search, reranking, reasoning._ | _Celery schedule, caching._ |
| Billing | `backend/billing`, `frontend/lib/services/billing` | _Subscriptions, Stripe hooks._ | |
| Metrics | `backend/metrics`, `frontend/app/analytics` | _Logging, dashboards._ | |

## 4. Data Model Snapshot
Describe primary entities (Users, ChatLog, Subscription, SemanticCacheEntry, BOEDocument, etc.) with fields + relationships. Include diagrams if available.

## 5. API Surface
| Endpoint | Method | Purpose | Auth | Verification |
|----------|--------|---------|------|--------------|
| `/api/v1/health/` | GET | _Service readiness._ | Public | `curl ...` |
| `/api/v1/auth/login/` | POST | _JWT login._ | Public | `pytest users/tests` |
| `/api/v1/chat/stream/` | POST (SSE) | _RAG chat streaming._ | JWT | _Manual SSE test script._ |
| `/api/v1/billing/create-checkout-session/` | POST | _Stripe checkout._ | JWT | _Stripe CLI test event._ |
| _Add others._ | | | | |

## 6. RAG Pipeline Summary
Reference `docs/RAG_PIPELINE_TEMPLATE.md` (or final doc) and summarize ingestion cadence, retrieval ranking, LLM prompt construction, validation, caching.

## 7. Environment & Config
- **Env files**: `.env.example`, deployment secrets.
- **Key variables**: `_DJANGO_SECRET_KEY, DATABASE_URL, REDIS_URL, STRIPE_*_, DEEPSEEK_*_`.
- **Service dependencies**: _Redis host, OpenSearch endpoint, Celery worker count._

## 8. Observability & Operations
- **Logging**: _Format, destinations, log levels per service._
- **Metrics/dashboards**: _Prometheus endpoints, Grafana panels._
- **Alerting**: _Triggers, paging policy._

## 9. Future Considerations / ADRs
- _List pending architecture decisions or link to ADR files._
