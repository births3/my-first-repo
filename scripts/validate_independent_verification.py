#!/usr/bin/env python3
"""Validate the per-question independent-solution audit."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = [
    ROOT / "data/2021/zhejiang.jsonl",
    ROOT / "data/2022/zhejiang.jsonl",
    ROOT / "data/2023/new-gaokao-1.jsonl",
    ROOT / "data/2024/new-gaokao-1.jsonl",
    ROOT / "data/2025/national-1.jsonl",
    ROOT / "data/2026/national-1.jsonl",
]
AUDIT_DIR = ROOT / "independent-verification"
BASE_AUDIT_FILES = [
    AUDIT_DIR / "2021-zhejiang.part1.jsonl",
    AUDIT_DIR / "2022-zhejiang.jsonl",
    AUDIT_DIR / "2023-new-gaokao-1.jsonl",
    AUDIT_DIR / "2024-new-gaokao-1.jsonl",
    AUDIT_DIR / "2025-national-1.jsonl",
    AUDIT_DIR / "2026-national-1.jsonl",
]
SUPPLEMENT_FILES = sorted(AUDIT_DIR.glob("supplemental-proofs*.jsonl"))


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}:{number}: {exc}") from exc
    return rows


def main() -> None:
    expected: dict[str, dict] = {}
    for path in DATA_FILES:
        for row in read_jsonl(path):
            qid = row["id"]
            if qid in expected:
                raise SystemExit(f"Duplicate dataset id: {qid}")
            expected[qid] = row

    audit: dict[str, dict] = {}
    for path in BASE_AUDIT_FILES:
        for row in read_jsonl(path):
            qid = row["question_id"]
            if qid in audit:
                raise SystemExit(f"Duplicate base audit id: {qid}")
            audit[qid] = row

    for path in SUPPLEMENT_FILES:
        for row in read_jsonl(path):
            qid = row["question_id"]
            if qid not in audit:
                raise SystemExit(f"Supplement references missing base record: {qid}")
            merged = dict(audit[qid])
            merged.update(row)
            merged["status"] = row["new_status"]
            audit[qid] = merged

    unknown = sorted(set(audit) - set(expected))
    if unknown:
        raise SystemExit(f"Audit contains unknown question ids: {unknown}")

    valid_statuses = {
        "independently_verified",
        "proof_checked",
        "needs_source_review",
        "mismatch",
    }
    for qid, row in audit.items():
        status = row.get("status")
        if status not in valid_statuses:
            raise SystemExit(f"Invalid status for {qid}: {status!r}")
        if status in {"independently_verified", "proof_checked"} and row.get("derived_answer") is None:
            raise SystemExit(f"Verified record lacks derived_answer: {qid}")
        if status == "needs_source_review" and not row.get("reason"):
            raise SystemExit(f"Review record lacks reason: {qid}")

    missing = sorted(set(expected) - set(audit))
    counts = {status: 0 for status in valid_statuses}
    for row in audit.values():
        counts[row["status"]] += 1

    report = {
        "total_questions": len(expected),
        "audited_questions": len(audit),
        "missing_questions": missing,
        "status_counts": counts,
        "complete": not missing and counts["needs_source_review"] == 0 and counts["mismatch"] == 0,
    }
    (AUDIT_DIR / "computed-summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if report["complete"]:
        print("Independent solution audit is complete.")
    else:
        print("Independent solution audit is not complete yet.")


if __name__ == "__main__":
    main()
