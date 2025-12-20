# Fixes Applied - Day 2 Ingestion Pipeline

**Date**: 2025-12-12
**Status**: ✅ Ready for Testing

---

## Issues Fixed

### 1. ✅ Redis Database Isolation

**Issue**: Legal GraphRAG and infosubvenciones-api sharing same Redis instance

**Solution**: Use different database indexes
- **infosubvenciones-api**: Redis DB 0 (`redis://localhost:6379/0`)
- **Legal GraphRAG**: Redis DB 1 (`redis://localhost:6379/1`)

**Documentation Updated**:
- ✅ `docs/01_ARCHITECTURE.md` - Updated Redis configuration example
- ✅ `docs/DAY_2_COMPLETE.md` - Added note about Redis DB index 1

**Action Required**:
Ensure `backend/.env` has:
```env
REDIS_URL=redis://localhost:6379/1
```

---

### 2. ✅ PDF URL Handling

**Issue**: Excel file has PDF URLs → Connector fetches binary PDF → NUL bytes error in PostgreSQL

**Error**:
```
django.db.utils.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes
```

**Root Cause**:
- PDF binary data contains NUL bytes (`0x00`)
- PostgreSQL text field (`LegalDocument.raw_html`) cannot store NUL bytes
- BOE connector was saving binary PDF content as text

**Solution Implemented**:

#### BOEConnector Auto-Conversion
- Detects PDF URLs (`.pdf` extension or `/pdf/` in URL)
- Extracts BOE ID (e.g., `BOE-A-1978-31229`)
- Converts to HTML URL: `https://www.boe.es/buscar/doc.php?id={boe_id}`
- Fetches HTML version instead of PDF

**Code**: `apps/legal_graphrag/services/ingestion/boe_connector.py`

**Example**:
```
PDF:  https://www.boe.es/buscar/pdf/1978/BOE-A-1978-31229-consolidado.pdf
      ↓
HTML: https://www.boe.es/buscar/doc.php?id=BOE-A-1978-31229
```

#### Excel URL Fix Script
Created `backend/scripts/fix_excel_urls.py` to check and fix PDF URLs in Excel file.

**Usage**:
```bash
# Check for PDF URLs
python scripts/fix_excel_urls.py --check

# Fix them (creates backup)
python scripts/fix_excel_urls.py --fix
```

**Documentation Created**:
- ✅ `docs/PDF_URL_FIX.md` - Comprehensive fix documentation

**User Action**:
User will fix Excel URLs manually. The connector will handle PDF URLs automatically if encountered.

---

## Testing Status

### Ready for Codex Testing

**Prerequisites**:
- [x] Redis running on port 6379
- [x] REDIS_URL set to `redis://localhost:6379/1` in `.env`
- [ ] Excel file URLs fixed (user is handling this)
- [x] Gemini API key configured
- [x] Database migrations applied
- [x] Corpus sources imported

**Next Steps for Codex**:

1. **Verify Redis isolation**:
   ```bash
   redis-cli -n 1 KEYS *  # Should be empty or only Legal GraphRAG keys
   redis-cli -n 0 KEYS *  # Should show infosubvenciones keys
   ```

2. **Run quick test**:
   ```bash
   cd "d:\IT workspace\Legal GraphRAG\backend"
   python manage.py ingest_source BOE-A-1978-31229 --sync
   ```

3. **Follow testing instructions**:
   See `docs/DAY_2_TESTING_INSTRUCTIONS.md`

---

## Files Modified

### Code Changes
1. `apps/legal_graphrag/services/ingestion/boe_connector.py`
   - Added PDF detection
   - Added `_convert_pdf_to_html_url()` method
   - Updated `fetch()` to handle PDF URLs

### Documentation Created
1. `docs/PDF_URL_FIX.md` - PDF URL issue documentation
2. `backend/scripts/fix_excel_urls.py` - URL fix utility

### Documentation Updated
1. `docs/01_ARCHITECTURE.md` - Redis DB index 1 for Legal GraphRAG
2. `docs/DAY_2_COMPLETE.md` - Redis configuration note

---

## Known Limitations

1. **PDF URL Conversion**: Only works for BOE URLs (pattern: `BOE-A-YYYY-NNNNN`)
   - EUR-Lex and DGT PDF URLs not yet supported
   - Will need manual URL fixing for non-BOE PDFs

2. **Actual PDF Parsing**: Not implemented yet
   - Current solution: convert PDF URLs to HTML URLs
   - Future: implement actual PDF text extraction with `pdfplumber`

3. **URL Validation**: No validation that converted URL actually exists
   - Assumes `https://www.boe.es/buscar/doc.php?id={boe_id}` is always valid

---

## Testing Checklist for Codex

- [ ] Verify Redis DB 1 is being used (check logs or `redis-cli -n 1 MONITOR`)
- [ ] Test Constitution ingestion (BOE-A-1978-31229)
- [ ] Verify no NUL bytes error occurs
- [ ] Check that `LegalDocument.raw_html` contains HTML (not binary)
- [ ] Verify DocumentChunks created with embeddings
- [ ] Test with PDF URL if one exists in Excel (should auto-convert)
- [ ] Run all unit tests
- [ ] Run integration test

---

## Rollback Plan

If issues occur:

1. **Redis conflicts**: Change back to DB 0 (or use separate Redis instance)
2. **PDF conversion fails**: Provide HTML URLs directly in Excel
3. **Connector broken**: Revert `boe_connector.py` to previous version

---

## Success Criteria

Day 2 is complete when:
- [x] Redis isolation working (DB 1 for Legal GraphRAG)
- [x] PDF URL handling implemented
- [ ] Constitution successfully ingested (Codex testing)
- [ ] No PostgreSQL NUL bytes errors
- [ ] All tests pass

---

**Status**: ✅ Fixes applied, ready for Codex testing
**Next**: Codex runs test suite per `DAY_2_TESTING_INSTRUCTIONS.md`
