# Legal GraphRAG Frontend - Integration Guide

## Document Information
- **Version**: 1.0
- **Last Updated**: 2025-12-13
- **Status**: Day 5 Complete - Integration Pending
- **Parent Project**: Artisting Platform (D:\IT workspace\infosubvenciones-api\ARTISTING-main)

---

## 1. Overview

> **🚨 CRITICAL**: These are **TWO COMPLETELY SEPARATE PROJECTS** for now.
>
> - **Legal GraphRAG**: `D:\IT workspace\Legal GraphRAG\`
> - **Parent Artisting**: `D:\IT workspace\infosubvenciones-api\ARTISTING-main\`
>
> **DO NOT mix files, dependencies, or code between projects.**
> **Each deploys SEPARATELY to different domains.**

The Legal GraphRAG frontend (`frontend-legal/`) is a **standalone Next.js app** that will **eventually** be merged into the main Artisting platform.

> **⚠️ Important**: The parent Artisting project has a **different chat system** (grants-related). This Legal GraphRAG chat is **completely independent** for legal questions. These are separate features.

### Current State (MVP - Sprint Week 1)
- ✅ Standalone Next.js 15 app (TypeScript + Tailwind)
- ✅ Custom components with basic styling
- ✅ Functional **legal-specific** chat interface
- ✅ **Independent deployment** (separate domain)
- ❌ **NOT integrated** with parent project
- ❌ **NOT using** parent's design system (yet)

### Future State (Post-MVP - Week 2-3+)
- Legal GraphRAG as a **route/page** in the main Artisting app
- Uses **shadcn/ui** components (parent's component library)
- Matches parent's **color scheme and branding**
- Integrated with parent's **auth and layout system**
- **Single deployment** with parent project

### Timeline
- **Now (Sprint)**: Build and deploy **separately**
- **Later (Post-MVP)**: Merge and integrate

---

## 2. Design System Comparison

### Legal GraphRAG (Current - Standalone)

**Location**: `D:\IT workspace\Legal GraphRAG\frontend-legal\`

**Tech Stack**:
- Next.js 15 (App Router)
- Tailwind CSS v4
- Custom React components (no component library)
- Geist fonts

**Colors**:
- Primary: Blue gradient (`from-blue-600 to-blue-800`)
- User messages: Blue (`bg-blue-600`)
- Assistant messages: Gray (`bg-gray-100`)
- No CSS variables

**Components**:
- Custom built from scratch
- No shadcn/ui
- No icon library (inline SVG)

---

### Artisting Platform (Target - Parent Project)

**Location**: `D:\IT workspace\infosubvenciones-api\ARTISTING-main\frontend\`

**Tech Stack**:
- Next.js (App Router)
- Tailwind CSS
- **shadcn/ui** component library (Radix UI primitives)
- **Lucide** icons
- Helvetica Neue fonts

**Colors** (from `tailwind.config.ts` and `globals.css`):
```typescript
primary: {
  DEFAULT: '#D4AF37',  // GOLD (brand color)
  foreground: 'hsl(var(--primary-foreground))'
}

// Light mode
--primary: 221.2 83.2% 53.3%  // Blue #3B82F6
--primary-rgb: 59, 130, 246

// Dark mode
--primary: 217.2 91.2% 59.8%  // Lighter blue #60A5FA
--primary-rgb: 96, 165, 250
```

**Key Features**:
- CSS variables for theming
- Dark mode support (`dark:` classes)
- Glass morphism effects
- Custom animations (typing indicator, streaming glow)
- shadcn/ui components in `components/ui/`

**Component Structure**:
```
frontend/
├── app/              # Next.js pages
├── components/
│   ├── ui/          # shadcn/ui components
│   └── ...          # Custom components
├── contexts/        # React contexts
├── hooks/           # Custom hooks
├── lib/             # Utilities
└── styles/          # Global styles
```

---

## 3. Integration Strategy

### Phase 1: Move Legal GraphRAG into Artisting (Post-MVP)

**Goal**: Add Legal GraphRAG as `/legal` route in main app

**Steps**:

1. **Copy Backend Integration**
   ```bash
   # Legal GraphRAG backend already exists at:
   # D:\IT workspace\Legal GraphRAG\backend\

   # Main Django app already has Legal GraphRAG:
   # D:\IT workspace\infosubvenciones-api\ARTISTING-main\backend\apps\legal_graphrag\
   ```

2. **Create Legal Route in Artisting Frontend**
   ```bash
   cd "D:\IT workspace\infosubvenciones-api\ARTISTING-main\frontend"

   # Create new route
   mkdir -p app/legal
   ```

3. **Refactor Components to Use shadcn/ui**

   **Current (Legal GraphRAG)**:
   ```tsx
   // Custom component
   <button className="px-6 py-3 bg-blue-600 text-white rounded-lg">
     Send
   </button>
   ```

   **Target (Artisting)**:
   ```tsx
   // shadcn/ui Button component
   import { Button } from "@/components/ui/button"

   <Button variant="default" size="lg">
     Send
   </Button>
   ```

4. **Update Color Scheme**

   **Replace**:
   - `bg-blue-600` → `bg-primary`
   - `text-blue-600` → `text-primary`
   - Gradient headers → Use parent's gold accent (`#D4AF37`)

5. **Add shadcn/ui Components**

   Install missing components:
   ```bash
   npx shadcn@latest add button
   npx shadcn@latest add card
   npx shadcn@latest add input
   npx shadcn@latest add alert
   ```

6. **Update Icons**
   ```bash
   npm install lucide-react
   ```

   Replace inline SVG with Lucide icons:
   ```tsx
   import { Send, ChevronDown, ExternalLink } from "lucide-react"
   ```

---

## 4. File Mapping (Post-Integration)

### Current Structure (Standalone)
```
Legal GraphRAG/frontend-legal/src/
├── app/
│   ├── page.tsx                    # Home (chat interface)
│   └── layout.tsx                  # Root layout
├── components/
│   ├── LegalChatInterface.tsx
│   ├── SourceCard.tsx
│   ├── LoadingSkeleton.tsx
│   ├── ErrorMessage.tsx
│   └── LegalDisclaimer.tsx
├── services/
│   └── api.ts                      # API client
└── types/
    └── api.ts                      # TypeScript types
```

### Target Structure (Integrated)
```
ARTISTING-main/frontend/
├── app/
│   ├── legal/                      # NEW: Legal GraphRAG route
│   │   ├── page.tsx               # Chat interface (refactored)
│   │   └── layout.tsx             # Legal-specific layout
│   └── ...
├── components/
│   ├── ui/                         # shadcn/ui (existing)
│   ├── legal/                      # NEW: Legal GraphRAG components
│   │   ├── LegalChatInterface.tsx
│   │   ├── LegalSourceCard.tsx
│   │   ├── LegalDisclaimer.tsx
│   │   └── ...
│   └── ...
├── lib/
│   ├── api/                        # NEW: API clients
│   │   └── legal-graphrag.ts      # Legal API client
│   └── ...
└── types/
    ├── legal.ts                    # NEW: Legal types
    └── ...
```

---

## 5. Component Migration Checklist

### LegalChatInterface.tsx
- [ ] Replace `bg-blue-600` with `bg-primary`
- [ ] Use shadcn/ui `Button` component
- [ ] Use shadcn/ui `Input` component
- [ ] Replace inline SVG with Lucide icons
- [ ] Add dark mode support (`dark:` classes)
- [ ] Use CSS variables (`hsl(var(--primary))`)
- [ ] Apply parent's animations (`.streaming-glow`, `.typing-indicator`)

### SourceCard.tsx
- [ ] Use shadcn/ui `Card` component
- [ ] Use shadcn/ui `Badge` for source type tags
- [ ] Use Lucide `ChevronDown` icon
- [ ] Use Lucide `ExternalLink` icon
- [ ] Add `.card-hover` class for hover effects
- [ ] Support dark mode

### LoadingSkeleton.tsx
- [ ] Use parent's `.typing-indicator` animation
- [ ] Use CSS variable colors

### ErrorMessage.tsx
- [ ] Use shadcn/ui `Alert` component
- [ ] Use Lucide `AlertCircle` icon
- [ ] Use Lucide `X` icon

### LegalDisclaimer.tsx
- [ ] Use shadcn/ui `Alert` component (variant="warning")
- [ ] Use Lucide `Info` icon

---

## 6. API Client Integration

### Current (Standalone)
```typescript
// frontend-legal/src/services/api.ts
const baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
```

### Target (Integrated)
```typescript
// ARTISTING-main/frontend/lib/api/legal-graphrag.ts
import { apiClient } from '@/lib/api/client' // Shared API client

export const legalGraphRAGAPI = {
  chat: async (query: string, sessionId?: string) => {
    return apiClient.post('/api/v1/legal-graphrag/chat/', {
      query,
      session_id: sessionId
    })
  },
  // ...
}
```

Use parent's existing API infrastructure (auth tokens, error handling, interceptors).

---

## 7. Authentication & Layout Integration

### Add Auth Wrapper
```tsx
// app/legal/layout.tsx
import { requireAuth } from '@/lib/auth'

export default async function LegalLayout({ children }) {
  await requireAuth() // Or use parent's auth check

  return (
    <div className="legal-graphrag-layout">
      {children}
    </div>
  )
}
```

### Use Parent Navigation
```tsx
import { MainNav } from '@/components/nav/main-nav'
import { UserNav } from '@/components/nav/user-nav'

// Include parent's header/sidebar
```

---

## 8. Environment Variables

### Current (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME="Legal GraphRAG - Artisting"
```

### Target (Merge into parent's .env)
```env
# Add to ARTISTING-main/frontend/.env.local
NEXT_PUBLIC_LEGAL_GRAPHRAG_ENABLED=true
```

Parent app already has `NEXT_PUBLIC_API_URL`.

---

## 9. Migration Timeline

### Immediate (MVP - Current Sprint)
- ✅ Keep standalone app for testing
- ✅ Deploy separately at `legal.artisting.es` (if needed)

### Post-MVP (Week 2)
- [ ] Set up `/legal` route in parent app
- [ ] Refactor components to use shadcn/ui
- [ ] Migrate to parent's design system
- [ ] Test integration with auth system

### Production (Week 3)
- [ ] Remove standalone app
- [ ] Deploy as integrated route
- [ ] Update DNS (if deployed separately before)

---

## 10. Design Tokens Reference

### Colors to Update

| Current (Standalone) | Target (Parent) | Usage |
|---------------------|-----------------|-------|
| `bg-blue-600` | `bg-primary` | Primary buttons, user messages |
| `from-blue-600 to-blue-800` | `bg-gradient-to-r from-primary/90 to-primary` | Header gradient |
| `text-blue-600` | `text-primary` | Links, accents |
| `bg-gray-100` | `bg-card` or `bg-muted` | Assistant messages, cards |
| `border-gray-300` | `border-border` | Borders |
| `text-gray-900` | `text-foreground` | Text color |

### Border Radius
```css
/* Current */
rounded-lg        /* 0.5rem */

/* Target */
rounded-lg        /* var(--radius) = 0.75rem */
```

### Shadows
```css
/* Current */
shadow-md

/* Target */
class="shadow-soft"  /* Custom shadow from globals.css */
```

---

## 11. Testing Integration

### Before Integration (Standalone)
```bash
cd "D:\IT workspace\Legal GraphRAG\frontend-legal"
npm run dev  # Port 3000
```

### After Integration (Parent App)
```bash
cd "D:\IT workspace\infosubvenciones-api\ARTISTING-main\frontend"
npm run dev
# Visit http://localhost:3000/legal
```

---

## 12. Documentation Updates Needed

### Update These Files
1. `frontend-legal/README.md` - Add integration section
2. `ARTISTING-main/frontend/README.md` - Document Legal route
3. `docs/06_DEPLOYMENT_GUIDE.md` - Update deployment for integrated app
4. `docs/01_ARCHITECTURE.md` - Show Legal as integrated route

---

## 13. Quick Reference Commands

### Install shadcn/ui in Legal Frontend (Test Migration)
```bash
cd "D:\IT workspace\Legal GraphRAG\frontend-legal"

# Initialize shadcn/ui
npx shadcn@latest init

# Add components
npx shadcn@latest add button card input alert badge
```

### Copy Parent's Design System
```bash
# Copy parent's Tailwind config
cp "D:\IT workspace\infosubvenciones-api\ARTISTING-main\frontend\tailwind.config.ts" \
   "D:\IT workspace\Legal GraphRAG\frontend-legal\tailwind.config.ts"

# Copy parent's global CSS
cp "D:\IT workspace\infosubvenciones-api\ARTISTING-main\frontend\app\globals.css" \
   "D:\IT workspace\Legal GraphRAG\frontend-legal\src\app\globals.css"

# Copy shadcn/ui config
cp "D:\IT workspace\infosubvenciones-api\ARTISTING-main\frontend\components.json" \
   "D:\IT workspace\Legal GraphRAG\frontend-legal\components.json"
```

---

## 14. Known Issues & Considerations

### Potential Conflicts
1. **Font clash**: Legal uses Geist, parent uses Helvetica Neue
2. **Port conflicts**: Both run on 3000 by default
3. **API client duplication**: Need to merge into parent's client
4. **Session management**: Use parent's session system

### Breaking Changes
- Removing blue theme → gold/neutral theme
- Custom components → shadcn/ui components
- Standalone layout → Nested layout (with parent nav)

---

## 15. Contact & Support

**Integration Owner**: Development Team
**Parent Project**: Artisting Platform
**Legal GraphRAG**: Legal question-answering system for artists

For integration questions, consult:
- [01_ARCHITECTURE.md](./01_ARCHITECTURE.md) - System architecture
- [08_MVP_SPRINT_PLAN.md](./08_MVP_SPRINT_PLAN.md) - Current sprint
- Parent project docs at `ARTISTING-main/docs/`

---

**Last Updated**: 2025-12-13
**Next Review**: Post-MVP (Week 2)
