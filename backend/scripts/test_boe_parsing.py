"""
Quick test script for BOE parsing

Tests the BOE connector with Constitution URL to verify parsing works
"""

import sys
from pathlib import Path

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Set up Django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')

import django
django.setup()

from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector

def test_constitution():
    """Test fetching and parsing Spanish Constitution"""
    print("=" * 60)
    print("Testing BOE Connector with Spanish Constitution")
    print("=" * 60)

    connector = BOEConnector()
    url = 'https://www.boe.es/buscar/doc.php?id=BOE-A-1978-31229'

    print(f"\nFetching: {url}\n")

    try:
        result = connector.fetch(url)

        print("[OK] Fetch successful!")
        print(f"\n[RESULTS]")
        print(f"  - HTML length: {len(result['html'])} chars")
        print(f"  - Content length: {len(result['content'])} chars")
        print(f"  - Articles parsed: {len(result['structure'])}")

        if result['metadata']:
            print(f"\n[METADATA]")
            for key, value in result['metadata'].items():
                if value:
                    print(f"  - {key}: {value}")

        if result['structure']:
            print(f"\n[ARTICLES] First 5:")
            for article in result['structure'][:5]:
                text_preview = article['text'][:80] + '...' if len(article['text']) > 80 else article['text']
                print(f"  {article['label']}: {text_preview}")
                print(f"    (Full text length: {len(article['text'])} chars)")

            # Check for empty articles
            empty_count = sum(1 for a in result['structure'] if not a['text'])
            if empty_count > 0:
                print(f"\n[WARNING] {empty_count} articles have empty text!")
            else:
                print(f"\n[OK] All {len(result['structure'])} articles have text content")

        else:
            print("\n[ERROR] No articles parsed!")

        return result

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    result = test_constitution()

    if result and result['structure'] and all(a['text'] for a in result['structure']):
        print("\n" + "=" * 60)
        print("[PASS] TEST PASSED - Ready for ingestion!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("[FAIL] TEST FAILED - Parser needs fixes")
        print("=" * 60)
        sys.exit(1)
