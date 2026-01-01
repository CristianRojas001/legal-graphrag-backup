"""
Manual Smoke Test for Operational Memory V1.1

Run against live backend to verify:
1. Topic lock prevents drift
2. Session state persists
3. Logs show merge attempts

Usage:
    python apps/legal_graphrag/tests/smoke_test_manual_v1_1.py
"""

import requests
import json
import uuid
from time import sleep


BASE_URL = "http://localhost:8000/api/v1/legal-graphrag/v1_1/chat/"


def test_topic_lock_prevents_drift():
    """
    Critical test: Topic lock prevents IVA drift

    Turn 1: "Soy autónomo músico. ¿Qué gastos suelen ser deducibles en IRPF...?"
        Expected: area=Fiscal, topic_lock=Fiscal

    Turn 2: "si toco en un restaurante por 120 euros, lo declaro?"
        Expected: Stays in Fiscal (no IVA drift)
                  forced_area=Fiscal OR area_principal=Fiscal
    """
    print("\n" + "="*80)
    print("TEST: Topic Lock Prevents Drift")
    print("="*80)

    session_id = str(uuid.uuid4())
    print(f"Session ID: {session_id}\n")

    # Turn 1
    print("Turn 1:")
    print("Query: Soy autónomo músico. ¿Qué gastos suelen ser deducibles en IRPF...?")

    r1 = requests.post(BASE_URL, json={
        "query": "Soy autónomo músico. ¿Qué gastos suelen ser deducibles en IRPF y cuáles son típicamente problemáticos?",
        "session_id": session_id,
    })

    assert r1.status_code == 200, f"Turn 1 failed: {r1.status_code}"

    meta1 = r1.json()["metadata"]
    print(f"  Area principal: {meta1.get('area_principal')}")
    print(f"  Pending slots: {meta1.get('pending_slots', [])}")
    print(f"  Fallback used: {meta1.get('fallback_used', False)}")
    print()

    # Verify Turn 1
    assert meta1.get("area_principal") == "Fiscal", f"Expected Fiscal, got {meta1.get('area_principal')}"

    sleep(1)

    # Turn 2
    print("Turn 2:")
    print("Query: si toco en un restaurante por 120 euros, lo declaro?")

    r2 = requests.post(BASE_URL, json={
        "query": "si toco en un restaurante por 120 euros, lo declaro?",
        "session_id": session_id,
    })

    assert r2.status_code == 200, f"Turn 2 failed: {r2.status_code}"

    meta2 = r2.json()["metadata"]
    print(f"  Area principal: {meta2.get('area_principal')}")
    print(f"  Forced area: {meta2.get('forced_area')}")
    print(f"  Fallback used: {meta2.get('fallback_used', False)}")
    print(f"  Fallback reason: {meta2.get('fallback_reason', 'N/A')}")
    print()

    # CRITICAL VERIFICATION
    effective_area = meta2.get("forced_area") or meta2.get("area_principal")
    print(f"✅ Effective area: {effective_area}")

    assert effective_area == "Fiscal", f"❌ DRIFT DETECTED: Expected Fiscal, got {effective_area}"
    print("✅ TEST PASSED: Topic lock prevented drift to IVA")

    # Check answer preview
    answer_preview = r2.json()["answer"][:200]
    print(f"\nAnswer preview: {answer_preview}...")

    return session_id


def test_slot_fill_flow():
    """
    Test slot fill with topic lock

    Turn 1: "¿Deducciones fiscales para autónomos?"
        Expected: pending_slots=["location"] (if answer asks for it)

    Turn 2: "Valencia"
        Expected: slot_fill, merged_query
    """
    print("\n" + "="*80)
    print("TEST: Slot Fill Flow")
    print("="*80)

    session_id = str(uuid.uuid4())
    print(f"Session ID: {session_id}\n")

    # Turn 1
    print("Turn 1:")
    print("Query: ¿Qué deducciones fiscales tengo como autónomo?")

    r1 = requests.post(BASE_URL, json={
        "query": "¿Qué deducciones fiscales tengo como autónomo?",
        "session_id": session_id,
    })

    assert r1.status_code == 200

    meta1 = r1.json()["metadata"]
    print(f"  Area principal: {meta1.get('area_principal')}")
    print(f"  Pending slots: {meta1.get('pending_slots', [])}")
    print()

    if meta1.get("pending_slots"):
        sleep(1)

        # Turn 2
        print("Turn 2:")
        print("Query: Barcelona")

        r2 = requests.post(BASE_URL, json={
            "query": "Barcelona",
            "session_id": session_id,
        })

        assert r2.status_code == 200

        meta2 = r2.json()["metadata"]
        print(f"  Follow-up: {meta2.get('follow_up', False)}")
        print(f"  Follow-up reason: {meta2.get('follow_up_reason', 'N/A')}")
        print(f"  Slot filled: {meta2.get('slot_filled', 'N/A')}")
        print(f"  Merged query: {meta2.get('merged_query', 'N/A')[:100]}...")
        print()

        if meta2.get("follow_up_reason") == "slot_fill":
            print("✅ Slot fill detected")
        else:
            print(f"⚠️  Expected slot_fill, got: {meta2.get('follow_up_reason')}")
    else:
        print("⚠️  No pending slots in Turn 1 (answer didn't ask for location)")

    return session_id


def check_logs(session_id: str):
    """
    Check if operational memory events are logged

    Look for:
    - opmem_merge_attempt
    - opmem_forced_area
    """
    print("\n" + "="*80)
    print("LOG VERIFICATION")
    print("="*80)

    import os
    log_file = "logs/query_flow_v1_1.jsonl"

    if not os.path.exists(log_file):
        print(f"❌ Log file not found: {log_file}")
        return

    print(f"Searching logs for session_id: {session_id[:8]}...\n")

    found_session = False
    found_merge = False
    found_forced_area = False

    with open(log_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                log = json.loads(line)
                if log.get("session_id") == session_id:
                    found_session = True

                    # Check for op-mem events
                    steps = log.get("steps", {})

                    if "opmem_merge_attempt" in steps:
                        found_merge = True
                        merge_data = steps["opmem_merge_attempt"]
                        print(f"✅ opmem_merge_attempt found:")
                        print(f"   Reason: {merge_data.get('reason')}")
                        print(f"   Success: {merge_data.get('merge_success')}")

                    if "opmem_forced_area" in steps:
                        found_forced_area = True
                        forced_data = steps["opmem_forced_area"]
                        print(f"✅ opmem_forced_area found:")
                        print(f"   Used: {forced_data.get('used_forced_area')}")
                        print(f"   Value: {forced_data.get('forced_area_value')}")

            except json.JSONDecodeError:
                continue

    if not found_session:
        print(f"⚠️  No logs found for session {session_id[:8]}")
    else:
        print()
        if found_merge:
            print("✅ Merge attempt logging verified")
        else:
            print("⚠️  No opmem_merge_attempt events (may be expected if no merges occurred)")

        if found_forced_area:
            print("✅ Forced area logging verified")
        else:
            print("⚠️  No opmem_forced_area events")


if __name__ == "__main__":
    print("\n" + "="*80)
    print("OPERATIONAL MEMORY V1.1 - MANUAL SMOKE TEST")
    print("="*80)
    print("\nNOTE: Make sure backend is running at http://localhost:8000\n")

    try:
        # Test 1: Critical - Topic lock prevents drift
        session1 = test_topic_lock_prevents_drift()

        # Test 2: Slot fill flow
        session2 = test_slot_fill_flow()

        # Verify logs
        check_logs(session1)

        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETED")
        print("="*80)

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        exit(1)
    except requests.exceptions.ConnectionError:
        print("\n❌ Backend not reachable. Start the server first:")
        print("   cd backend && python manage.py runserver")
        exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
