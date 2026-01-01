# 🚀 Integration Sprint - START HERE

**Welcome to the Legal GraphRAG + ARTISTING Integration Sprint!**

This document is your starting point for integrating authentication, billing, and chat history into Legal GraphRAG.

---

## 📚 Documentation Structure

We've created 3 comprehensive documents for this integration:

### 1. **[INTEGRATION_SPRINT_PLAN.md](./INTEGRATION_SPRINT_PLAN.md)** 📅
**Purpose**: Day-by-day execution plan (10 days)
**Use when**: You're ready to start coding and need step-by-step instructions
**Contains**:
- Daily task breakdown
- Estimated time per task
- Success criteria for each day
- Testing checklist per milestone

### 2. **[INTEGRATION_TECHNICAL_REFERENCE.md](./INTEGRATION_TECHNICAL_REFERENCE.md)** 🔧
**Purpose**: Deep technical details and implementation patterns
**Use when**: You need to understand HOW something works
**Contains**:
- Architecture diagrams
- Authentication flow
- Billing & credits flow
- Database schema
- API endpoint specifications
- Code examples
- Security considerations
- Troubleshooting guide

### 3. **[../INTEGRATION_CHECKLIST.md](../INTEGRATION_CHECKLIST.md)** ✅
**Purpose**: Quick progress tracker
**Use when**: You want to see what's done and what's next
**Contains**:
- Simple checkbox lists
- Files to copy
- Dependencies to install
- Configuration changes
- Testing checklist

---

## 🎯 Quick Start (First 30 Minutes)

### Step 1: Understand the Plan (10 min)
1. Read this document (you're doing it!)
2. Skim the [Sprint Plan](./INTEGRATION_SPRINT_PLAN.md) to understand the scope
3. Review the [Checklist](../INTEGRATION_CHECKLIST.md) to see all tasks

### Step 2: Prepare Your Environment (10 min)
```bash
# 1. Ensure Redis is running
redis-cli ping
# Should return: PONG ✅

# 2. Create git branch for integration
cd "D:\IT workspace\Legal GraphRAG"
git checkout -b feature/artisting-integration

# 3. Commit current state (clean slate)
git add docs/INTEGRATION*.md INTEGRATION_CHECKLIST.md
git commit -m "docs: Add integration sprint documentation"

# 4. Verify Python environment
cd backend
source .venv/bin/activate  # or `.venv\Scripts\activate` on Windows
pip list | grep -E "(django|celery|redis)"
```

### Step 3: Create Stripe Account (10 min)
1. Go to https://stripe.com
2. Sign up for test account (free)
3. Get your test API keys:
   - Dashboard → Developers → API keys
   - Copy `Publishable key` (pk_test_...)
   - Copy `Secret key` (sk_test_...)
4. Save these for later (you'll add to `.env` on Day 2)

---

## 📋 Integration Overview

### What We're Integrating

```
FROM: ARTISTING-main/
├── backend/users/          → Authentication (login/signup/JWT)
├── backend/billing/        → Stripe subscriptions
├── frontend/lib/services/  → API client architecture
├── frontend/contexts/      → Auth context
└── frontend/app/*pages     → UI pages (login/billing/history)

INTO: Legal GraphRAG/
├── backend/apps/
│   ├── users/             [NEW] User management
│   ├── billing/           [NEW] Subscription & payments
│   └── legal_graphrag/    [UPDATE] Link to users, add credits
└── frontend-legal/src/
    ├── lib/services/      [NEW] Service layer
    ├── contexts/          [NEW] Auth context
    ├── app/login/         [NEW] Login page
    ├── app/billing/       [NEW] Billing page
    └── app/history/       [NEW] Chat history
```

### What We're Building

**Core Features**:
1. ✅ User Authentication (JWT-based)
2. ✅ Credit System (5 free credits → paid tiers)
3. ✅ Stripe Subscriptions (Basic/Pro/Enterprise)
4. ✅ Protected RAG Queries (requires auth + credits)
5. ✅ Chat History (per-user sessions)

**User Journey**:
```
New User
  ↓
Sign Up → Get 5 free credits
  ↓
Ask 5 RAG questions → Credits: 5 → 4 → 3 → 2 → 1 → 0
  ↓
Credits = 0 → Blocked from asking more
  ↓
Subscribe to Plan → Get 50/200/1000 credits
  ↓
Continue using RAG
  ↓
View chat history
  ↓
Manage subscription
```

---

## 🗓️ Sprint Timeline

**Total Duration**: 10 days (8 working days + 2 buffer)
**Start**: 2025-12-27
**End**: 2026-01-06

### Week 1: Backend Foundation
- **Day 1** (Dec 27): Backend auth (users app, JWT)
- **Day 2** (Dec 28): Backend billing (Stripe integration)
- **Day 3** (Dec 29): Link chat to users, credit system

**🎯 Milestone 1**: Backend API complete

### Week 2: Frontend & Integration
- **Day 4** (Dec 30): Frontend service layer & auth context
- **Day 5** (Dec 31): Auth pages (login/signup/account)
- **Day 6** (Jan 1): Billing UI (subscription management)
- **Day 7** (Jan 2): Chat history UI

**🎯 Milestone 2**: Full-stack features complete

### Week 2: Polish & Deploy
- **Day 8** (Jan 3): Integration & polish
- **Day 9** (Jan 4): Testing & bug fixes
- **Day 10** (Jan 5): Documentation & deployment prep

**🎯 Final Milestone**: Production-ready

---

## 🛠️ Key Technical Decisions (Already Made)

You reviewed these with Claude. Here's the summary:

### ✅ Credits Strategy
- **Per query** (1 credit = 1 RAG question)
- Deducted BEFORE query execution
- Stored in `UserProfile.credits`

### ✅ Subscription Model
- Use `Subscription` model (simple, hardcoded tiers)
- Ignore `UserSubscription` + `SubscriptionPlan` (too complex)
- Credits stored in `UserProfile`, not per-subscription

### ✅ Chat History
- Keep Legal GraphRAG's `ChatSession` + `ChatMessage` models
- Add `user` ForeignKey to `ChatSession`
- Ignore ARTISTING's simpler `ChatLog` model

### ✅ API Response Format
- Use ARTISTING format for auth/billing endpoints
- Keep existing format for RAG endpoints (backward compatibility)

### ✅ Branding
- Keep ARTISTING UI components (Shadcn/UI)
- Customize: logos, colors, site title

### ✅ Redis
- Already have it! ✅
- Just ensure it's running locally

---

## 🎯 Success Criteria

### Minimum Viable Integration (MVP)
By end of Day 7, you should have:

1. **Working Authentication**
   - [ ] Users can sign up
   - [ ] Users can log in
   - [ ] JWT tokens work
   - [ ] Protected routes redirect to login

2. **Working Billing**
   - [ ] Users can subscribe to plans
   - [ ] Stripe checkout works
   - [ ] Webhooks update subscription status
   - [ ] Credits allocated after payment

3. **Working Credits**
   - [ ] New users get 5 free credits
   - [ ] RAG queries deduct 1 credit
   - [ ] Zero credits blocks queries
   - [ ] Subscription adds credits

4. **Working Chat History**
   - [ ] Users see only their own sessions
   - [ ] Can view past conversations
   - [ ] Can search/filter history

### Complete Integration (Production-Ready)
By end of Day 10, you should also have:

5. **Polish & UX**
   - [ ] Loading states
   - [ ] Error handling
   - [ ] Mobile responsive
   - [ ] Smooth animations

6. **Testing**
   - [ ] Unit tests passing
   - [ ] Integration tests passing
   - [ ] Manual E2E test completed

7. **Documentation**
   - [ ] README updated
   - [ ] Deployment guide written
   - [ ] User guide created

---

## 🚦 Daily Workflow

Each day, follow this pattern:

### Morning
1. Review today's tasks in [Sprint Plan](./INTEGRATION_SPRINT_PLAN.md)
2. Check yesterday's completed items in [Checklist](../INTEGRATION_CHECKLIST.md)
3. Set clear goal for the day

### During Work
1. Follow step-by-step instructions from Sprint Plan
2. Check off items in Checklist as you complete them
3. Reference Technical Reference for implementation details
4. Commit code frequently (after each major task)

### Evening
1. Update Checklist with progress
2. Test what you built today
3. Note any blockers for tomorrow
4. Commit day's work with clear message

---

## 🆘 When You Get Stuck

### Issue: Don't understand how something works
**→ Read**: [INTEGRATION_TECHNICAL_REFERENCE.md](./INTEGRATION_TECHNICAL_REFERENCE.md)
**→ Section**: Find the relevant section (auth flow, billing flow, etc.)

### Issue: Not sure what to do next
**→ Read**: [INTEGRATION_SPRINT_PLAN.md](./INTEGRATION_SPRINT_PLAN.md)
**→ Check**: Current day's tasks

### Issue: Lost track of progress
**→ Read**: [../INTEGRATION_CHECKLIST.md](../INTEGRATION_CHECKLIST.md)
**→ Find**: Last unchecked item

### Issue: Hit a technical blocker
**→ Check**: "Common Issues & Solutions" in Technical Reference
**→ Search**: ARTISTING-main codebase for examples
**→ Ask**: Claude for help (provide context from docs)

---

## 📊 Progress Tracking

Update this daily:

**Current Day**: [ ] Day 1 | [ ] Day 2 | [ ] Day 3 | ... | [ ] Day 10

**Milestones Completed**:
- [ ] Milestone 1: Backend API (Day 3)
- [ ] Milestone 2: Full-stack (Day 7)
- [ ] Milestone 3: Production-ready (Day 10)

**Overall Progress**: 0% → Target: 100% by Jan 6

---

## 🎉 Ready to Start?

### Pre-flight Checklist
- [x] Redis running (confirmed)
- [ ] Stripe test account created
- [ ] Git branch created: `feature/artisting-integration`
- [ ] Read this document
- [ ] Skimmed Sprint Plan
- [ ] Reviewed Checklist

### First Action
**→ Go to**: [INTEGRATION_SPRINT_PLAN.md](./INTEGRATION_SPRINT_PLAN.md)
**→ Start**: Day 1 - Backend Foundation

---

## 📞 Need Help?

If you need clarification on:
- **What to do**: Check Sprint Plan
- **How it works**: Check Technical Reference
- **What's done**: Check Checklist
- **Why this approach**: Re-read our earlier conversation (answers documented in Technical Reference)

---

## 🎯 Remember

- ✅ **Take it day by day** - Don't rush ahead
- ✅ **Test as you go** - Don't wait until the end
- ✅ **Commit frequently** - Small, atomic commits
- ✅ **Document blockers** - Write down issues for next day
- ✅ **Celebrate progress** - Check off those boxes! ✅

---

**Good luck! You've got this! 🚀**

---

**Document Created**: 2025-12-27
**Status**: READY TO START
**Next Step**: → [Open Sprint Plan](./INTEGRATION_SPRINT_PLAN.md) and start Day 1