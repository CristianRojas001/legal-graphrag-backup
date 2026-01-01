# Integration Technical Reference

**Document**: Technical details for ARTISTING → Legal GraphRAG integration
**Created**: 2025-12-27
**Purpose**: Quick reference for implementation decisions and patterns

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  Login   │  │  Chat    │  │  Billing │  │ History │ │
│  │  Signup  │  │  (RAG)   │  │  (Stripe)│  │  (List) │ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │             │              │             │      │
│  ┌────┴─────────────┴──────────────┴─────────────┴────┐ │
│  │         Service Layer (auth/user/chat/billing)     │ │
│  └────────────────────────┬─────────────────────────────┘ │
└──────────────────────────┼─────────────────────────────┘
                           │ HTTPS + JWT
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Backend (Django REST)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │  users/  │  │ billing/ │  │  legal_  │  │  Redis  │ │
│  │  (Auth)  │  │ (Stripe) │  │ graphrag │  │ (Celery)│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬────┘ │
│       │             │              │             │      │
│  ┌────┴─────────────┴──────────────┴─────────────┴────┐ │
│  │            PostgreSQL + pgvector                    │ │
│  └──────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Stripe    │
                    │  (Webhooks) │
                    └─────────────┘
```

---

## 🔐 Authentication Flow

### Registration
```
User → Frontend → POST /api/v1/auth/register
                  {email, password, firstName, lastName}

Backend:
1. Create User (Django default model)
2. Create UserProfile (5 free credits)
3. Generate JWT tokens
4. Return {access, refresh, user}

Frontend:
5. Store tokens in localStorage
6. Store user in AuthContext
7. Redirect to /chat
```

### Login
```
User → Frontend → POST /api/v1/auth/login
                  {email, password}

Backend:
1. Authenticate user
2. Generate JWT tokens
3. Return {access, refresh, user}

Frontend:
4. Store tokens in localStorage
5. Update AuthContext
6. Redirect to /chat
```

### Token Refresh
```
Frontend (auto-refresh):
1. Detect access token expiring soon (<5min)
2. POST /api/v1/auth/token/refresh/ {refresh}
3. Get new access token
4. Update localStorage
```

### Protected API Calls
```
Frontend:
1. Get access token from localStorage
2. Add header: Authorization: Bearer <token>
3. Make request

Backend:
4. JWTAuthentication validates token
5. Sets request.user
6. View checks permissions
```

---

## 💳 Billing & Credits Flow

### Initial State
```
New User:
- UserProfile.credits = 5 (free)
- UserProfile.plan = "free"
- No Subscription record
```

### Subscription Flow
```
1. User → Frontend → Select Plan (Basic/Pro/Enterprise)

2. Frontend → POST /api/v1/billing/create-checkout-session/
              {
                price_id: "price_xxx",
                success_url: "http://localhost:3000/billing/success",
                cancel_url: "http://localhost:3000/billing/cancel"
              }

3. Backend:
   - Get/create Stripe customer
   - Create Stripe checkout session
   - Return {id: "cs_xxx", url: "https://checkout.stripe.com/..."}

4. Frontend:
   - Redirect user to Stripe checkout URL

5. User completes payment on Stripe

6. Stripe → Webhook → POST /api/v1/billing/webhook/
   Event: checkout.session.completed
   {
     customer: "cus_xxx",
     subscription: "sub_xxx",
     ...
   }

7. Backend (webhook handler):
   - Verify webhook signature
   - Create/update Subscription record:
     * tier = "basic" (from metadata)
     * status = "active"
     * stripe_subscription_id = "sub_xxx"
     * current_period_end = timestamp
   - Allocate credits to UserProfile:
     * Basic: +50 credits
     * Professional: +200 credits
     * Enterprise: +1000 credits

8. Stripe redirects user → success_url

9. Frontend (success page):
   - Fetch updated user profile
   - Show "Subscription active! You have X credits"
```

### Credit Deduction Flow
```
User asks RAG question:

1. Frontend → POST /api/v1/legal-graphrag/query/
              Headers: {Authorization: Bearer <token>}
              {query: "..."}

2. Backend (views_v1_1.py):
   a. Authenticate user (JWTAuthentication)
   b. Get user.profile
   c. Check: profile.credits > 0
      - If NO: Return 403 {"error": "No credits remaining"}
   d. Deduct: profile.credits -= 1
   e. Save profile
   f. Execute RAG query
   g. Return {answer, sources, remaining_credits: X}

3. Frontend:
   - Update credits display
   - If credits == 0: Show upgrade modal
```

### Monthly Credit Allocation (Celery Task)
```
Celery Beat Schedule (monthly):

Task: allocate_monthly_credits()

For each active Subscription:
1. Check if current_period_end passed
2. Allocate credits based on tier:
   - Basic: +50
   - Professional: +200
   - Enterprise: +1000
3. Update Subscription.current_period_end (+1 month)
4. Log allocation

Note: First implementation can skip this - handle via Stripe webhooks only
```

---

## 📊 Database Schema

### New Tables

#### users_userprofile
```sql
CREATE TABLE users_userprofile (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE,
    plan VARCHAR(20) DEFAULT 'free',
    credits INTEGER DEFAULT 5
);

-- Signal creates UserProfile automatically when User created
```

#### users_passwordresettoken
```sql
CREATE TABLE users_passwordresettoken (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    token VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    is_used BOOLEAN DEFAULT FALSE
);

-- TTL: 24 hours (handled in view logic)
```

#### billing_subscription
```sql
CREATE TABLE billing_subscription (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    tier VARCHAR(32) DEFAULT 'basic',  -- basic, professional, enterprise
    status VARCHAR(64) DEFAULT 'inactive',  -- active, cancelled, past_due
    current_period_end TIMESTAMP,
    credits INTEGER DEFAULT 0,  -- Optional: track per-subscription
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index on user_id, stripe_subscription_id
```

#### billing_paymentrecord
```sql
CREATE TABLE billing_paymentrecord (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE,
    stripe_event_id VARCHAR(200) UNIQUE NOT NULL,
    stripe_charge_id VARCHAR(200),
    amount INTEGER,  -- cents
    currency VARCHAR(10) DEFAULT 'eur',
    success BOOLEAN DEFAULT FALSE,
    raw_event JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index on user_id, stripe_event_id
```

### Updated Tables

#### legal_graphrag_chatsession
```sql
ALTER TABLE legal_graphrag_chatsession
ADD COLUMN user_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE;

-- Migration: Set existing sessions to admin user
UPDATE legal_graphrag_chatsession
SET user_id = (SELECT id FROM auth_user WHERE is_superuser = TRUE LIMIT 1)
WHERE user_id IS NULL;

-- After migration, make NOT NULL
ALTER TABLE legal_graphrag_chatsession
ALTER COLUMN user_id SET NOT NULL;

-- Add index
CREATE INDEX idx_chatsession_user ON legal_graphrag_chatsession(user_id);
```

---

## 🔌 API Endpoints Reference

### Authentication

#### POST /api/v1/auth/register
```json
Request:
{
  "email": "user@example.com",
  "password": "SecurePass123",
  "first_name": "John",
  "last_name": "Doe"
}

Response: 200 OK
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe"
  }
}
```

#### POST /api/v1/auth/login
```json
Request:
{
  "email": "user@example.com",
  "password": "SecurePass123"
}

Response: 200 OK
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe"
  }
}

Error: 401 Unauthorized
{
  "detail": "Invalid credentials"
}
```

#### POST /api/v1/auth/token/refresh/
```json
Request:
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response: 200 OK
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

#### GET /api/v1/auth/me
```json
Headers:
Authorization: Bearer <access_token>

Response: 200 OK
{
  "id": 1,
  "email": "user@example.com",
  "firstName": "John",
  "lastName": "Doe",
  "profile": {
    "plan": "professional",
    "credits": 150
  }
}
```

#### POST /api/v1/auth/logout/
```json
Request:
{
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}

Response: 200 OK
{
  "message": "Logout successful"
}
```

### Billing

#### POST /api/v1/billing/create-checkout-session/
```json
Request:
Headers: {Authorization: Bearer <token>}
{
  "price_id": "price_xxx",  // Stripe Price ID
  "success_url": "http://localhost:3000/billing/success",
  "cancel_url": "http://localhost:3000/billing/cancel"
}

Response: 200 OK
{
  "id": "cs_xxx",
  "url": "https://checkout.stripe.com/c/pay/cs_xxx"
}
```

#### POST /api/v1/billing/webhook/
```json
Headers:
Stripe-Signature: t=xxx,v1=xxx

Request: (Stripe event object)
{
  "id": "evt_xxx",
  "type": "checkout.session.completed",
  "data": {
    "object": {
      "customer": "cus_xxx",
      "subscription": "sub_xxx",
      ...
    }
  }
}

Response: 200 OK
{
  "status": "success"
}
```

#### GET /api/v1/billing/subscription/status/
```json
Headers: {Authorization: Bearer <token>}

Response: 200 OK
{
  "tier": "professional",
  "status": "active",
  "current_period_end": "2026-02-27T00:00:00Z",
  "stripe_subscription_id": "sub_xxx"
}
```

### Legal GraphRAG (Updated)

#### POST /api/v1/legal-graphrag/query/
```json
Request:
Headers: {Authorization: Bearer <token>}
{
  "query": "¿Qué es el IVA?",
  "session_id": "uuid-xxx"  // Optional
}

Response: 200 OK
{
  "answer": "El IVA es...",
  "sources": [...],
  "session_id": "uuid-xxx",
  "remaining_credits": 149,
  "metadata": {...}
}

Error: 403 Forbidden (no credits)
{
  "error": "You have 0 credits left. Please upgrade your plan."
}

Error: 401 Unauthorized (no auth)
{
  "detail": "Authentication credentials were not provided."
}
```

#### GET /api/v1/legal-graphrag/sessions/
```json
Request:
Headers: {Authorization: Bearer <token>}

Response: 200 OK
{
  "sessions": [
    {
      "id": "uuid-1",
      "title": "¿Qué es el IVA?",
      "created_at": "2025-12-27T10:00:00Z",
      "updated_at": "2025-12-27T10:15:00Z",
      "message_count": 5
    },
    ...
  ],
  "total": 10,
  "credits": 149
}
```

#### GET /api/v1/legal-graphrag/sessions/{id}/
```json
Request:
Headers: {Authorization: Bearer <token>}

Response: 200 OK
{
  "session": {
    "id": "uuid-1",
    "title": "¿Qué es el IVA?",
    "created_at": "2025-12-27T10:00:00Z",
    "message_count": 5
  },
  "messages": [
    {
      "role": "user",
      "content": "¿Qué es el IVA?",
      "created_at": "2025-12-27T10:00:00Z"
    },
    {
      "role": "assistant",
      "content": "El IVA es...",
      "sources": [...],
      "created_at": "2025-12-27T10:00:05Z"
    },
    ...
  ]
}
```

---

## 🎨 Frontend Service Architecture

### Base Service Pattern
```typescript
// lib/services/base.service.ts
class BaseApiService {
  protected baseURL: string;

  protected async request<T>(
    endpoint: string,
    options?: RequestInit
  ): Promise<T> {
    const token = this.getToken();
    const headers = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options?.headers,
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      // Token expired, try refresh
      await this.refreshToken();
      // Retry request
    }

    return response.json();
  }
}
```

### Auth Service
```typescript
// lib/services/auth.service.ts
class AuthService extends BaseApiService {
  async login(email: string, password: string) {
    const data = await this.post('/api/v1/auth/login', {
      email,
      password,
    });

    this.setToken(data.access);
    this.setRefreshToken(data.refresh);
    this.setUser(data.user);

    return data;
  }

  async register(userData: RegisterData) {
    const data = await this.post('/api/v1/auth/register', userData);

    this.setToken(data.access);
    this.setRefreshToken(data.refresh);
    this.setUser(data.user);

    return data;
  }

  async refreshToken() {
    const refresh = this.getRefreshToken();
    const data = await this.post('/api/v1/auth/token/refresh/', {
      refresh,
    });

    this.setToken(data.access);
    return data;
  }
}

export const authService = new AuthService();
```

### Usage in Components
```typescript
// app/login/page.tsx
'use client';

import { authService } from '@/lib/services';
import { useAuth } from '@/contexts/auth-context';

export default function LoginPage() {
  const { login } = useAuth();

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    try {
      const data = await authService.login(email, password);
      login(data.user, data.access);
      router.push('/chat');
    } catch (error) {
      toast.error('Invalid credentials');
    }
  };

  return <form onSubmit={handleSubmit}>...</form>;
}
```

---

## 🔒 Security Considerations

### Backend
1. **JWT Token Security**
   - Access token: 12 hours (short-lived)
   - Refresh token: 7 days (stored securely)
   - HTTPS only in production

2. **Stripe Webhook Validation**
   ```python
   # Verify webhook signature
   sig = request.META.get('HTTP_STRIPE_SIGNATURE')
   event = stripe.Webhook.construct_event(
       payload, sig, settings.STRIPE_WEBHOOK_SECRET
   )
   ```

3. **CORS Configuration**
   ```python
   CORS_ALLOWED_ORIGINS = [
       "http://localhost:3000",
       "https://yourdomain.com",
   ]
   ```

4. **Rate Limiting** (TODO)
   - Implement rate limiting on auth endpoints
   - Prevent brute force attacks

### Frontend
1. **Token Storage**
   - localStorage (acceptable for non-critical apps)
   - Consider httpOnly cookies for production

2. **XSS Protection**
   - Sanitize user input
   - Use React's built-in escaping

3. **CSRF Protection**
   - JWT tokens don't need CSRF (stateless)
   - Stripe checkout uses secure redirect

---

## 📈 Performance Optimizations

### Backend
1. **Database Indexes**
   ```sql
   CREATE INDEX idx_chatsession_user ON legal_graphrag_chatsession(user_id);
   CREATE INDEX idx_subscription_user ON billing_subscription(user_id);
   CREATE INDEX idx_subscription_stripe ON billing_subscription(stripe_subscription_id);
   ```

2. **Query Optimization**
   - Use `select_related('user', 'user__profile')` to avoid N+1
   - Cache user profile in request for multiple accesses

3. **Redis Caching** (Optional)
   - Cache user profile (5 min TTL)
   - Cache subscription status (10 min TTL)

### Frontend
1. **Code Splitting**
   - Lazy load billing pages (most users won't access)
   - Lazy load history page

2. **Data Caching**
   - Cache user profile in React Context
   - Invalidate on credit change

3. **Optimistic Updates**
   - Decrement credits immediately in UI
   - Rollback on error

---

## 🐛 Common Issues & Solutions

### Issue: Webhook not receiving events
**Solution**:
- Verify webhook URL is publicly accessible (use ngrok for local dev)
- Check Stripe dashboard for failed webhook attempts
- Verify webhook secret matches

### Issue: Token expired mid-session
**Solution**:
- Implement auto-refresh in axios/fetch interceptor
- Refresh token when access token <5min from expiry

### Issue: Credits not deducted
**Solution**:
- Check transaction isolation level
- Ensure save() called after decrement
- Add logging to track credit changes

### Issue: User sees old credit count
**Solution**:
- Return updated credits in RAG response
- Update AuthContext immediately
- Add polling/websocket for real-time updates (advanced)

---

## 📝 Migration Script Example

```python
# Migration: Link existing ChatSessions to default user

from django.db import migrations
from django.contrib.auth import get_user_model

def link_sessions_to_admin(apps, schema_editor):
    User = get_user_model()
    ChatSession = apps.get_model('legal_graphrag', 'ChatSession')

    # Get or create default admin user
    admin_user, _ = User.objects.get_or_create(
        email='admin@legalgraphrag.com',
        defaults={
            'username': 'admin',
            'is_staff': True,
            'is_superuser': True,
        }
    )

    # Link all orphaned sessions
    ChatSession.objects.filter(user__isnull=True).update(user=admin_user)

class Migration(migrations.Migration):
    dependencies = [
        ('legal_graphrag', '0005_add_fts_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatsession',
            name='user',
            field=models.ForeignKey(
                'auth.User',
                on_delete=models.CASCADE,
                null=True,
                blank=True
            ),
        ),
        migrations.RunPython(link_sessions_to_admin),
        migrations.AlterField(
            model_name='chatsession',
            name='user',
            field=models.ForeignKey(
                'auth.User',
                on_delete=models.CASCADE,
                null=False,
                blank=False
            ),
        ),
    ]
```

---

## 🎯 Testing Strategy

### Unit Tests
- Test credit deduction logic
- Test subscription status checks
- Test token generation/validation

### Integration Tests
- Test full auth flow (register → login → refresh)
- Test full billing flow (checkout → webhook → credits)
- Test RAG query with credit deduction

### E2E Tests (Manual)
1. New user signup
2. Receive 5 free credits
3. Ask 5 RAG questions
4. Credits = 0, query blocked
5. Subscribe to Basic plan
6. Receive 50 credits
7. Continue chatting
8. View history
9. Cancel subscription

---

**Document Version**: 1.0
**Last Updated**: 2025-12-27
**Maintained By**: Integration Team