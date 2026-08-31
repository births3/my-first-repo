#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "working" / "compact"
FILES = {
    "2021": ROOT / "data/2021/zhejiang.jsonl",
    "2022": ROOT / "data/2022/zhejiang.jsonl",
    "2023": ROOT / "data/2023/new-gaokao-1.jsonl",
    "2024": ROOT / "data/2024/new-gaokao-1.jsonl",
    "2025": ROOT / "data/2025/national-1.jsonl",
    "2026": ROOT / "data/2026/national-1.jsonl",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for year, path in FILES.items():
        records = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            q = json.loads(line)
            records.append(
                {
                    "id": q["id"],
                    "question_no": q["question_no"],
                    "question_type": q["question_type"],
                    "stem": q.get("stem_latex") or q.get("stem"),
                    "options": q.get("options_latex") or q.get("options"),
                    "reference_answer": q.get("answer_latex") or q.get("answer"),
                    "needs_figure": bool(q.get("needs_figure")),
                    "figure_urls": q.get("figure_urls", []),
                }
            )
        target = OUT / f"{year}.jsonl"
        target.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records) + "\n",
            encoding="utf-8",
        )
        total += len(records)
        print(f"{year}: {len(records)} questions -> {target.relative_to(ROOT)}")
    print(f"total: {total}")


if __name__ == "__main__":
    main()
