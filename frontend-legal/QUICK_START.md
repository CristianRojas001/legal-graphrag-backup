# Quick Start Guide

## For Codex: Simple Testing Tasks

### 1. Start the Application

**Terminal 1 - Backend**:
```bash
cd "d:\IT workspace\Legal GraphRAG\backend"
python manage.py runserver
```

**Terminal 2 - Frontend**:
```bash
cd "d:\IT workspace\Legal GraphRAG\frontend-legal"
npm run dev
```

### 2. Open in Browser

Navigate to: http://localhost:3000

### 3. Test a Query

Type in the chat: "¿Puedo deducir gastos de home studio?"

### 4. What to Check

- [ ] Page loads without errors
- [ ] Chat interface displays correctly
- [ ] Query sends successfully
- [ ] Response appears with sources
- [ ] Sources can be expanded
- [ ] No console errors (F12)

### 5. Create Test Report

After testing, create `FRONTEND_TEST_REPORT.md` documenting:
- What works
- What doesn't work
- Any errors or issues

See [INSTRUCTIONS_FOR_CODEX.md](./INSTRUCTIONS_FOR_CODEX.md) for detailed testing checklist.

---

That's it! Simple and straightforward.
