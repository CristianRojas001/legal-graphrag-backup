# Migration Plan: Move "Fundamento" Citations to "Fuentes legales" Section

## Current Architecture

### Two Citation Systems (Redundant & Confusing)

1. **"Fundamento:" (LLM-generated text)**
   ```
   **Fundamento:**
   - [Fuente 4]: Real Decreto 887/2006 - Artículo 71
   - [Fuente 2]: Ley 55/2007 - Artículo 34
   ```
   - Location: Inside `answer` text (markdown)
   - Generator: LLM based on prompt instructions
   - Format: Plain text bullets
   - Issues: ❌ Not interactive, ❌ Can be inconsistent

2. **"Fuentes legales" (Backend-generated structured data)**
   ```tsx
   <div className="mt-6 pt-4 border-t border-gray-300">
     <h4>Fuentes legales (5)</h4>
     <SourceCard source={...} /> // Expandable, clickable
   </div>
   ```
   - Location: `response.sources` array → React components
   - Generator: Backend `_format_sources()` method
   - Format: Structured JSON → Interactive cards
   - Benefits: ✅ Reliable, ✅ Interactive, ✅ Consistent

## Goal

**Remove redundant "Fundamento:" from answer text and enhance "Fuentes legales" to show citation context.**

### Before (Current)
```
Answer text with explanation...

**Fundamento:**
- [Fuente 4]: Real Decreto 887/2006 - Artículo 71. Forma de justificación.
- [Fuente 2]: Ley 55/2007, del cine - Artículo 34. Nuevas tecnologías.

**En la práctica:**
...

---

Fuentes legales (5)  // Separate section below
[Expandable cards with all 5 sources]
```

### After (Improved)
```
Answer text with explanation...

**En la práctica:**
...

---

Fuentes utilizadas (2)  // Only cited sources, with citation context
[Expandable cards showing]:
  ✓ Real Decreto 887/2006 - Artículo 71
    → "Citado para: Forma de justificación de subvenciones"
  ✓ Ley 55/2007 - Artículo 34
    → "Citado para: Nuevas tecnologías en producción audiovisual"

Fuentes adicionales (3)  // Other retrieved sources (collapsed by default)
[...]
```

## Implementation Plan

### Phase 1: Remove "Fundamento:" from Prompt (LOW RISK)

**Files to modify**:
- `backend/apps/legal_graphrag/services/legal_rag_engine.py:259-347` (prompt)
- `backend/apps/legal_graphrag/services/v1_1/legal_rag_engine_v1_1.py` (if it has custom prompt)

**Changes**:
```python
# REMOVE this section from prompt:
"""
**Fundamento:**
- [Cita fuente RELEVANT 1 con ID]
- [Cita fuente RELEVANT 2 con ID]
[Cada cita debe respaldar una afirmación específica en Respuesta]
"""

# Keep only:
"""
**Respuesta:**
[2-4 párrafos directos basados en fuentes RELEVANT]

**En la práctica:**
[1-2 párrafos aplicación práctica]
"""
```

**Risk**: 🟢 LOW - LLM will adapt, just removes a section
**Testing**: Run regression tests to ensure answers still cite sources with [ID: ...]

---

### Phase 2: Enhance Backend Source Formatting (MEDIUM RISK)

**Goal**: Attach citation context to each source (why it was cited)

**Files to modify**:
- `backend/apps/legal_graphrag/services/v1_1/legal_rag_engine_v1_1.py:516-545` (_attach_citations)
- `backend/apps/legal_graphrag/services/legal_rag_engine.py:465-499` (_format_sources)

**New approach**:
```python
def _attach_citation_context(
    self,
    answer: str,
    sources: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, str]:
    """
    Extract citation context from answer.

    Returns: {document_id: "citation reason/context"}
    """
    citation_contexts = {}

    # Find sentences containing [ID: ...] citations
    for match in re.finditer(r"([^.!?]*\[ID:\s*([^\]]+)\][^.!?]*[.!?])", answer):
        sentence = match.group(1).strip()
        doc_id = match.group(2).strip()

        # Extract key phrase (simplified)
        context = sentence.replace(f"[ID: {doc_id}]", "").strip()
        citation_contexts[doc_id] = context[:150]  # Limit length

    return citation_contexts

def _format_sources(self, sources: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Enhanced with citation context"""
    formatted = []

    for naturaleza, chunks in sources.items():
        for chunk in chunks:
            formatted.append({
                'id': chunk.get('document_id', ''),
                'title': chunk.get('document_title', ''),
                'url': chunk.get('document_url', ''),
                'source_type': chunk.get('source_naturaleza', ''),
                'relevance_score': chunk.get('similarity', chunk.get('rrf_score', 0)),
                'excerpt': chunk.get('chunk_text', '')[:300],

                # NEW: Citation context
                'citation_context': None,  # Will be filled by answer_query
                'is_cited': False,  # Will be filled by answer_query
            })

    return formatted
```

**In `answer_query()` method**:
```python
# After LLM generation and validation
citation_contexts = self._attach_citation_context(answer_text, sources)

# Format sources with citation context
formatted_sources = self._format_sources(sources)
for source in formatted_sources:
    if source['id'] in citation_contexts:
        source['citation_context'] = citation_contexts[source['id']]
        source['is_cited'] = True
```

**Risk**: 🟡 MEDIUM - Adds complexity but doesn't break existing flow
**Testing**: Verify citation_context extraction works correctly

---

### Phase 3: Update Frontend to Use Citation Context (LOW RISK)

**Files to modify**:
- `frontend-legal/src/types/api.ts` (add new fields)
- `frontend-legal/src/components/LegalChatInterface.tsx` (split cited/uncited sources)
- `frontend-legal/src/components/SourceCard.tsx` (show citation context)

**Changes**:

**1. Update TypeScript types**:
```typescript
// src/types/api.ts
export interface LegalSource {
  id: string;
  title: string;
  url: string;
  source_type: string;
  relevance_score: number;
  excerpt: string;

  // NEW fields
  citation_context?: string | null;
  is_cited?: boolean;
}
```

**2. Update LegalChatInterface to split sources**:
```tsx
{message.sources && message.sources.length > 0 && (
  <div className="mt-6 pt-4 border-t border-gray-300">
    {/* Cited sources */}
    {message.sources.filter(s => s.is_cited).length > 0 && (
      <>
        <h4 className="font-semibold text-sm text-gray-700 mb-3">
          Fuentes utilizadas ({message.sources.filter(s => s.is_cited).length})
        </h4>
        <div className="space-y-2 mb-4">
          {message.sources
            .filter(s => s.is_cited)
            .map((source, idx) => (
              <SourceCard
                key={`cited-${source.id}-${idx}`}
                source={source}
                showCitationContext={true}
              />
            ))}
        </div>
      </>
    )}

    {/* Additional sources (not cited) */}
    {message.sources.filter(s => !s.is_cited).length > 0 && (
      <details className="mt-4">
        <summary className="cursor-pointer font-semibold text-sm text-gray-600 hover:text-gray-800">
          Fuentes adicionales ({message.sources.filter(s => !s.is_cited).length})
        </summary>
        <div className="space-y-2 mt-2">
          {message.sources
            .filter(s => !s.is_cited)
            .map((source, idx) => (
              <SourceCard
                key={`additional-${source.id}-${idx}`}
                source={source}
                showCitationContext={false}
              />
            ))}
        </div>
      </details>
    )}
  </div>
)}
```

**3. Update SourceCard to show citation context**:
```tsx
export default function SourceCard({
  source,
  showCitationContext = false
}: SourceCardProps) {
  return (
    <div className={`border rounded-lg overflow-hidden ${
      source.is_cited
        ? 'border-blue-300 bg-blue-50'
        : 'border-gray-300 bg-white'
    }`}>
      <button onClick={() => setIsExpanded(!isExpanded)} className="w-full px-4 py-3">
        <div className="flex-1 min-w-0">
          {/* Existing title and badges */}

          {/* NEW: Citation context */}
          {showCitationContext && source.citation_context && (
            <p className="text-xs text-blue-700 mt-1 italic">
              → Citado: "{source.citation_context}"
            </p>
          )}
        </div>
      </button>

      {/* Existing expanded content */}
    </div>
  );
}
```

**Risk**: 🟢 LOW - Purely additive, backwards compatible
**Testing**: Verify UI renders correctly with new fields

---

## Risk Assessment

| Phase | Risk | Difficulty | Rollback Strategy |
|-------|------|-----------|-------------------|
| 1. Remove Fundamento prompt | 🟢 LOW | Easy | Revert prompt change |
| 2. Backend citation context | 🟡 MEDIUM | Medium | Make fields optional, default to null |
| 3. Frontend enhancement | 🟢 LOW | Easy | Fall back to old rendering if fields missing |

**Overall Risk**: 🟡 **MEDIUM** (mostly due to Phase 2 complexity)

## Testing Strategy

### Unit Tests
- [ ] Test `_attach_citation_context()` extracts correct context
- [ ] Test `_format_sources()` includes new fields
- [ ] Test backward compatibility (old answers without citation_context)

### Integration Tests
- [ ] Cited sources appear in "Fuentes utilizadas"
- [ ] Uncited sources appear in "Fuentes adicionales"
- [ ] Citation context displays correctly
- [ ] Old responses (before migration) still work

### Regression Tests
- [ ] All existing citation confetti tests pass
- [ ] No duplicate source listings
- [ ] Answer quality unchanged (no degradation)

## Rollout Plan

### Step 1: Backend Changes
1. Implement `_attach_citation_context()` in V1.1 engine
2. Update `_format_sources()` to add new fields (nullable)
3. Run regression tests
4. Deploy backend

### Step 2: Frontend Changes
1. Update TypeScript types with optional fields
2. Update LegalChatInterface with graceful fallback
3. Update SourceCard component
4. Test with old responses (should still work)
5. Deploy frontend

### Step 3: Prompt Update
1. Remove "Fundamento:" from prompt
2. Monitor answer quality for 24-48 hours
3. Adjust if needed

## Timeline Estimate

- **Phase 1 (Prompt)**: 30 minutes
- **Phase 2 (Backend)**: 2-3 hours (implementation + testing)
- **Phase 3 (Frontend)**: 1-2 hours
- **Testing & QA**: 2-3 hours
- **Total**: **6-9 hours** of focused work

## Benefits

✅ **Single source of truth** - No redundant citation sections
✅ **Better UX** - Interactive, expandable sources with context
✅ **Cleaner answers** - Remove LLM-generated redundancy
✅ **Citation transparency** - User sees WHY each source was cited
✅ **Works with citation fix** - Leverages our `_attach_citations()` improvements

## Recommendation

**I recommend implementing this migration in 3 phases:**

1. **Quick win**: Remove "Fundamento:" from prompt (30 min) ✅ Safe
2. **Backend enhancement**: Add citation context extraction (2-3 hours) ⚠️ Test thoroughly
3. **Frontend polish**: Update UI to show cited vs. additional sources (1-2 hours) ✅ Safe

**Total effort**: 1 day of focused work
**Impact**: Significant UX improvement + eliminates confusion

Would you like me to proceed with implementing this migration?
