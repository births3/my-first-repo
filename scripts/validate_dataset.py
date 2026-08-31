#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "data/2021/zhejiang.jsonl": 22,
    "data/2022/zhejiang.jsonl": 22,
    "data/2023/new-gaokao-1.jsonl": 22,
    "data/2024/new-gaokao-1.jsonl": 19,
    "data/2025/national-1.jsonl": 19,
    "data/2026/national-1.jsonl": 19,
}
errors = []
all_ids = set()
for rel, expected in EXPECTED.items():
    path = ROOT / rel
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) != expected:
        errors.append(f"{rel}: {len(rows)} != {expected}")
    if [r.get("question_no") for r in rows] != list(range(1, expected + 1)):
        errors.append(f"{rel}: question_no 不连续")
    for row in rows:
        qid = row.get("id")
        if not qid or qid in all_ids:
            errors.append(f"{rel}: ID 缺失或重复 {qid}")
        all_ids.add(qid)
        if not row.get("stem") or row.get("answer") is None:
            errors.append(f"{qid}: 题干或答案缺失")
        if row.get("question_type") in {"single_choice", "multiple_choice"}:
            if set((row.get("options") or {}).keys()) != set("ABCD"):
                errors.append(f"{qid}: 四选项不完整")
        if row.get("verification", {}).get("status") not in {"verified", "verified_with_figure_dependency"}:
            errors.append(f"{qid}: 校验状态未收口")

for analysis_path in sorted((ROOT / "analysis").glob("*.json")):
    items = json.loads(analysis_path.read_text(encoding="utf-8"))
    ids = {item.get("question_id") or item.get("id") for item in items}
    expected_ids = {qid for qid in all_ids if qid.startswith(analysis_path.stem)}
    if ids != expected_ids:
        errors.append(f"{analysis_path.relative_to(ROOT)}: 解析 ID 与题目不一致")

if errors:
    print("校验失败：")
    for error in errors:
        print("-", error)
    raise SystemExit(1)
print(f"校验通过：{len(EXPECTED)} 套，{len(all_ids)} 道题。")
