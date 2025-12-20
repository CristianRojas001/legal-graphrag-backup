"""
Quick test script to verify BOE parser works with doc.php format
"""

import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Set up Django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ovra_backend.settings')
import django
django.setup()

from apps.legal_graphrag.services.ingestion.boe_connector import BOEConnector

def test_boe_parser():
    """Test BOE connector with Constitution"""
    print("Testing BOE parser with Constitution...")
    print("-" * 60)

    connector = BOEConnector()

    # Test with doc.php URL (what PDF URLs convert to)
    url = 'https://www.boe.es/buscar/doc.php?id=BOE-A-1978-31229'
    print(f"\nFetching: {url}")

    result = connector.fetch(url)

    print(f"\n✅ Fetch successful!")
    print(f"   HTML length: {len(result['html'])} chars")
    print(f"   Content length: {len(result['content'])} chars")
    print(f"   Articles found: {len(result['structure'])}")

    if result['structure']:
        print(f"\n📄 First 3 articles:")
        for article in result['structure'][:3]:
            print(f"\n   {article['label']}")
            text_preview = article['text'][:100] if article['text'] else '(empty)'
            print(f"   Text: {text_preview}...")
            print(f"   Full text length: {len(article['text'])} chars")
    else:
        print("\n❌ No articles parsed!")
        return False

    # Check if articles have text
    empty_count = sum(1 for a in result['structure'] if not a['text'])
    if empty_count > 0:
        print(f"\n⚠️  Warning: {empty_count} articles have empty text")
        return False

    print(f"\n✅ All {len(result['structure'])} articles have text content!")
    return True


if __name__ == '__main__':
    success = test_boe_parser()
    sys.exit(0 if success else 1)
