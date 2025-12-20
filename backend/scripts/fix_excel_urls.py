"""
Script to check and fix PDF URLs in the Excel corpus file

Usage:
    python scripts/fix_excel_urls.py --check    # Check for PDF URLs
    python scripts/fix_excel_urls.py --fix      # Convert PDF URLs to HTML
"""

import pandas as pd
import re
import sys
from pathlib import Path

# Add parent directory to path to import Django settings
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

EXCEL_PATH = BASE_DIR.parent / 'corpus_normativo_artisting_enriched.xlsx'


def convert_pdf_to_html_url(pdf_url: str) -> str:
    """
    Convert BOE PDF URL to HTML URL

    Example:
    PDF:  https://www.boe.es/buscar/pdf/1978/BOE-A-1978-31229-consolidado.pdf
    HTML: https://www.boe.es/buscar/doc.php?id=BOE-A-1978-31229
    """
    # Extract BOE ID
    match = re.search(r'(BOE-A-\d{4}-\d+)', pdf_url)
    if not match:
        return pdf_url  # Can't convert, return original

    boe_id = match.group(1)
    html_url = f"https://www.boe.es/buscar/doc.php?id={boe_id}"

    return html_url


def check_urls():
    """Check for PDF URLs in Excel file"""
    print(f"Checking URLs in: {EXCEL_PATH}")

    df = pd.read_excel(EXCEL_PATH)

    pdf_urls = []
    for idx, row in df.iterrows():
        url = row['URL oficial']
        if pd.notna(url) and (url.endswith('.pdf') or '/pdf/' in str(url).lower()):
            pdf_urls.append({
                'row': idx + 2,  # +2 because Excel is 1-indexed and has header
                'id_oficial': row['ID oficial'],
                'titulo': row['Norma / fuente (título resumido)'],
                'url': url,
                'converted': convert_pdf_to_html_url(url)
            })

    if pdf_urls:
        print(f"\n❌ Found {len(pdf_urls)} PDF URLs:\n")
        for item in pdf_urls:
            print(f"Row {item['row']}: {item['titulo']}")
            print(f"  ID: {item['id_oficial']}")
            print(f"  Current:   {item['url']}")
            print(f"  Suggested: {item['converted']}")
            print()
    else:
        print("\n✅ No PDF URLs found! All URLs are HTML.")

    return pdf_urls


def fix_urls():
    """Convert PDF URLs to HTML URLs and save Excel file"""
    print(f"Fixing URLs in: {EXCEL_PATH}")

    df = pd.read_excel(EXCEL_PATH)

    fixed_count = 0
    for idx, row in df.iterrows():
        url = row['URL oficial']
        if pd.notna(url) and (url.endswith('.pdf') or '/pdf/' in str(url).lower()):
            original_url = url
            new_url = convert_pdf_to_html_url(url)
            df.at[idx, 'URL oficial'] = new_url
            fixed_count += 1

            print(f"Row {idx + 2}: {row['Norma / fuente (título resumido)']}")
            print(f"  {original_url}")
            print(f"  → {new_url}")
            print()

    if fixed_count > 0:
        # Save backup
        backup_path = EXCEL_PATH.with_suffix('.xlsx.backup')
        import shutil
        shutil.copy(EXCEL_PATH, backup_path)
        print(f"✅ Backup saved to: {backup_path}")

        # Save fixed file
        df.to_excel(EXCEL_PATH, index=False)
        print(f"✅ Fixed {fixed_count} URLs and saved to: {EXCEL_PATH}")
    else:
        print("\n✅ No PDF URLs to fix!")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/fix_excel_urls.py --check")
        print("  python scripts/fix_excel_urls.py --fix")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == '--check':
        check_urls()
    elif mode == '--fix':
        fix_urls()
    else:
        print(f"Unknown mode: {mode}")
        print("Use --check or --fix")
        sys.exit(1)
