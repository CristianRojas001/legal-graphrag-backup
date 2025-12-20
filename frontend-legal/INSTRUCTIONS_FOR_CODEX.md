# Instructions for Codex - Frontend Testing & Simple Tasks

This document contains simple tasks that Codex can complete for the Legal GraphRAG frontend.

## Status: Ready for Testing

The frontend application has been built and is ready for testing with the backend API.

### Current Progress (2025-12-13)
- ✅ Backend + frontend dev servers started locally, API smoke tests logged in `FRONTEND_TEST_REPORT.md`
- ⚠️ Browser-based checklist (UI/UX, responsive, console/network, error states) still pending manual execution
- ⚠️ `/api/v1/health/` endpoint not implemented yet; health check command will 404 until added or docs updated
- 🔁 Next action: follow the checklist below in a browser session and update the report with pass/fail results

## Simple Tasks for Codex

### 1. Start the Development Server

```bash
cd "d:\IT workspace\Legal GraphRAG\frontend-legal"
npm run dev
```

The app will be available at http://localhost:3000

### 2. Test Backend Connection

Before testing the chat, ensure the Django backend is running:

```bash
# In a separate terminal, from the backend directory
cd "d:\IT workspace\Legal GraphRAG\backend"
python manage.py runserver
```

Verify the backend health:
```bash
curl http://localhost:8000/api/v1/health/
```

### 3. Manual Testing Checklist

Open http://localhost:3000 and test the following:

#### UI/UX Testing
- [ ] Page loads without errors
- [ ] Legal disclaimer is visible at the top
- [ ] Disclaimer can be dismissed by clicking X
- [ ] Welcome message displays with example queries
- [ ] Input field is responsive and accepts text
- [ ] Character counter shows current/max (500) characters
- [ ] Send button is disabled when input is empty
- [ ] Send button is disabled during loading

#### Chat Functionality
- [ ] Type a test query: "¿Puedo deducir gastos de home studio?"
- [ ] Click "Enviar" button
- [ ] Loading skeleton appears
- [ ] User message appears in blue bubble (right side)
- [ ] Assistant response appears in gray bubble (left side)
- [ ] Response is formatted as markdown
- [ ] Sources section appears below the answer
- [ ] Source cards show source type badges (BOE, EUR-Lex, etc.)
- [ ] Click on a source card to expand it
- [ ] Verify "Ver documento completo" link works
- [ ] Timestamp shows correctly

#### Error Handling
- [ ] Turn off backend (stop Django server)
- [ ] Try to send a message
- [ ] Error message appears in red banner
- [ ] Error can be dismissed by clicking X
- [ ] Error message shows in chat as assistant response

#### Responsive Design
- [ ] Resize browser window to mobile size (375px width)
- [ ] Check that layout adapts correctly
- [ ] Verify messages are readable on mobile
- [ ] Verify input form works on mobile

#### Multi-Message Testing
- [ ] Send multiple queries in sequence
- [ ] Verify chat scrolls to bottom automatically
- [ ] Click "Nueva consulta" button
- [ ] Verify chat clears and returns to welcome screen

### 4. Console Error Check

Open browser DevTools (F12) and check for:
- [ ] No console errors
- [ ] No network errors (except when backend is intentionally off)
- [ ] No React warnings

### 5. Performance Check

In DevTools Network tab:
- [ ] Verify API requests go to http://localhost:8000
- [ ] Check response times are reasonable (<5s for chat)
- [ ] Verify proper request/response structure

### 6. Simple Code Improvements (Optional)

If you find any simple improvements, you can make them:

#### Add a Favicon
1. Download or create a legal-themed icon
2. Place in `public/favicon.ico`
3. Verify it appears in browser tab

#### Add Type-Check Script
Add to `package.json` scripts:
```json
"type-check": "tsc --noEmit"
```

#### Update Port (if needed)
If port 3000 is occupied, update the dev server:
```json
// package.json
"dev": "next dev -p 3001"
```

### 7. Create Test Report

After testing, create a file `FRONTEND_TEST_REPORT.md` with:

```markdown
# Frontend Test Report

**Date**: [Current Date]
**Tester**: Codex
**Environment**: Windows, Node.js [version], Chrome [version]

## Test Results

### Passed Tests
- [List all passing tests from checklist above]

### Failed Tests
- [List any failing tests with error details]

### Issues Found
- [List any bugs, UI issues, or improvements needed]

### Performance
- Average response time: [X]s
- Page load time: [X]s
- Build size: [Check .next folder size]

### Browser Compatibility
- [ ] Chrome
- [ ] Firefox
- [ ] Edge
- [ ] Safari (if available)

### Recommendations
- [Any suggestions for improvement]
```

## What NOT to Do

- **Don't** make complex architectural changes
- **Don't** add new features not in the original spec
- **Don't** modify the API client without verifying backend compatibility
- **Don't** change the design significantly (colors, layout)

## What TO Report

- Any errors in console
- Any TypeScript type errors
- Any broken functionality
- Performance issues (slow loads, lag)
- Accessibility issues
- Mobile responsive issues

## Next Steps After Testing

1. If tests pass → Mark Day 5 as complete
2. If tests fail → Document issues in test report
3. Create list of any bugs that need fixing
4. Update the sprint plan with actual vs. expected results

## Backend Integration Notes

The frontend expects these API responses:

### Chat Response
```json
{
  "answer": "Markdown formatted answer...",
  "sources": [
    {
      "id": "BOE-A-1978-31229",
      "title": "Constitución Española",
      "url": "https://www.boe.es/...",
      "source_type": "BOE",
      "relevance_score": 0.95,
      "excerpt": "Text excerpt..."
    }
  ],
  "query": "Original query",
  "timestamp": "2025-12-13T12:00:00Z",
  "session_id": "uuid-here"
}
```

### Error Response
```json
{
  "error": "Error message",
  "detail": "Detailed error description"
}
```

If the backend responses don't match this format, the frontend may need adjustments.

## Support

For questions or issues during testing, refer to:
- [README.md](./README.md) - Full documentation
- [Sprint Plan](../docs/08_MVP_SPRINT_PLAN.md) - Day 5 requirements
- Backend API docs (if available)

Good luck with testing!
