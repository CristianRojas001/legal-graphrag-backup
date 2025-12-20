# PDF URL Handling - Fix Documentation

**Issue**: Excel file contains PDF URLs that cannot be processed directly
**Impact**: Ingestion fails with `DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes`
**Status**: ✅ Fixed

---

## Problem Description

### Issue 1: Excel File Has PDF URLs

Some sources in `corpus_normativo_artisting_enriched.xlsx` have PDF URLs instead of HTML URLs:

**Example**:
```
https://www.boe.es/buscar/pdf/1978/BOE-A-1978-31229-consolidado.pdf
```

This should be:
```
https://www.boe.es/eli/es/c/1978/12/27/(1)/con
```

or:
```
https://www.boe.es/buscar/doc.php?id=BOE-A-1978-31229
```

### Issue 2: PDF Binary Data in PostgreSQL

When the connector fetches a PDF URL, it receives binary data containing NUL bytes (`0x00`). PostgreSQL text fields cannot store NUL bytes, causing this error:

```
django.db.utils.DataError: PostgreSQL text fields cannot contain NUL (0x00) bytes
```

The error occurs when trying to save `raw_html` field in `LegalDocument` model.

---

## Solutions Implemented

### Solution 1: BOE Connector PDF Detection & Conversion

**File**: `apps/legal_graphrag/services/ingestion/boe_connector.py`

The BOEConnector now:
1. Detects PDF URLs (checks for `.pdf` extension or `/pdf/` in URL)
2. Extracts the BOE ID (e.g., `BOE-A-1978-31229`)
3. Converts to HTML URL: `https://www.boe.es/buscar/doc.php?id={boe_id}`
4. Fetches the HTML version instead

**Code**:
```python
def fetch(self, url: str) -> Dict:
    # Check if URL points to PDF
    if url.endswith('.pdf') or '/pdf/' in url.lower():
        logger.warning(f"PDF URL detected: {url}")

        # Convert to HTML URL
        html_url = self._convert_pdf_to_html_url(url)
        if html_url:
            logger.info(f"Converted to HTML URL: {html_url}")
            url = html_url
        else:
            raise ValueError(f"Cannot process PDF URL: {url}")

    # Continue with HTML fetching...
```

**Benefits**:
- Automatic conversion at runtime
- No manual URL fixing needed
- Works even if Excel has PDF URLs

**Limitations**:
- Only works for BOE URLs (pattern: `BOE-A-YYYY-NNNNN`)
- EUR-Lex and DGT PDFs not yet supported

---

### Solution 2: Excel URL Fix Script

**File**: `backend/scripts/fix_excel_urls.py`

A utility script to check and fix PDF URLs in the Excel file.

**Usage**:

```bash
cd "d:\IT workspace\Legal GraphRAG\backend"

# Check for PDF URLs
python scripts/fix_excel_urls.py --check

# Fix PDF URLs (creates backup first)
python scripts/fix_excel_urls.py --fix
```

**What it does**:
1. Scans Excel file for PDF URLs
2. Extracts BOE ID from each PDF URL
3. Converts to HTML URL
4. Creates backup (`.xlsx.backup`)
5. Saves fixed Excel file

**Example Output**:
```
Checking URLs in: corpus_normativo_artisting_enriched.xlsx

❌ Found 3 PDF URLs:

Row 5: Ley del IRPF
  ID: BOE-A-2006-20764
  Current:   https://www.boe.es/buscar/pdf/2006/BOE-A-2006-20764-consolidado.pdf
  Suggested: https://www.boe.es/buscar/doc.php?id=BOE-A-2006-20764
```

---

## Recommended Workflow

### Option A: Fix Excel First (Recommended)

1. **Check for PDF URLs**:
   ```bash
   python scripts/fix_excel_urls.py --check
   ```

2. **Fix them**:
   ```bash
   python scripts/fix_excel_urls.py --fix
   ```

3. **Re-import corpus** (if already imported):
   ```bash
   python manage.py shell
   ```
   ```python
   from apps.legal_graphrag.models import CorpusSource
   CorpusSource.objects.all().delete()  # Delete old sources
   exit()
   ```
   ```bash
   python manage.py import_corpus_from_excel corpus_normativo_artisting_enriched.xlsx
   ```

4. **Run ingestion**:
   ```bash
   python manage.py ingest_source BOE-A-1978-31229 --sync
   ```

### Option B: Let Connector Handle It (Automatic)

If you don't fix the Excel file, the BOEConnector will automatically convert PDF URLs to HTML at runtime.

**Pros**:
- No manual intervention
- Works immediately

**Cons**:
- Slightly slower (conversion happens every time)
- Logs show warnings

---

## Future Improvements

### 1. Full PDF Support

To support actual PDF parsing (instead of conversion), we would need to:

1. **Add PDF parsing library**:
   ```bash
   pip install pypdf2 pdfplumber
   ```

2. **Implement PDF text extraction**:
   ```python
   import pdfplumber

   def _extract_pdf_text(self, pdf_content: bytes) -> str:
       with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
           text = '\n\n'.join([page.extract_text() for page in pdf.pages])
       return text
   ```

3. **Store PDF as file instead of database**:
   - Save PDF to filesystem: `media/legal_pdfs/{boe_id}.pdf`
   - Store path in database instead of binary content

**Not implemented yet** because:
- HTML versions provide better structure (articles, sections)
- PDF parsing is less reliable
- Adds complexity

---

## Testing

After implementing the fix, test with:

```bash
# Test with a PDF URL
python manage.py shell
```

```python
from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector

connector = BOEConnector()
result = connector.fetch('https://www.boe.es/buscar/pdf/1978/BOE-A-1978-31229-consolidado.pdf')

print(f"Fetched: {result['metadata'].get('titulo')}")
print(f"Structure chunks: {len(result['structure'])}")
print(f"HTML length: {len(result['html'])}")
```

**Expected output**:
```
WARNING ... PDF URL detected: https://www.boe.es/buscar/pdf/1978/BOE-A-1978-31229-consolidado.pdf
INFO ... Converted to HTML URL: https://www.boe.es/buscar/doc.php?id=BOE-A-1978-31229
Fetched: Constitución Española
Structure chunks: 169
HTML length: 245678
```

---

## Summary

| Problem | Solution | Status |
|---------|----------|--------|
| Excel has PDF URLs | Use `fix_excel_urls.py` script | ✅ Script created |
| Connector fetches PDFs | Auto-convert to HTML in BOEConnector | ✅ Implemented |
| NUL bytes in PostgreSQL | Never store binary PDF data | ✅ Prevented |

**Next Steps for User**:
1. Run `python scripts/fix_excel_urls.py --check` to see if your Excel has PDF URLs
2. If yes, run `python scripts/fix_excel_urls.py --fix` to fix them
3. Re-import corpus if needed
4. Proceed with testing

---

**Created**: 2025-12-12
**Author**: Claude
**Related Files**:
- `apps/legal_graphrag/services/ingestion/boe_connector.py` (updated)
- `backend/scripts/fix_excel_urls.py` (new)
