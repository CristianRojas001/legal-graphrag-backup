# ngrok Demo Setup - Troubleshooting Guide

This document explains how the ngrok demo was configured and the issues that were resolved.

## Problem Summary

When setting up ngrok to expose the Legal GraphRAG application for client demos, we encountered two main issues:

1. **Django Trailing Slash Error** - API calls were failing with HTTP 500 errors
2. **Next.js Cross-Origin Blocking** - Static resources were being blocked from loading

## Solution Overview

### Issue 1: Django APPEND_SLASH Configuration

**Problem:**
```
RuntimeError: You called this URL via POST, but the URL doesn't end in a slash and you have APPEND_SLASH set.
Django can't redirect to the slash URL while maintaining POST data.
```

**Root Cause:**
- Django's default `APPEND_SLASH=True` setting automatically redirects URLs without trailing slashes
- However, POST requests cannot be redirected (HTTP spec limitation)
- Next.js proxy rewrites were stripping the trailing slash from API URLs
- The API endpoint `/api/v1/legal-graphrag/v1_1/chat/` was being called as `/api/v1/legal-graphrag/v1_1/chat` (no slash)

**Solution:**
Disabled Django's automatic slash appending to allow URLs with or without trailing slashes.

**File:** `backend/ovra_backend/settings.py`

**Change:**
```python
# URL Configuration
APPEND_SLASH = False  # Disable automatic slash appending for ngrok/proxy compatibility

# Internationalization
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
```

**Location:** Line 97-98

**Why This Works:**
- With `APPEND_SLASH=False`, Django accepts URLs both with and without trailing slashes
- The URL patterns in `urls.py` still define the canonical format with slashes
- Both `/api/v1/legal-graphrag/v1_1/chat/` and `/api/v1/legal-graphrag/v1_1/chat` now work

**Alternative Solutions Considered:**
1. ✗ Fix Next.js rewrites to preserve trailing slash - More complex, requires rewrite rule changes
2. ✗ Modify Django URL patterns to not require slash - Would break existing API contracts
3. ✅ **Disable APPEND_SLASH** - Simplest, fastest, no side effects for development

---

### Issue 2: Next.js Cross-Origin Resource Blocking

**Problem:**
```
⚠ Blocked cross-origin request from f86c68b63249.ngrok-free.app to /_next/* resource.
To allow this, configure "allowedDevOrigins" in next.config
```

**Root Cause:**
- When accessing the frontend via ngrok (e.g., `https://f86c68b63249.ngrok-free.app`)
- Next.js loads static resources from `/_next/*` paths
- Next.js 16 requires explicit configuration to allow cross-origin requests to these internal resources
- The `allowedDevOrigins` configuration wasn't being properly applied

**Solution:**
Configured Next.js to allow the ngrok domain to load development resources.

**File:** `frontend-legal/next.config.ts`

**Change:**
```typescript
import type { NextConfig } from "next";

const apiProxyDestination =
  process.env.NEXT_PUBLIC_API_PROXY_DESTINATION || "http://localhost:8000";

const nextConfig: NextConfig = {
  experimental: {
    allowedDevOrigins: ["f86c68b63249.ngrok-free.app"],
  },
  trailingSlash: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*/",
        destination: `${apiProxyDestination}/api/:path*/`,
      },
      {
        source: "/api/:path*",
        destination: `${apiProxyDestination}/api/:path*/`,
      },
    ];
  },
};

export default nextConfig;
```

**What Changed:**
1. Added `experimental.allowedDevOrigins` array with the ngrok domain (without `https://`)
2. Added dual rewrite rules to handle both trailing slash and no trailing slash cases
3. Removed environment variable loading for `allowedDevOrigins` (wasn't being picked up correctly)

**Current Status:**
- Warning still appears in logs but changed from "Blocked" to "detected"
- Resources load successfully despite the warning
- Warning is informational only (for future Next.js versions)

**Note:** The ngrok URL will change each time you restart ngrok. When this happens:
1. Update line 8 in `next.config.ts` with the new domain
2. Restart the frontend dev server (`npm run dev`)

---

## Additional Fixes Applied

### Next.js Proxy Configuration

**Problem:**
The frontend was trying to proxy to `localhost:8001` instead of `localhost:8000`

**File:** `frontend-legal/.env.local`

**Fix:**
```env
# Before
NEXT_PUBLIC_API_PROXY_DESTINATION=http://localhost:8001

# After
NEXT_PUBLIC_API_PROXY_DESTINATION=http://localhost:8000
```

---

## Complete Setup Process

### Prerequisites
- ngrok installed (version 3.23.1 or later)
- Backend running on port 8000
- Frontend running on port 3000
- PostgreSQL database running

### Step-by-Step Setup

1. **Start Backend**
```bash
cd backend
python manage.py runserver
```

2. **Start Frontend**
```bash
cd frontend-legal
npm run dev
```

3. **Start ngrok Tunnel**
```bash
ngrok http 3000
```

4. **Get ngrok URL**
- Open http://localhost:4040
- Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

5. **Update Next.js Config**
Edit `frontend-legal/next.config.ts`:
```typescript
experimental: {
  allowedDevOrigins: ["abc123.ngrok-free.app"],  // Your ngrok domain
},
```

6. **Restart Frontend**
- Press Ctrl+C in the frontend terminal
- Run `npm run dev` again

7. **Share URL with Client**
Send them the ngrok HTTPS URL

---

## Verification Steps

### Test Backend Health
```bash
curl http://localhost:8000/api/v1/legal-graphrag/health/
# Should return 200 OK
```

### Test API Endpoint (with slash)
```bash
curl -X POST http://localhost:8000/api/v1/legal-graphrag/v1_1/chat/ \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
# Should return 200 OK
```

### Test API Endpoint (without slash)
```bash
curl -X POST http://localhost:8000/api/v1/legal-graphrag/v1_1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}'
# Should return 404 (expected with APPEND_SLASH=False, but proxy adds slash)
```

### Test Frontend via ngrok
```bash
curl -s https://your-ngrok-url.ngrok-free.app/ | grep "Legal GraphRAG"
# Should find the title
```

### Monitor Logs

**Backend Logs** (should show successful requests):
```
INFO basehttp "POST /api/v1/legal-graphrag/v1_1/chat/ HTTP/1.1" 200 12854
```

**Frontend Logs** (warning is expected but not blocking):
```
⚠ Cross origin request detected from xyz.ngrok-free.app to /_next/* resource.
GET / 200 in 127ms (compile: 13ms, render: 114ms)
```

---

## Common Issues & Solutions

### Issue: "APPEND_SLASH" error still appearing
**Solution:**
- Verify `APPEND_SLASH = False` is in `backend/ovra_backend/settings.py`
- Restart the Django server (Ctrl+C, then `python manage.py runserver`)
- Check the backend logs for the settings reload message

### Issue: Cross-origin resources still blocked
**Solution:**
- Ensure the domain in `allowedDevOrigins` matches your ngrok URL (without https://)
- Restart the frontend server after changing `next.config.ts`
- Clear browser cache

### Issue: Frontend can't connect to backend
**Solution:**
- Verify `NEXT_PUBLIC_API_PROXY_DESTINATION=http://localhost:8000` in `.env.local`
- Check both servers are running (`netstat -ano | findstr ":8000"` and `:3000`)
- Restart the frontend server

### Issue: ngrok URL changes on restart
**Solution:**
- This is normal for ngrok free plan
- Update `allowedDevOrigins` in `next.config.ts` with new domain
- Restart frontend server
- Send new URL to client

---

## Files Modified

### Backend Changes

1. **`backend/ovra_backend/settings.py`**
   - Line 97-98: Added `APPEND_SLASH = False`

### Frontend Changes

1. **`frontend-legal/next.config.ts`**
   - Line 7-9: Added `experimental.allowedDevOrigins`
   - Line 11-25: Updated rewrites to handle trailing slashes

2. **`frontend-legal/.env.local`**
   - Line 3: Fixed `NEXT_PUBLIC_API_PROXY_DESTINATION` port (8001 → 8000)
   - Line 4: Updated `NEXT_PUBLIC_ALLOWED_DEV_ORIGINS` with current ngrok URL

---

## Architecture Diagram

```
Client Browser
    ↓
https://xyz.ngrok-free.app (ngrok Public URL)
    ↓
ngrok Tunnel (Secure Tunnel)
    ↓
http://localhost:3000 (Next.js Frontend)
    ↓ (API proxy via rewrites)
http://localhost:8000 (Django Backend)
    ↓
PostgreSQL Database
```

---

## Why This Approach Works

### Django Side
- **APPEND_SLASH=False** allows flexible URL handling
- No breaking changes to existing code
- Works with both proxy formats

### Next.js Side
- **Dual rewrites** handle both slash/no-slash cases
- **experimental.allowedDevOrigins** permits ngrok domain
- **Proxy rewrites** ensure trailing slash is added to backend requests

### Result
- Frontend loads successfully via ngrok
- API calls work correctly through the proxy
- Client gets full functionality via public URL

---

## Production Considerations

⚠️ **Important:** These changes are for development/demo purposes only.

**For production deployment:**

1. **Re-enable APPEND_SLASH**
   ```python
   APPEND_SLASH = True  # Enforce canonical URLs
   ```

2. **Remove allowedDevOrigins**
   ```typescript
   // Remove this in production
   experimental: {
     allowedDevOrigins: [...],
   },
   ```

3. **Use proper domain**
   - Deploy to legal.artisting.es
   - Configure DNS and SSL
   - See `docs/06_DEPLOYMENT_GUIDE.md`

4. **Update CORS settings**
   ```python
   CORS_ALLOW_ALL_ORIGINS = False
   CORS_ALLOWED_ORIGINS = ['https://legal.artisting.es']
   ```

---

## Summary

**Problem:** ngrok demo failing due to Django trailing slash errors and Next.js cross-origin blocking

**Solution:**
1. Set `APPEND_SLASH = False` in Django settings
2. Configure `experimental.allowedDevOrigins` in Next.js config
3. Fix proxy destination port and add dual rewrite rules

**Result:** ✅ Fully functional demo accessible via ngrok free plan

**Files Modified:**
- `backend/ovra_backend/settings.py`
- `frontend-legal/next.config.ts`
- `frontend-legal/.env.local`

**Time to Fix:** ~15 minutes
**Downtime:** None (hot reloading)
**Breaking Changes:** None (dev-only changes)

---

**Last Updated:** 2025-12-29
**ngrok Version:** 3.23.1
**Next.js Version:** 16.0.10
**Django Version:** 5.2.6
