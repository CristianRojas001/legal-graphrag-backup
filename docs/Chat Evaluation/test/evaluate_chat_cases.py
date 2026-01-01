import csv
import json
import os
import re
import sys
import time
import argparse
from collections import defaultdict
from statistics import mean
from pathlib import Path
from datetime import datetime, timezone
from typing import Sequence

import requests


ROOT = Path(__file__).resolve().parents[2]
CASES_PATH = ROOT / "docs" / "Chat Evaluation" / "CHAT_EVAL_50_CASES.csv"
RESULTS_PATH = ROOT / "docs" / "Chat Evaluation" / "CHAT_EVAL_50_RESULTS.csv"
SUMMARY_PATH = ROOT / "docs" / "Chat Evaluation" / "CHAT_EVAL_50_SUMMARY.txt"

API_URL = os.getenv("LEGAL_GRAPHRAG_API_URL", "http://localhost:8000")
CHAT_ENDPOINT = f"{API_URL}/api/v1/legal-graphrag/v1_1/chat/"
SEARCH_ENDPOINT = f"{API_URL}/api/v1/legal-graphrag/search/"
DEBUG_HEADER = {"X-Developer-Debug": "1"}


def _parse_cited_ids(answer: str) -> list[str]:
    if not answer:
        return []
    match = re.search(r"<!--CITED_IDS:\\s*([^>]*)-->", answer)
    if not match:
        return []
    content = match.group(1).strip()
    if not content:
        return []
    parts = [part.strip() for part in content.split(",")]
    return [part for part in parts if part]


def _extract_ids_from_sources(sources: list[dict]) -> tuple[list[str], list[str]]:
    cited = []
    additional = []
    for src in sources or []:
        doc_id = src.get("id") or src.get("document_id") or src.get("doc_id")
        if not doc_id:
            continue
        if src.get("is_cited"):
            cited.append(doc_id)
        else:
            additional.append(doc_id)
    return cited, additional


def _bool(value: bool) -> str:
    return "yes" if value else "no"


def _expected_docs_list(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(";") if part.strip()]


def _is_abstained(metadata: dict, answer: str) -> bool:
    if metadata and metadata.get("abstained") is True:
        return True
    lowered = (answer or "").lower()
    return (
        "no puedo afirmar" in lowered
        or "no tengo informacion" in lowered
        or "necesitaria mas contexto" in lowered
        or "necesito mas contexto" in lowered
    )


def _style_auto_score(answer: str) -> int:
    length = len(answer or "")
    if length < 120:
        return 0
    if length > 2200:
        return 0
    return 1


def evaluate_case_turn(row: dict, response: dict) -> dict:
    metadata = response.get("metadata") or {}
    decision = metadata.get("decision") or {}
    mode = decision.get("mode")
    answer = response.get("answer", "")
    sources = response.get("sources", [])

    cited_ids, additional_ids = _extract_ids_from_sources(sources)
    if not cited_ids:
        cited_ids = _parse_cited_ids(answer)

    expected_docs = _expected_docs_list(row["expected_docs"])
    expect_abstain = row["expect_abstain"].strip().lower() == "yes"
    abstained = _is_abstained(metadata, answer)

    citation_score = 0
    if expected_docs and not abstained:
        if all(doc in cited_ids for doc in expected_docs):
            citation_score = 2
        elif any(doc in cited_ids for doc in expected_docs):
            citation_score = 1

    abstain_score = 0
    if expect_abstain:
        abstain_score = 2 if abstained else 0
    else:
        abstain_score = 2 if not abstained else 0

    followup_ok = True
    if int(row["turn"]) > 1:
        followup_ok = mode != "CLARIFY"

    return {
        "response_mode": mode or "",
        "cited_ids": ", ".join(cited_ids),
        "additional_ids": ", ".join(additional_ids),
        "abstained": _bool(abstained),
        "citation_score": str(citation_score),
        "abstain_score": str(abstain_score),
        "followup_ok": _bool(followup_ok),
        "style_auto_score": str(_style_auto_score(answer)),
        "answer_len": str(len(answer or "")),
        "error": "",
    }


def evaluate_thread_turn(row: dict, response: dict, thread_index: int) -> dict:
    """
    Evaluate a turn that belongs to a single conversation thread (shared session_id)
    even if the underlying CSV row is turn=1 for that case_id.
    """
    payload = evaluate_case_turn(row, response)
    if thread_index > 1:
        payload["followup_ok"] = _bool(payload.get("response_mode") != "CLARIFY")
    return payload


def _search_doc_present(doc_id: str, timeout_s: int = 30) -> bool:
    """
    Best-effort presence check: ask the search endpoint for the doc_id and see if it returns it.
    """
    doc_id = (doc_id or "").strip()
    if not doc_id:
        return False
    try:
        resp = requests.post(SEARCH_ENDPOINT, json={"query": doc_id, "limit": 10}, timeout=timeout_s)
        resp.raise_for_status()
        data = resp.json() or {}
        results = data.get("results") or []
        for item in results:
            if (item.get("document_id") or "").strip() == doc_id:
                return True
    except Exception:
        return False
    return False


def _preflight_expected_docs(rows: list[dict]) -> list[dict]:
    """
    Returns a list of missing expected doc ids found via /search.
    """
    missing = []
    seen = set()
    for row in rows:
        for doc in _expected_docs_list(row.get("expected_docs", "")):
            if doc in seen:
                continue
            seen.add(doc)
            if not _search_doc_present(doc):
                missing.append({"doc_id": doc, "case_id": row.get("case_id", ""), "turn": row.get("turn", "")})
    return missing


def _parse_list_arg(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate chat cases against the v1.1 chat endpoint.")
    parser.add_argument("--api-url", default=API_URL, help="Base API URL (default from LEGAL_GRAPHRAG_API_URL).")
    parser.add_argument(
        "--cases-file",
        default=str(CASES_PATH),
        help="Custom cases CSV (default: docs/Chat Evaluation/CHAT_EVAL_50_CASES.csv).",
    )
    parser.add_argument(
        "--case-ids",
        default="",
        help="Comma-separated case_ids to run from the cases CSV (default: all).",
    )
    parser.add_argument(
        "--thread-case-ids",
        default="",
        help=(
            "Comma-separated case_ids to run as ONE continuous conversation (shared session_id). "
            "Uses CSV ordering per case (turn 1,2,...) and then the provided case order."
        ),
    )
    parser.add_argument(
        "--preflight-docs",
        action="store_true",
        help="Check that expected_docs exist via /search before running chat eval.",
    )
    parser.add_argument(
        "--results-path",
        default="",
        help="Override CSV results output path.",
    )
    parser.add_argument(
        "--summary-path",
        default="",
        help="Override summary output path.",
    )
    parser.add_argument(
        "--log-jsonl",
        default="",
        help="Write per-turn request/response logs (including developer_debug when available) as JSONL.",
    )
    parser.add_argument(
        "--max-sources",
        type=int,
        default=0,
        help="If set (>0), include max_sources in each chat request payload.",
    )
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Fail (exit code 1) if KPI thresholds are violated.",
    )
    parser.add_argument("--max-abstain-mismatch", type=int, default=999999, help="Max allowed abstain mismatches.")
    parser.add_argument("--max-citation-miss", type=int, default=999999, help="Max allowed citation misses.")
    parser.add_argument("--max-followup-fail", type=int, default=999999, help="Max allowed follow-up failures.")
    parser.add_argument("--max-latency-avg-ms", type=int, default=999999, help="Max allowed average latency (ms).")
    parser.add_argument("--max-latency-p95-ms", type=int, default=999999, help="Max allowed p95 latency (ms).")
    parser.add_argument(
        "--min-answer-len",
        type=int,
        default=0,
        help="Minimum allowed answer length (characters) for non-abstained turns (0 disables).",
    )
    parser.add_argument(
        "--max-short-answers",
        type=int,
        default=999999,
        help="Max allowed count of too-short answers (only evaluated when --min-answer-len > 0).",
    )
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    chat_endpoint = f"{api_url}/api/v1/legal-graphrag/v1_1/chat/"
    global CHAT_ENDPOINT, SEARCH_ENDPOINT
    CHAT_ENDPOINT = chat_endpoint
    SEARCH_ENDPOINT = f"{api_url}/api/v1/legal-graphrag/search/"

    cases_path = Path(args.cases_file)
    if not cases_path.exists():
        print(f"Missing cases file: {cases_path}")
        return 1

    with cases_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    case_id_filter = set(_parse_list_arg(args.case_ids))
    thread_case_ids = _parse_list_arg(args.thread_case_ids)

    if case_id_filter:
        rows = [row for row in rows if row.get("case_id") in case_id_filter]

    by_case: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_case[row["case_id"]].append(row)
    for case_rows in by_case.values():
        case_rows.sort(key=lambda r: int(r["turn"]))

    if args.preflight_docs:
        missing_docs = _preflight_expected_docs(rows)
        if missing_docs:
            print("Preflight: missing expected_docs in /search:", file=sys.stderr)
            for item in missing_docs:
                print(f"- {item['doc_id']} (from {item['case_id']} turn {item['turn']})", file=sys.stderr)
        else:
            print("Preflight: all expected_docs found via /search.")

    results = []
    summary = {}

    results_path = Path(args.results_path) if args.results_path else RESULTS_PATH
    summary_path = Path(args.summary_path) if args.summary_path else SUMMARY_PATH
    log_jsonl_path = Path(args.log_jsonl) if args.log_jsonl else None

    completed = set()
    if results_path.exists():
        with results_path.open("r", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                completed.add((row.get("case_id"), row.get("turn")))
                results.append(row)

    fieldnames = list(rows[0].keys()) + [
        "session_id",
        "response_mode",
        "cited_ids",
        "additional_ids",
        "abstained",
        "citation_score",
        "abstain_score",
        "followup_ok",
        "style_auto_score",
        "answer_len",
        "response_ms",
        "error",
    ]
    if not results_path.exists():
        with results_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()

    session_ids: dict[str, str] = {}

    def run_one_turn(row: dict, session_id: str | None, label: str, evaluator, thread_index: int | None = None) -> tuple[dict, str]:
        payload = {"query": row["user_text"]}
        if args.max_sources and args.max_sources > 0:
            payload["max_sources"] = args.max_sources
        if session_id:
            payload["session_id"] = session_id
        print(label, flush=True)
        data = {}
        error = ""
        start_time = time.perf_counter()
        try:
            response = requests.post(CHAT_ENDPOINT, json=payload, headers=DEBUG_HEADER, timeout=60)
            response.raise_for_status()
            data = response.json()
            session_id = data.get("session_id") or session_id
        except Exception as exc:
            error = f"{exc.__class__.__name__}: {exc}"
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        result = {**row, "session_id": session_id or ""}
        if data:
            if thread_index is None:
                result.update(evaluator(row, data))
            else:
                result.update(evaluator(row, data, thread_index))
            result["response_ms"] = str(elapsed_ms)
            result["error"] = error
            # flag empty responses when no sources were returned (even if metadata says no abstain)
            answer_text = (data.get("answer") or "").strip()
            metadata = data.get("metadata") or {}
            sources = data.get("sources") or []
            abstained_flag = metadata.get("abstained") is True
            if not answer_text and not sources and not abstained_flag:
                result["error"] = result.get("error") or "empty_answer"
        else:
            result.update({
                "response_mode": "",
                "cited_ids": "",
                "additional_ids": "",
                "abstained": "no",
                "citation_score": "0",
                "abstain_score": "0",
                "followup_ok": "yes",
                "style_auto_score": "0",
                "answer_len": "0",
                "response_ms": str(elapsed_ms),
                "error": error,
            })
        with results_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writerow(result)

        if log_jsonl_path is not None:
            log_jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "case_id": row.get("case_id"),
                "turn": row.get("turn"),
                "area": row.get("area"),
                "thread_index": thread_index,
                "request": payload,
                "session_id": session_id or "",
                "response_ms": elapsed_ms,
                "response": data,
                "error": error,
            }
            with log_jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        return result, session_id or ""

    if thread_case_ids:
        thread_rows: list[dict] = []
        for cid in thread_case_ids:
            thread_rows.extend(by_case.get(cid, []))
        session_id = None
        thread_index = 0
        for row in thread_rows:
            thread_index += 1
            turn_key = (row.get("case_id"), row.get("turn"))
            if turn_key in completed:
                continue
            label = f"[THREAD][{row['case_id']}][turn {row['turn']}][idx {thread_index}] sending"
            result, session_id = run_one_turn(row, session_id, label, evaluate_thread_turn, thread_index=thread_index)
            results.append(result)
        session_ids["THREAD"] = session_id or ""
    else:
        for case_id, case_rows in by_case.items():
            session_id = None
            for row in case_rows:
                if (row["case_id"], row["turn"]) in completed:
                    continue
                label = f"[{case_id}][turn {row['turn']}] sending"
                result, session_id = run_one_turn(row, session_id, label, evaluate_case_turn)
                results.append(result)
            session_ids[case_id] = session_id or ""

    _deduplicate_results(results_path, fieldnames)
    with results_path.open("r", encoding="utf-8") as handle:
        all_results = list(csv.DictReader(handle))

    summary = {
        "total_turns": 0,
        "abstain_mismatch": 0,
        "citation_miss": 0,
        "followup_fail": 0,
        "short_answers": 0,
        "latencies_ms": [],
        "by_area": defaultdict(int),
        "by_doc_miss": defaultdict(int),
    }
    for row in all_results:
        summary["total_turns"] += 1
        summary["by_area"][row["area"]] += 1
        if row["abstained"] == "yes" and row["expect_abstain"] == "no":
            summary["abstain_mismatch"] += 1
        if row["abstained"] == "no" and row["expect_abstain"] == "yes":
            summary["abstain_mismatch"] += 1
        if row["expected_docs"] and row["citation_score"] == "0" and not row["error"]:
            summary["citation_miss"] += 1
            for doc in _expected_docs_list(row["expected_docs"]):
                summary["by_doc_miss"][doc] += 1
        if row["turn"] != "1" and row["followup_ok"] == "no" and not row["error"]:
            summary["followup_fail"] += 1
        try:
            answer_len = int(row.get("answer_len") or "0")
        except ValueError:
            answer_len = 0
        if args.min_answer_len and args.min_answer_len > 0:
            if row.get("abstained") == "no" and not row.get("error") and answer_len < args.min_answer_len:
                summary["short_answers"] += 1
        if row.get("response_ms"):
            try:
                summary["latencies_ms"].append(int(row["response_ms"]))
            except ValueError:
                pass

    latencies = summary["latencies_ms"]
    latencies_sorted = sorted(latencies)
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95) - 1] if latencies_sorted else 0
    avg = int(mean(latencies)) if latencies else 0
    summary_lines = [
        f"Total turns: {summary['total_turns']}",
        f"Abstain mismatches: {summary['abstain_mismatch']}",
        f"Citation misses: {summary['citation_miss']}",
        f"Follow-up failures: {summary['followup_fail']}",
        f"Short answers (<{args.min_answer_len} chars, non-abstained): {summary['short_answers']}" if args.min_answer_len else "Short answers: (disabled)",
        f"Latency avg ms: {avg}",
        f"Latency p95 ms: {p95}",
        "",
        "By area:",
    ]
    for area, count in sorted(summary["by_area"].items()):
        summary_lines.append(f"- {area}: {count}")
    summary_lines.append("")
    summary_lines.append("Most missed expected docs:")
    for doc, count in sorted(summary["by_doc_miss"].items(), key=lambda kv: kv[1], reverse=True):
        summary_lines.append(f"- {doc}: {count}")

    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print(f"Wrote results: {results_path}")
    print(f"Wrote summary: {summary_path}")

    violations = []
    if summary["abstain_mismatch"] > args.max_abstain_mismatch:
        violations.append(f"abstain_mismatch={summary['abstain_mismatch']} > {args.max_abstain_mismatch}")
    if summary["citation_miss"] > args.max_citation_miss:
        violations.append(f"citation_miss={summary['citation_miss']} > {args.max_citation_miss}")
    if summary["followup_fail"] > args.max_followup_fail:
        violations.append(f"followup_fail={summary['followup_fail']} > {args.max_followup_fail}")
    if avg > args.max_latency_avg_ms:
        violations.append(f"latency_avg_ms={avg} > {args.max_latency_avg_ms}")
    if p95 > args.max_latency_p95_ms:
        violations.append(f"latency_p95_ms={p95} > {args.max_latency_p95_ms}")
    if args.min_answer_len and args.min_answer_len > 0:
        if summary["short_answers"] > args.max_short_answers:
            violations.append(f"short_answers={summary['short_answers']} > {args.max_short_answers}")

    if args.enforce and violations:
        print("KPI threshold violations:", file=sys.stderr)
        for item in violations:
            print(f"- {item}", file=sys.stderr)
        return 1

    return 0


def _deduplicate_results(path: Path, fieldnames: Sequence[str]) -> None:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    unique: dict[tuple[str, str], dict] = {}
    for row in rows:
        key = (row.get("case_id", ""), row.get("turn", ""))
        if key[0] or key[1]:
            unique[key] = row

    def _sort_key(record: dict) -> tuple[str, int]:
        turn_value = record.get("turn") or "0"
        try:
            turn_int = int(turn_value)
        except ValueError:
            turn_int = 0
        return (record.get("case_id", ""), turn_int)

    sorted_rows = sorted(unique.values(), key=_sort_key)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in sorted_rows:
            writer.writerow(row)


if __name__ == "__main__":
    sys.exit(main())
