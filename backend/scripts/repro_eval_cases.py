import csv
import json
import os
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "docs" / "Chat Evaluation" / "CHAT_EVAL_50_CASES.csv"
TRACE_PATH = ROOT / "logs" / "chat_trace_v1_1.jsonl"
OUTPUT_DIR = ROOT / "docs" / "debug" / "responses"
TRACE_OUT = ROOT / "docs" / "debug" / "traces"

API_URL = os.getenv("LEGAL_GRAPHRAG_API_URL", "http://localhost:8000")
CHAT_ENDPOINT = f"{API_URL}/api/v1/legal-graphrag/v1_1/chat/"
DEBUG_HEADER = {"X-Developer-Debug": "1"}

TARGETS = {
    ("F08", "1"),
    ("L14", "1"),
    ("P29", "1"),
}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_OUT.mkdir(parents=True, exist_ok=True)

    with CASES_PATH.open("r", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if (row["case_id"], row["turn"]) in TARGETS]

    session_ids = {}
    for row in rows:
        payload = {"query": row["user_text"], "case_id": row["case_id"], "turn": int(row["turn"])}
        session_id = session_ids.get(row["case_id"])
        if session_id:
            payload["session_id"] = session_id
        response = requests.post(CHAT_ENDPOINT, json=payload, headers=DEBUG_HEADER, timeout=120)
        response.raise_for_status()
        data = response.json()
        session_id = data.get("session_id") or session_id
        session_ids[row["case_id"]] = session_id

        out_file = OUTPUT_DIR / f"{row['case_id']}_turn{row['turn']}.json"
        out_file.write_text(json.dumps({
            "request": payload,
            "response": data,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    if TRACE_PATH.exists():
        traces = []
        with TRACE_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                case_id = payload.get("orchestrator_input", {}).get("case_id")
                turn = payload.get("orchestrator_input", {}).get("turn")
                if case_id and turn and (str(case_id), str(turn)) in TARGETS:
                    traces.append(payload)
        trace_out_file = TRACE_OUT / "trace_F08_L14_P29.json"
        trace_out_file.write_text(json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Repro complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
