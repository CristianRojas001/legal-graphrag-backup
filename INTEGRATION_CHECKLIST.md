# Integration Checklist - Quick Reference

**Status**: 🔴 NOT STARTED | 🟡 IN PROGRESS | 🟢 COMPLETE

---

## 🎯 Pre-Flight

- [ ] Redis running (✅ CONFIRMED)
- [ ] Stripe test account created
- [ ] Git branch created: `feature/artisting-integration`
- [ ] Backup current state committed

---

## 📦 Backend Apps to Copy

- [ ] `users/` → Copy entire app
- [ ] `billing/` → Copy (remove UserSubscription model)
- [ ] ~~`chat/`~~ → SKIP (we have better models)
- [ ] `metrics/` → OPTIONAL (add later)
- [ ] `semantic_cache/` → OPTIONAL (add later)

---

## 🔧 Backend Configuration

### Dependencies Added
- [ ] `djangorestframework-simplejwt==5.5.1`
- [ ] `stripe`

### settings.py Updates
- [ ] Add `'users'` to INSTALLED_APPS
- [ ] Add `'billing'` to INSTALLED_APPS
- [ ] Add `'rest_framework_simplejwt'` to INSTALLED_APPS
- [ ] Configure REST_FRAMEWORK authentication
- [ ] Add SIMPLE_JWT settings
- [ ] Add Stripe configuration
- [ ] Add EMAIL configuration

### URL Configuration
- [ ] `/api/v1/auth/register`
- [ ] `/api/v1/auth/token/refresh/`
- [ ] `/api/v1/auth/logout/`
- [ ] `/api/v1/auth/me`
- [ ] `/api/v1/billing/create-checkout-session/`
- [ ] `/api/v1/billing/webhook/`

### Database Migrations
- [ ] `python manage.py makemigrations users`
- [ ] `python manage.py migrate users`
- [ ] `python manage.py makemigrations billing`
- [ ] `python manage.py migrate billing`
- [ ] Add `user` FK to `ChatSession`
- [ ] Migrate existing sessions to default user

---

## 🎨 Frontend Files to Copy

### Service Layer
- [ ] `lib/services/base.service.ts`
- [ ] `lib/services/auth.service.ts`
- [ ] `lib/services/user.service.ts`
- [ ] `lib/services/config.ts`
- [ ] `lib/services/index.ts`

### Context
- [ ] `contexts/auth-context.tsx`

### Pages
- [ ] `app/login/page.tsx`
- [ ] `app/signup/page.tsx`
- [ ] `app/account/page.tsx`
- [ ] `app/billing/page.tsx`
- [ ] `app/pricing/page.tsx`
- [ ] `app/history/page.tsx`
- [ ] `app/billing/success/page.tsx`
- [ ] `app/billing/cancel/page.tsx`

### Components
- [ ] `components/ui/button.tsx`
- [ ] `components/ui/input.tsx`
- [ ] `components/ui/label.tsx`
- [ ] `components/ui/card.tsx`
- [ ] `components/ui/dialog.tsx`
- [ ] `components/ui/toast.tsx`
- [ ] `components/ui/dropdown-menu.tsx`
- [ ] `components/protected-route.tsx`
- [ ] `components/shared-header.tsx`
- [ ] `components/shared-footer.tsx`

### Dependencies
- [ ] `@radix-ui/react-avatar`
- [ ] `@radix-ui/react-dialog`
- [ ] `@radix-ui/react-dropdown-menu`
- [ ] `@radix-ui/react-label`
- [ ] `@radix-ui/react-toast`
- [ ] `react-hook-form`
- [ ] `zod`
- [ ] `class-variance-authority`
- [ ] `clsx`
- [ ] `tailwind-merge`
- [ ] `lucide-react`
- [ ] `next-themes`
- [ ] `react-hot-toast`
- [ ] `@stripe/stripe-js`

---

## 🔐 Environment Variables

### Backend (.env)
```bash
# Existing
DJANGO_SECRET_KEY=...
DEBUG=True
LEGAL_DB_NAME=...
LEGAL_DB_USER=...
LEGAL_DB_PASSWORD=...

# NEW - Add these
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
FRONTEND_SUCCESS_URL=http://localhost:3000/billing/success
FRONTEND_CANCEL_URL=http://localhost:3000/billing/cancel

# Email (for password reset)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
```

---

## 🧪 Testing Checklist

### Backend Tests
- [ ] Register new user → Returns JWT tokens
- [ ] Login → Returns access + refresh tokens
- [ ] Token refresh → Returns new access token
- [ ] Protected endpoint with valid token → 200 OK
- [ ] Protected endpoint without token → 401 Unauthorized
- [ ] Credit deduction → Profile.credits decrements
- [ ] Zero credits → Query blocked with error
- [ ] Stripe checkout → Session created
- [ ] Stripe webhook → Subscription updated

### Frontend Tests
- [ ] Signup form → User created, tokens stored
- [ ] Login form → Tokens stored, redirects to chat
- [ ] Logout → Tokens cleared, redirects to login
- [ ] Protected route without auth → Redirects to login
- [ ] Chat with auth → Shows user info and credits
- [ ] Credit display → Updates after query
- [ ] Zero credits → Shows upgrade modal
- [ ] Billing page → Shows subscription status
- [ ] Checkout flow → Redirects to Stripe, returns with success
- [ ] History page → Shows past conversations

### Integration Tests
- [ ] Full user journey (signup → chat → subscribe → chat more → view history)

---

## 🎨 Branding Updates

- [ ] Replace logo (ARTISTING → Legal GraphRAG)
- [ ] Update site title
- [ ] Update metadata (description, OG tags)
- [ ] Update color scheme (if needed)
- [ ] Update footer links
- [ ] Update privacy/terms pages

---

## 📚 Documentation

- [ ] Update README.md with new features
- [ ] Document environment variables
- [ ] Create user guide (signup, billing, credits)
- [ ] Create deployment guide
- [ ] Create admin guide (grant credits, manage users)

---

## 🚀 Production Prep

- [ ] Production Stripe account configured
- [ ] Real payment tested
- [ ] Webhooks configured for production domain
- [ ] HTTPS enabled
- [ ] CORS configured for production domain
- [ ] Database backed up before migration
- [ ] Monitoring/logging configured
- [ ] Error tracking setup (Sentry)

---

## 📊 Progress Tracker

**Overall Progress**: 0% (0/8 milestones)

- [ ] Milestone 1: Backend Auth (Day 1)
- [ ] Milestone 2: Backend Billing (Day 2)
- [ ] Milestone 3: Backend Credits (Day 3)
- [ ] Milestone 4: Frontend Services (Day 4)
- [ ] Milestone 5: Frontend Auth Pages (Day 5)
- [ ] Milestone 6: Frontend Billing (Day 6)
- [ ] Milestone 7: Chat History (Day 7)
- [ ] Milestone 8: Integration & Polish (Days 8-10)

---

**Last Updated**: 2025-12-27
**Next Action**: Start Day 1 - Copy users app