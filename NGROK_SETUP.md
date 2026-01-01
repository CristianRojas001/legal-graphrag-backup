# ngrok Setup for Client Demo

This guide helps you expose your Legal GraphRAG project to clients using ngrok's free plan.

Status: Closed - frontend and backend confirmed working.

## Prerequisites

✅ ngrok is already installed (version 3.23.1)
- Backend should be running on port 8000
- Frontend should be running on port 3001

## Quick Start

### Step 1: Start Your Services

**Terminal 1 - Backend:**
```bash
cd backend
python manage.py runserver
```

**Terminal 2 - Frontend:**
```bash
cd frontend-legal
npm run dev
```

### Step 2: Start ngrok Tunnels

**Option A - Automated (Recommended):**
```bash
# Double-click or run:
start-ngrok.bat
```

**Option B - Manual:**

**Terminal 3 - Backend Tunnel:**
```bash
ngrok http 8000
```

**Terminal 4 - Frontend Tunnel:**
```bash
ngrok http 3001
```

### Step 3: Get Your Public URLs

1. Open the ngrok dashboard: http://localhost:4040
2. You'll see both tunnels with their public URLs:
   - **Backend**: `https://xxxx-xxx-xxx-xxx-xxx.ngrok-free.app` (port 8000)
   - **Frontend**: `https://yyyy-yyy-yyy-yyy-yyy.ngrok-free.app` (port 3001)

### Step 4: Configure Frontend to Use ngrok Backend

1. Edit `frontend-legal/.env.local`:
```env
NEXT_PUBLIC_API_URL=https://xxxx-xxx-xxx-xxx-xxx.ngrok-free.app
```

2. Restart your frontend development server (Ctrl+C then `npm run dev`)

### Step 5: Share with Client

Send your client the **Frontend ngrok URL**:
```
https://yyyy-yyy-yyy-yyy-yyy.ngrok-free.app
```

## Important Notes

### ngrok Free Plan Limitations
- ⚠️ **URLs change on restart**: Each time you restart ngrok, you get new URLs
- ⚠️ **Session timeout**: Free tunnels expire after 2 hours
- ⚠️ **Warning page**: Visitors see an ngrok warning page first (click "Visit Site")
- ✅ **No account required**: Works without login (with limitations)
- ✅ **HTTPS included**: All tunnels are automatically HTTPS

### Tips for Client Demo

1. **Before the demo:**
   - Start all services 10 minutes early
   - Test the ngrok URLs yourself first
   - Warn client about the ngrok warning page

2. **During the demo:**
   - Keep terminal windows open (don't close them)
   - Monitor the ngrok dashboard for requests
   - Have backend logs visible to debug issues

3. **If URLs change:**
   - Update `frontend-legal/.env.local` with new backend URL
   - Restart frontend server
   - Send new frontend URL to client

## Troubleshooting

### Frontend can't connect to backend
```bash
# Check backend ngrok URL in frontend config
cat frontend-legal/.env.local

# Should show:
# NEXT_PUBLIC_API_URL=https://xxxx-xxx-xxx-xxx-xxx.ngrok-free.app
```

### CORS errors
The Django backend should already have CORS configured. If you see CORS errors, check `backend/ovra_backend/settings.py`:

```python
CORS_ALLOW_ALL_ORIGINS = True  # Or configure specific origins
```

### ngrok tunnel not accessible
```bash
# Check if services are running
netstat -ano | findstr ":8000"  # Backend
netstat -ano | findstr ":3001"  # Frontend

# Restart ngrok if needed
# Close existing ngrok windows and run start-ngrok.bat again
```

## Alternative: ngrok Config File (Advanced)

If you want both tunnels in one command, create `ngrok.yml`:

```yaml
version: "2"
authtoken: YOUR_AUTH_TOKEN  # Optional, get from https://dashboard.ngrok.com
tunnels:
  backend:
    proto: http
    addr: 8000
  frontend:
    proto: http
    addr: 3001
```

Then start with:
```bash
ngrok start --all
```

## Production Deployment

For a permanent solution, see [docs/06_DEPLOYMENT_GUIDE.md](docs/06_DEPLOYMENT_GUIDE.md) for Digital Ocean deployment.

---

**Need help?** Check ngrok documentation: https://ngrok.com/docs
