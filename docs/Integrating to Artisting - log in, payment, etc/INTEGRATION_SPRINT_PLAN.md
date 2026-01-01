# Legal GraphRAG + ARTISTING Integration Sprint Plan

**Project**: Integrate Authentication, Billing, and Chat History from ARTISTING into Legal GraphRAG
**Duration**: 8-10 days
**Start Date**: 2025-12-27
**Target Completion**: 2026-01-06

---

## 🎯 Sprint Goals

1. ✅ User authentication (login/signup/logout) working end-to-end
2. ✅ Billing integration with Stripe (subscriptions + credits)
3. ✅ Chat history linked to authenticated users
4. ✅ RAG queries protected and credit-tracked
5. ✅ Frontend UI complete with ARTISTING branding

---

## 📋 Pre-Flight Checklist

- [x] Redis running locally (confirmed)
- [ ] Stripe test account created
- [ ] Environment variables documented
- [ ] Backup current working state (git commit)
- [ ] Development branch created (`feature/artisting-integration`)

---

## 🗓️ Day-by-Day Sprint Plan

---

### **DAY 1: Backend Foundation - Users & Auth** (2025-12-27)

**Goal**: Get user registration and login working with JWT tokens

#### Tasks:
1. **Copy users app** (1h)
   - [ ] Copy `ARTISTING-main/backend/users/` → `Legal GraphRAG/backend/apps/users/`
   - [ ] Review models: `UserProfile`, `PasswordResetToken`
   - [ ] Review views: `RegisterView`, `LoginView`, `logout_view`, `me_view`

2. **Install dependencies** (15min)
   - [ ] Add to `requirements.txt`:
     ```txt
     djangorestframework-simplejwt==5.5.1
     stripe
     ```
   - [ ] Run `pip install -r requirements.txt`

3. **Update Django settings** (30min)
   - [ ] Add `'users'` to `INSTALLED_APPS`
   - [ ] Add `'rest_framework_simplejwt'` to `INSTALLED_APPS`
   - [ ] Configure `REST_FRAMEWORK` authentication classes
   - [ ] Add `SIMPLE_JWT` settings (12h access, 7d refresh)
   - [ ] Add EMAIL settings for password reset

4. **Update URLs** (15min)
   - [ ] Add auth endpoints to `ovra_backend/urls.py`:
     - `/api/v1/auth/register`
     - `/api/v1/auth/token/refresh/`
     - `/api/v1/auth/logout/`
     - `/api/v1/auth/me`

5. **Create migrations** (15min)
   - [ ] Run `python manage.py makemigrations users`
   - [ ] Run `python manage.py migrate users`
   - [ ] Verify tables created: `users_userprofile`, `users_passwordresettoken`

6. **Test authentication** (30min)
   - [ ] Test registration: `POST /api/v1/auth/register`
   - [ ] Test login: Returns JWT access + refresh tokens
   - [ ] Test token refresh: `POST /api/v1/auth/token/refresh/`
   - [ ] Test `/api/v1/auth/me` with Bearer token

**Deliverable**: Working JWT authentication API
**Success Criteria**: Can register, login, and get user profile via API

---

### **DAY 2: Backend - Billing Integration** (2025-12-28)

**Goal**: Stripe checkout and subscription management working

#### Tasks:
1. **Setup Stripe account** (30min)
   - [ ] Create Stripe test account at stripe.com
   - [ ] Get test API keys (pk_test_..., sk_test_...)
   - [ ] Create 3 products in Stripe dashboard:
     - Basic (€9.99/month, 50 credits/month)
     - Professional (€29.99/month, 200 credits/month)
     - Enterprise (€99.99/month, 1000 credits/month)
   - [ ] Copy Price IDs (price_xxx...)

2. **Copy billing app** (1h)
   - [ ] Copy `ARTISTING-main/backend/billing/` → `Legal GraphRAG/backend/apps/billing/`
   - [ ] **REMOVE** `UserSubscription` and `SubscriptionPlan` models (not using them)
   - [ ] **KEEP** `Subscription` and `PaymentRecord` models
   - [ ] Review views: `create_checkout_session`, webhook handler

3. **Configure billing** (30min)
   - [ ] Add `'billing'` to `INSTALLED_APPS`
   - [ ] Add Stripe keys to `.env`:
     ```bash
     STRIPE_SECRET_KEY=sk_test_...
     STRIPE_PUBLISHABLE_KEY=pk_test_...
     STRIPE_WEBHOOK_SECRET=whsec_...  # Get this after webhook setup
     FRONTEND_SUCCESS_URL=http://localhost:3000/billing/success
     FRONTEND_CANCEL_URL=http://localhost:3000/billing/cancel
     ```
   - [ ] Update `settings.py` with Stripe config

4. **Create migrations** (15min)
   - [ ] Run `python manage.py makemigrations billing`
   - [ ] Run `python manage.py migrate billing`
   - [ ] Verify tables: `billing_subscription`, `billing_paymentrecord`

5. **Update URLs** (15min)
   - [ ] Add billing endpoints to `ovra_backend/urls.py`:
     - `/api/v1/billing/create-checkout-session/`
     - `/api/v1/billing/webhook/`
     - `/api/v1/billing/subscription/status/`

6. **Test Stripe integration** (1h)
   - [ ] Test checkout session creation
   - [ ] Complete test payment in Stripe
   - [ ] Setup webhook endpoint using Stripe CLI:
     ```bash
     stripe listen --forward-to localhost:8000/api/v1/billing/webhook/
     ```
   - [ ] Verify webhook events logged

**Deliverable**: Working Stripe checkout flow
**Success Criteria**: Can create checkout session, complete test payment, receive webhook

---

### **DAY 3: Backend - Link Chat to Users + Credits** (2025-12-29)

**Goal**: ChatSession linked to users, credits deducted per query

#### Tasks:
1. **Update ChatSession model** (30min)
   - [ ] Add `user` ForeignKey to `ChatSession` model:
     ```python
     user = models.ForeignKey(
         'auth.User',
         on_delete=models.CASCADE,
         null=True,  # Nullable during migration
         blank=True,
         related_name='chat_sessions'
     )
     ```
   - [ ] Run `python manage.py makemigrations legal_graphrag`
   - [ ] Run `python manage.py migrate legal_graphrag`

2. **Create migration for existing sessions** (30min)
   - [ ] Create data migration to link existing sessions to admin user
   - [ ] Create default admin/system user if needed

3. **Update RAG views** (1h)
   - [ ] Import `IsAuthenticated`, `AllowAny` permissions
   - [ ] Add to `LegalRAGQueryView`:
     ```python
     permission_classes = [IsAuthenticated]  # or AllowAny for migration
     ```
   - [ ] Update view to:
     - Get `request.user`
     - Check `user.profile.credits > 0`
     - Deduct 1 credit before query: `profile.credits -= 1; profile.save()`
     - Link session to user: `session.user = request.user`
     - Return remaining credits in response

4. **Add credit tracking** (1h)
   - [ ] Create helper function `deduct_credit(user)` in `users/` app
   - [ ] Add credit validation middleware (optional)
   - [ ] Log credit usage to `MetricLog` (optional)

5. **Update serializers** (30min)
   - [ ] Add `user` field to `ChatSessionSerializer`
   - [ ] Add `remaining_credits` to response serializers

6. **Test credit system** (1h)
   - [ ] Create test user with 5 credits
   - [ ] Make 5 RAG queries
   - [ ] Verify credits decrease: 5 → 4 → 3 → 2 → 1 → 0
   - [ ] Verify 6th query fails with "no credits" error
   - [ ] Purchase subscription (test)
   - [ ] Verify credits replenished

**Deliverable**: Protected RAG API with credit tracking
**Success Criteria**: Authenticated users can query RAG, credits deducted correctly

---

### **DAY 4: Frontend - Service Layer & Auth Context** (2025-12-30)

**Goal**: Frontend authentication infrastructure working

#### Tasks:
1. **Copy service architecture** (1h)
   - [ ] Copy `ARTISTING-main/frontend/lib/services/` → `Legal GraphRAG/frontend-legal/src/lib/services/`
   - [ ] Files to copy:
     - `base.service.ts`
     - `auth.service.ts`
     - `user.service.ts`
     - `config.ts`
     - `index.ts`
   - [ ] Update `config.ts` with Legal GraphRAG API URL

2. **Copy auth context** (30min)
   - [ ] Copy `ARTISTING-main/frontend/contexts/` → `Legal GraphRAG/frontend-legal/src/contexts/`
   - [ ] Review `auth-context.tsx`
   - [ ] Update import paths if needed

3. **Install frontend dependencies** (30min)
   - [ ] Add to `package.json`:
     ```json
     {
       "dependencies": {
         "@radix-ui/react-avatar": "latest",
         "@radix-ui/react-dialog": "1.1.4",
         "@radix-ui/react-dropdown-menu": "latest",
         "@radix-ui/react-label": "2.1.1",
         "@radix-ui/react-toast": "1.2.4",
         "@radix-ui/react-slot": "1.1.1",
         "react-hook-form": "^7.54.1",
         "zod": "^3.24.1",
         "class-variance-authority": "^0.7.1",
         "clsx": "^2.1.1",
         "tailwind-merge": "^2.5.5",
         "lucide-react": "^0.454.0",
         "next-themes": "latest",
         "react-hot-toast": "^2.5.2"
       }
     }
     ```
   - [ ] Run `npm install`

4. **Update root layout** (30min)
   - [ ] Wrap app in `AuthProvider` in `app/layout.tsx`
   - [ ] Add Toaster for notifications
   - [ ] Test context available in pages

5. **Create .env.local** (15min)
   - [ ] Create `frontend-legal/.env.local`:
     ```bash
     NEXT_PUBLIC_API_URL=http://localhost:8000
     NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
     ```

6. **Test service layer** (30min)
   - [ ] Test `authService.login()` from browser console
   - [ ] Verify tokens stored in localStorage
   - [ ] Test `authService.isAuthenticated()`

**Deliverable**: Frontend auth services configured
**Success Criteria**: Can call authService methods, tokens persist

---

### **DAY 5: Frontend - Auth Pages** (2025-12-31)

**Goal**: Login, signup, and account pages working

#### Tasks:
1. **Copy UI components** (1h)
   - [ ] Copy `ARTISTING-main/frontend/components/ui/` → `Legal GraphRAG/frontend-legal/src/components/ui/`
   - [ ] Essential components:
     - `button.tsx`
     - `input.tsx`
     - `label.tsx`
     - `card.tsx`
     - `dialog.tsx`
     - `toast.tsx`
     - `dropdown-menu.tsx`
   - [ ] Update Tailwind paths if needed

2. **Copy auth pages** (1.5h)
   - [ ] Copy `ARTISTING-main/frontend/app/login/` → `Legal GraphRAG/frontend-legal/src/app/login/`
   - [ ] Copy `ARTISTING-main/frontend/app/signup/` → `Legal GraphRAG/frontend-legal/src/app/signup/`
   - [ ] Copy `ARTISTING-main/frontend/app/account/` → `Legal GraphRAG/frontend-legal/src/app/account/`
   - [ ] Update import paths
   - [ ] Update branding (logos, text)

3. **Copy utility components** (1h)
   - [ ] Copy `protected-route.tsx`
   - [ ] Copy `shared-header.tsx`
   - [ ] Copy `shared-footer.tsx`
   - [ ] Update navigation links

4. **Test auth flow** (1h)
   - [ ] Test signup: Create new user
   - [ ] Test login: Get JWT tokens
   - [ ] Test logout: Clear tokens
   - [ ] Test protected route redirect
   - [ ] Test "remember me" functionality

5. **Update existing chat interface** (1h)
   - [ ] Add auth check to chat page
   - [ ] Show user info in header
   - [ ] Show remaining credits
   - [ ] Redirect to login if not authenticated

**Deliverable**: Complete auth UI
**Success Criteria**: Users can sign up, log in, and access chat

---

### **DAY 6: Frontend - Billing UI** (2026-01-01)

**Goal**: Subscription management and payment UI working

#### Tasks:
1. **Copy billing pages** (1.5h)
   - [ ] Copy `ARTISTING-main/frontend/app/billing/` → `Legal GraphRAG/frontend-legal/src/app/billing/`
   - [ ] Copy `ARTISTING-main/frontend/app/pricing/` → `Legal GraphRAG/frontend-legal/src/app/pricing/`
   - [ ] Copy `ARTISTING-main/frontend/app/credits/` → `Legal GraphRAG/frontend-legal/src/app/credits/`
   - [ ] Update pricing tiers and amounts

2. **Create billing service** (1h)
   - [ ] Create `frontend-legal/src/lib/services/billing.service.ts`
   - [ ] Methods:
     - `createCheckoutSession(priceId)`
     - `getSubscriptionStatus()`
     - `cancelSubscription()`
     - `getPaymentHistory()`

3. **Integrate Stripe checkout** (1h)
   - [ ] Install `@stripe/stripe-js`
   - [ ] Create checkout flow:
     - User selects plan
     - Call `createCheckoutSession()`
     - Redirect to Stripe checkout
     - Handle success/cancel redirects

4. **Create success/cancel pages** (30min)
   - [ ] Create `app/billing/success/page.tsx`
   - [ ] Create `app/billing/cancel/page.tsx`
   - [ ] Show appropriate messages

5. **Update header with credits** (30min)
   - [ ] Show credit count in header/sidebar
   - [ ] Add "Upgrade" button when credits low
   - [ ] Link to billing page

6. **Test billing flow** (1h)
   - [ ] Select Basic plan
   - [ ] Complete test checkout (use Stripe test card: 4242 4242 4242 4242)
   - [ ] Verify webhook updates subscription
   - [ ] Verify credits allocated
   - [ ] Test cancel subscription

**Deliverable**: Complete billing UI
**Success Criteria**: Users can subscribe, see credits, manage billing

---

### **DAY 7: Chat History UI** (2026-01-02)

**Goal**: Users can view and manage chat history

#### Tasks:
1. **Create chat service** (1h)
   - [ ] Update `frontend-legal/src/lib/services/chat.service.ts`
   - [ ] Methods:
     - `getConversations()` - List all sessions
     - `getConversation(sessionId)` - Get messages
     - `deleteConversation(sessionId)` - Delete session

2. **Copy history page** (1h)
   - [ ] Copy `ARTISTING-main/frontend/app/history/` → `Legal GraphRAG/frontend-legal/src/app/history/`
   - [ ] Update to use Legal GraphRAG's `ChatSession` model
   - [ ] Show session metadata (topic_lock, question_type, etc.)

3. **Update backend views** (1h)
   - [ ] Create `/api/v1/legal-graphrag/sessions/` endpoint
   - [ ] Filter by `request.user`
   - [ ] Return list of sessions with preview
   - [ ] Create `/api/v1/legal-graphrag/sessions/<id>/` endpoint
   - [ ] Return full session with messages

4. **Build history UI components** (1.5h)
   - [ ] Session list component (cards with preview)
   - [ ] Session detail view (full chat replay)
   - [ ] Search/filter functionality
   - [ ] Delete confirmation dialog

5. **Test history features** (30min)
   - [ ] View list of past conversations
   - [ ] Click to view full conversation
   - [ ] Search for specific topic
   - [ ] Delete a conversation
   - [ ] Verify empty state when no history

**Deliverable**: Working chat history UI
**Success Criteria**: Users can browse, search, and manage chat history

---

### **DAY 8: Integration & Polish** (2026-01-03)

**Goal**: Connect all pieces, fix bugs, polish UX

#### Tasks:
1. **Navigation updates** (1h)
   - [ ] Update header with:
     - User avatar/menu
     - Credits display
     - Links: Chat | History | Billing | Account
   - [ ] Add sidebar navigation (optional)
   - [ ] Update footer links

2. **Error handling** (1h)
   - [ ] Add error boundaries
   - [ ] Add toast notifications for errors
   - [ ] Handle network failures gracefully
   - [ ] Add loading states to all async operations

3. **Credit flow refinement** (1h)
   - [ ] Show credit deduction animation
   - [ ] Warn when credits low (<5)
   - [ ] Block queries when credits = 0
   - [ ] Show "upgrade to continue" modal

4. **Branding updates** (1h)
   - [ ] Replace ARTISTING logo with Legal GraphRAG
   - [ ] Update color scheme in `tailwind.config.ts`
   - [ ] Update site title and metadata
   - [ ] Update legal pages (privacy, terms)

5. **Performance optimization** (1h)
   - [ ] Add loading skeletons
   - [ ] Optimize image loading
   - [ ] Add request debouncing
   - [ ] Cache user profile data

6. **Mobile responsiveness** (1h)
   - [ ] Test all pages on mobile
   - [ ] Fix layout issues
   - [ ] Optimize touch interactions

**Deliverable**: Polished, production-ready UI
**Success Criteria**: All features working smoothly, good UX

---

### **DAY 9: Testing & Bug Fixes** (2026-01-04)

**Goal**: Comprehensive testing and bug elimination

#### Tasks:
1. **Backend tests** (2h)
   - [ ] Write tests for auth endpoints
   - [ ] Write tests for credit deduction
   - [ ] Write tests for Stripe webhooks
   - [ ] Write tests for chat history filtering
   - [ ] Run full test suite: `pytest`

2. **Frontend tests** (1h)
   - [ ] Test auth flow (manual or automated)
   - [ ] Test billing flow
   - [ ] Test chat with credits
   - [ ] Test history browsing

3. **Integration tests** (2h)
   - [ ] End-to-end user journey:
     1. Sign up
     2. Get 5 free credits
     3. Ask 5 RAG questions
     4. Run out of credits
     5. Subscribe to plan
     6. Get more credits
     7. Continue chatting
     8. View history
     9. Cancel subscription

4. **Bug fixes** (2h)
   - [ ] Fix any issues found during testing
   - [ ] Handle edge cases (expired tokens, failed payments, etc.)

**Deliverable**: Stable, tested system
**Success Criteria**: All critical paths working without errors

---

### **DAY 10: Documentation & Deployment Prep** (2026-01-05)

**Goal**: Document integration and prepare for deployment

#### Tasks:
1. **Update documentation** (2h)
   - [ ] Update README.md with new features
   - [ ] Document environment variables
   - [ ] Create user guide:
     - How to sign up
     - How to manage subscription
     - How to use credits
   - [ ] Create deployment guide:
     - Environment setup
     - Database migrations
     - Stripe configuration

2. **Create admin tools** (1h)
   - [ ] Django admin for UserProfile
   - [ ] Django admin for Subscription
   - [ ] Django admin for ChatSession (with user filter)
   - [ ] Script to grant credits manually

3. **Environment configuration** (1h)
   - [ ] Create `.env.example` files for backend and frontend
   - [ ] Document all required variables
   - [ ] Create setup scripts

4. **Security review** (1h)
   - [ ] Review CORS settings
   - [ ] Review authentication permissions
   - [ ] Review Stripe webhook signature validation
   - [ ] Ensure secrets not committed to git

5. **Performance review** (1h)
   - [ ] Check database indexes
   - [ ] Review N+1 queries
   - [ ] Check API response times
   - [ ] Optimize slow endpoints

6. **Deployment checklist** (1h)
   - [ ] Create deployment checklist
   - [ ] Document rollback procedure
   - [ ] Plan database migration strategy
   - [ ] Configure production Stripe account

**Deliverable**: Production-ready codebase with documentation
**Success Criteria**: Code documented, deployable, secure

---

## 📊 Sprint Metrics

### Estimated Effort:
- **Backend**: 20 hours
- **Frontend**: 18 hours
- **Testing**: 6 hours
- **Documentation**: 4 hours
- **Total**: ~48 hours (~6 working days at 8h/day)

### Risk Areas:
1. ⚠️ Stripe webhook configuration (can be tricky)
2. ⚠️ Token refresh handling (race conditions)
3. ⚠️ Migration of existing chat sessions
4. ⚠️ Credit synchronization between models

---

## ✅ Definition of Done

A task is complete when:
- [ ] Code written and working locally
- [ ] Manual testing passed
- [ ] No console errors
- [ ] Responsive on mobile
- [ ] Git committed with clear message
- [ ] Relevant documentation updated

---

## 🚀 Launch Checklist (Post-Sprint)

Before going live:
- [ ] All tests passing
- [ ] Production Stripe account configured
- [ ] Production database backed up
- [ ] Environment variables set in production
- [ ] HTTPS configured
- [ ] Domain configured
- [ ] Email sending tested
- [ ] Monitoring/logging configured
- [ ] User acceptance testing completed

---

## 📞 Daily Standup Questions

1. What did I complete yesterday?
2. What am I working on today?
3. Any blockers or risks?

---

## 🎯 Success Criteria (End of Sprint)

- [x] User can sign up and log in
- [x] User receives 5 free credits on signup
- [x] User can ask RAG questions (credits deducted)
- [x] User can subscribe to a plan via Stripe
- [x] Credits replenished after subscription
- [x] User can view chat history
- [x] User can manage subscription
- [x] UI matches ARTISTING branding
- [x] All critical bugs fixed
- [x] Documentation complete

---

**Sprint Plan Created**: 2025-12-27
**Last Updated**: 2025-12-27
**Status**: READY TO START 🚀