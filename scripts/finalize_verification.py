#!/usr/bin/env python3
"""Finalize the 2021-2026 Gaokao math verification result.

This post-processing step runs after ``sync_and_validate.py``. It has two jobs:

1. Normalize human-readable LaTeX without corrupting commands such as ``\\in``,
   ``\\int`` or ``\\Rightarrow`` (the original synchronizer used broad string
   replacements for custom one-letter macros).
2. Adjudicate three documented 2025 disagreements where the GaokaoWiki page is
   inconsistent with the source paper, the pinned transcription, other
   independent answer sets, and direct mathematical recomputation.

No disagreement is silently discarded: the original secondary answer and the
reason for the adjudication are written to a machine-readable resolution log.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TODAY = date.today().isoformat()

DATA_FILES = (
    "data/2021/zhejiang.jsonl",
    "data/2022/zhejiang.jsonl",
    "data/2023/new-gaokao-1.jsonl",
    "data/2024/new-gaokao-1.jsonl",
    "data/2025/national-1.jsonl",
    "data/2026/national-1.jsonl",
)
ANALYSIS_FILES = (
    "analysis/2021-zhejiang.json",
    "analysis/2022-zhejiang.json",
    "analysis/2023-new-gaokao-1.json",
    "analysis/2024-new-gaokao-1.json",
    "analysis/2025-national-1.json",
    "analysis/2026-national-1.json",
)
REPORT_FILES = (
    "verification/2021-zhejiang.json",
    "verification/2022-zhejiang.json",
    "verification/2023-new-gaokao-1.json",
    "verification/2024-new-gaokao-1.json",
    "verification/2025-national-1.json",
    "verification/2026-national-1.json",
)

# The GaokaoWiki answer excerpt is retained verbatim so the conflict remains
# auditable. The decision uses the source PDF identity, a pinned independent
# transcription, additional published answer sets, and direct recomputation.
RESOLUTIONS: dict[str, dict[str, Any]] = {
    "2025-national-1-04": {
        "question_no": 4,
        "canonical_answer": "B",
        "secondary_answer": "C",
        "secondary_source": "GaokaoWiki 2025 浙江数学 q04 页面",
        "decision": "canonical_answer_confirmed",
        "reason": (
            "y=2tan(x-π/3) 的全部对称中心为 (π/3+kπ,0)，k∈Z；"
            "a>0 时最小值为 π/3，对应 B。"
        ),
        "support": [
            "deekur/gaokaomath 原始 PDF（Git blob SHA 已核）",
            "DxAThing/Gaokao-Math-Problems-Compilation 固定转写与解析",
            "中国教育在线 2025 全国一卷数学答案页",
            "21世纪教育网 2025 全国一卷试题与解析",
            "独立数学推导",
        ],
    },
    "2025-national-1-09": {
        "question_no": 9,
        "canonical_answer": ["B", "D"],
        "secondary_answer": "BC",
        "secondary_source": "GaokaoWiki 2025 浙江数学 q09 页面",
        "decision": "canonical_answer_confirmed",
        "reason": (
            "正三棱柱中 BC⊥AD 且 BC⊥AA₁，故 B₁C₁∥BC⊥平面 AA₁D；"
            "CC₁∥AA₁ 且 CC₁ 不在平面 AA₁D 内，故 CC₁∥平面 AA₁D。"
            "A、C 均不成立，因此答案为 BD。"
        ),
        "support": [
            "deekur/gaokaomath 原始 PDF（Git blob SHA 已核）",
            "DxAThing/Gaokao-Math-Problems-Compilation 固定转写与解析",
            "21世纪教育网多份独立讲义/解析均给出 BD",
            "独立空间几何推导",
        ],
    },
    "2025-national-1-13": {
        "question_no": 13,
        "canonical_answer": "2",
        "secondary_answer": "±2",
        "secondary_source": "GaokaoWiki 2025 浙江数学 q13 页面",
        "decision": "canonical_answer_confirmed",
        "reason": (
            "S₈=S₄(1+q⁴)，由 68=4(1+q⁴) 得 q⁴=16。"
            "题设等比数列各项均为正数，因此 q>0，只能取 q=2。"
        ),
        "support": [
            "deekur/gaokaomath 原始 PDF（Git blob SHA 已核）",
            "DxAThing/Gaokao-Math-Problems-Compilation 固定转写与解析",
            "独立数列推导",
        ],
    },
}

QUESTION_NOTES = {
    "2025-national-1-04": "多源冲突已裁决：GaokaoWiki 标为 C；原卷、固定参考转写、其他答案集及数学推导均支持 B（π/3）。",
    "2025-national-1-09": "多源冲突已裁决：GaokaoWiki 标为 BC；原卷、固定参考转写、其他解析及空间几何推导均支持 BD。",
    "2025-national-1-11": "完整题面与逐项推导确认 A、B、C 正确，D 错误；此前 ACD 结论已撤销并在校验链路中纠正。",
    "2025-national-1-13": "多源冲突已裁决：由各项均为正数可知公比 q>0，因此 q=2，不取 -2。",
}

FIGURE_RE = re.compile(r"\\(?:bitmapfigure|includegraphics)(?:\[[^\]]*\])?\{([^{}]+)\}", re.S)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise RuntimeError(f"{path}:{lineno} 不是 JSON 对象")
        rows.append(value)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )


def strip_latex_comments(text: str) -> str:
    output: list[str] = []
    for line in text.splitlines():
        cut: int | None = None
        for idx, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            cursor = idx - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = idx
                break
        output.append(line if cut is None else line[:cut])
    return "\n".join(output)


def replace_exact_command(text: str, command: str, replacement: str) -> str:
    pattern = re.compile(re.escape(command) + r"(?![A-Za-z])")
    return pattern.sub(lambda _match: replacement, text)


def repair_legacy_macro_corruption(text: str) -> str:
    # Reverse only cases in which the replacement is immediately followed by
    # letters. A legitimate imaginary unit/exponential constant should not be
    # glued to the next command name without an operator or space.
    text = re.sub(r"\\mathrm\{i\}(?=[A-Za-z])", r"\\i", text)
    text = re.sub(r"\\mathrm\{e\}(?=[A-Za-z])", r"\\e", text)
    text = re.sub(r"\\mathbb\{R\}(?=[A-Za-z])", r"\\R", text)
    text = re.sub(r"\\mathbb\{N\}(?=[A-Za-z])", r"\\N", text)
    return text


def clean_latex_safely(text: str) -> str:
    text = strip_latex_comments(text)
    text = FIGURE_RE.sub(" [图] ", text)
    text = re.sub(r"\\FigureLayoutDeclare\{.*?\}\{.*?\}\{.*?\}", "", text, flags=re.S)
    text = text.replace(r"\begin{center}", "").replace(r"\end{center}", "")
    text = text.replace(r"\(", "$ ").replace(r"\)", " $")
    text = text.replace(r"\[", "$$ ").replace(r"\]", " $$")
    text = text.replace(r"\fillinblank{}", "____")
    text = replace_exact_command(text, r"\dfrac", r"\frac")
    text = replace_exact_command(text, r"\R", r"\mathbb{R}")
    text = replace_exact_command(text, r"\N", r"\mathbb{N}")
    text = replace_exact_command(text, r"\e", r"\mathrm{e}")
    text = replace_exact_command(text, r"\i", r"\mathrm{i}")
    text = replace_exact_command(text, r"\quad", " ")
    text = re.sub(r"\\bs\{([^{}]+)\}", r"\\vec{\1}", text)
    text = text.replace(r"\begin{enumerate}", " ").replace(r"\end{enumerate}", " ")
    text = re.sub(r"\\item(?:\[[^\]]*\])?", "；", text)
    text = repair_legacy_macro_corruption(text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?:；\s*){2,}", "；", text)
    return text


def deep_repair(value: Any) -> Any:
    if isinstance(value, str):
        return repair_legacy_macro_corruption(value)
    if isinstance(value, list):
        return [deep_repair(item) for item in value]
    if isinstance(value, dict):
        return {key: deep_repair(item) for key, item in value.items()}
    return value


def normalize_dataset() -> dict[str, Any]:
    changed_files: dict[str, int] = {}
    question_count = 0

    for rel in DATA_FILES:
        path = ROOT / rel
        rows = read_jsonl(path)
        changed = 0
        for idx, row in enumerate(rows):
            before = json.dumps(row, ensure_ascii=False, sort_keys=True)
            row = deep_repair(row)
            if isinstance(row.get("stem_latex"), str):
                row["stem"] = clean_latex_safely(row["stem_latex"])
            options_latex = row.get("options_latex")
            if isinstance(options_latex, dict):
                row["options"] = {
                    key: clean_latex_safely(str(options_latex[key])) for key in "ABCD" if key in options_latex
                }
            nested_status = (row.get("verification") or {}).get("status")
            if nested_status:
                row["verification_status"] = nested_status
            qid = row.get("id")
            if qid in QUESTION_NOTES:
                row["verification_notes"] = QUESTION_NOTES[qid]
                methods = row.setdefault("verification", {}).setdefault("methods", [])
                for method in ("independent_mathematical_recomputation", "documented_source_disagreement_resolution"):
                    if method not in methods:
                        methods.append(method)
            rows[idx] = row
            after = json.dumps(row, ensure_ascii=False, sort_keys=True)
            if after != before:
                changed += 1
        write_jsonl(path, rows)
        question_count += len(rows)
        changed_files[rel] = changed

    for rel in ANALYSIS_FILES:
        path = ROOT / rel
        items = load_json(path)
        if not isinstance(items, list):
            raise RuntimeError(f"{rel} 顶层必须是数组")
        changed = 0
        for idx, item in enumerate(items):
            before = json.dumps(item, ensure_ascii=False, sort_keys=True)
            item = deep_repair(item)
            ref_latex = item.get("reference_solution_latex")
            if isinstance(ref_latex, str) and ref_latex.strip():
                cleaned = clean_latex_safely(ref_latex)
                item["reference_solution"] = cleaned
                if item.get("analysis_source") == "pinned_reference_solution":
                    item["analysis"] = cleaned
            items[idx] = item
            after = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if after != before:
                changed += 1
        dump_json(path, items)
        changed_files[rel] = changed

    return {"question_count": question_count, "changed_files": changed_files}


def canonical_answer(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value)
    return str(value)


def resolve_2025_report() -> dict[str, Any]:
    path = ROOT / "verification/2025-national-1.json"
    report = deep_repair(load_json(path))
    checks = {str(item.get("question_id")): item for item in report.get("question_checks", [])}

    for qid, resolution in RESOLUTIONS.items():
        check = checks.get(qid)
        if check is None:
            raise RuntimeError(f"校验报告缺少 {qid}")
        if canonical_answer(check.get("answer")) != canonical_answer(resolution["canonical_answer"]):
            raise RuntimeError(
                f"{qid} 当前答案 {check.get('answer')} 与裁决答案 {resolution['canonical_answer']} 不一致"
            )
        check["secondary_original_status"] = check.get("secondary_status")
        check["secondary_original_answer_excerpt"] = check.get("secondary_answer_excerpt")
        check["secondary_status"] = "disagreement_resolved"
        check["source_disagreement_resolution"] = {
            "decision": resolution["decision"],
            "canonical_answer": resolution["canonical_answer"],
            "secondary_answer": resolution["secondary_answer"],
            "reason": resolution["reason"],
            "support": resolution["support"],
            "resolved_at": TODAY,
        }

    unresolved = [
        item for item in report.get("question_checks", []) if item.get("secondary_status") == "mismatch"
    ]
    if unresolved:
        raise RuntimeError(f"仍有未解决的 2025 二来源冲突：{unresolved}")

    report["status"] = "verified"
    report["verified_at"] = TODAY
    source_pdf = report.get("source_pdf")
    if isinstance(source_pdf, dict):
        # The old value was a byte-pattern hint, not a reliable PDF page count.
        source_pdf.pop("page_count_hint", None)
        source_pdf["file_identity_verified"] = bool(
            source_pdf.get("git_blob_verified") and source_pdf.get("pdf_magic_verified")
        )
    summary = report.setdefault("summary", {})
    summary["secondary_mismatch_count"] = 0
    summary["secondary_disagreement_count"] = len(RESOLUTIONS)
    summary["resolved_secondary_disagreement_count"] = len(RESOLUTIONS)
    summary["unresolved_secondary_disagreement_count"] = 0
    report["resolved_source_disagreements"] = list(RESOLUTIONS.values())
    dump_json(path, report)
    return report


def normalize_other_reports() -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for rel in REPORT_FILES:
        path = ROOT / rel
        report = deep_repair(load_json(path))
        source_pdf = report.get("source_pdf")
        if isinstance(source_pdf, dict):
            source_pdf.pop("page_count_hint", None)
            source_pdf["file_identity_verified"] = bool(
                source_pdf.get("git_blob_verified") and source_pdf.get("pdf_magic_verified")
            )
        if rel != "verification/2025-national-1.json":
            if report.get("hard_errors"):
                raise RuntimeError(f"{rel} 仍有硬错误：{report['hard_errors']}")
            report["status"] = "verified"
            report["verified_at"] = TODAY
            dump_json(path, report)
        reports.append(report)
    return reports


def update_metadata(reports: list[dict[str, Any]]) -> None:
    path = ROOT / "metadata/papers.json"
    items = load_json(path)
    if not isinstance(items, list):
        raise RuntimeError("metadata/papers.json 顶层必须是数组")
    by_key = {(int(r["year"]), str(r["paper"])): r for r in reports}
    for item in items:
        key = (int(item.get("year", 0)), str(item.get("paper", "")))
        report = by_key.get(key)
        if report is None:
            continue
        item["verification_status"] = report["status"]
        item["verified_at"] = TODAY
        item["unresolved_secondary_disagreement_count"] = report.get("summary", {}).get(
            "unresolved_secondary_disagreement_count", report.get("summary", {}).get("secondary_mismatch_count", 0)
        )
        item["resolved_secondary_disagreement_count"] = report.get("summary", {}).get(
            "resolved_secondary_disagreement_count", 0
        )
    dump_json(path, items)


def update_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    path = ROOT / "verification/summary.json"
    summary = load_json(path)
    report_by_year = {int(report["year"]): report for report in reports}
    for paper in summary.get("papers", []):
        report = report_by_year[int(paper["year"])]
        paper["status"] = report["status"]
        paper["secondary_mismatch_count"] = report.get("summary", {}).get(
            "unresolved_secondary_disagreement_count", report.get("summary", {}).get("secondary_mismatch_count", 0)
        )
        paper["resolved_secondary_disagreement_count"] = report.get("summary", {}).get(
            "resolved_secondary_disagreement_count", 0
        )
    summary["verified_at"] = TODAY
    summary["status"] = "verified" if all(r.get("status") == "verified" for r in reports) else "needs_review"
    summary["unresolved_secondary_disagreement_count"] = sum(
        int(r.get("summary", {}).get("unresolved_secondary_disagreement_count", r.get("summary", {}).get("secondary_mismatch_count", 0)))
        for r in reports
    )
    summary["resolved_secondary_disagreement_count"] = sum(
        int(r.get("summary", {}).get("resolved_secondary_disagreement_count", 0)) for r in reports
    )
    dump_json(path, summary)
    return summary


def update_readme(summary: dict[str, Any]) -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"\| 2025 \| 全国1卷 \| 19 \| (?:needs_review|verified) \| 2 \|",
        "| 2025 | 全国1卷 | 19 | verified | 2 |",
        text,
    )
    marker = "详细记录见 `VERIFICATION_REPORT.md` 和 `verification/`。"
    addition = (
        "详细记录见 `VERIFICATION_REPORT.md` 和 `verification/`。\n\n"
        "2025 年第 4、9、13 题曾与单一第三方题库发生答案分歧，现已依据原卷、固定参考转写、"
        "其他独立答案源及数学推导完成裁决；原冲突保留在 `verification/secondary-source-resolutions.json`。"
    )
    if "secondary-source-resolutions.json" not in text:
        text = text.replace(marker, addition)
    path.write_text(text, encoding="utf-8")


def write_resolution_log() -> None:
    payload = {
        "resolved_at": TODAY,
        "status": "all_resolved",
        "policy": (
            "单一 C 级来源与 A 级原卷/固定转写冲突时，必须增加至少一份独立来源并进行 D 级数学复核；"
            "证据链一致后方可标记 resolved。"
        ),
        "resolutions": [
            {"question_id": qid, **resolution} for qid, resolution in RESOLUTIONS.items()
        ],
    }
    dump_json(ROOT / "verification/secondary-source-resolutions.json", payload)


def write_markdown_report(reports: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    rows: list[str] = []
    for report in sorted(reports, key=lambda item: int(item["year"])):
        report_summary = report.get("summary", {})
        unresolved = int(
            report_summary.get(
                "unresolved_secondary_disagreement_count", report_summary.get("secondary_mismatch_count", 0)
            )
        )
        resolved = int(report_summary.get("resolved_secondary_disagreement_count", 0))
        rows.append(
            f"| {report['year']} | {report['paper']} | {report['question_count']} | {report['status']} | "
            f"{unresolved} | {resolved} | {report.get('figure_dependency_count', 0)} |"
        )

    resolution_lines = []
    for qid, item in RESOLUTIONS.items():
        resolution_lines.append(
            f"- `{qid}`：第三方答案 `{item['secondary_answer']}`，裁决为 `{canonical_answer(item['canonical_answer'])}`。"
            f"{item['reason']}"
        )

    text = "\n".join(
        [
            "# 2021—2026 浙江适用高考数学数据校验报告",
            "",
            f"校验日期：{TODAY}",
            "",
            f"范围：{summary['paper_count']} 套试卷，共 {summary['question_count']} 道题；最终状态：`{summary['status']}`。",
            "",
            "## 校验链路",
            "",
            "1. 下载 `deekur/gaokaomath` 原始 PDF，并按 Git blob SHA 核对文件身份；",
            "2. 使用固定提交的 `DxAThing/Gaokao-Math-Problems-Compilation` 恢复完整题面、四选项、答案与参考解析；",
            "3. 2021—2025 使用高考真题 Wiki 逐题页面做第二来源检查，2026 使用固定提交的独立结构化数据集；",
            "4. 对冲突题增加其他公开答案集并独立数学推导，不以单一第三方题库作为裁判；",
            "5. 检查 JSON/JSONL、题数、连续题号、唯一 ID、题型、四选项、答案、图形依赖和解析映射。",
            "",
            "## 分卷结果",
            "",
            "| 年份 | 卷型 | 题数 | 状态 | 未解决分歧 | 已裁决分歧 | 含图题 |",
            "|---:|---|---:|---|---:|---:|---:|",
            *rows,
            "",
            "## 已裁决的第三方分歧",
            "",
            *resolution_lines,
            "",
            "原第三方答案、裁决依据和证据链完整保存在 `verification/secondary-source-resolutions.json`，没有静默删除。",
            "",
            "## 结论边界",
            "",
            "`verified` 表示在本仓库定义的多源、可追溯、可复现校验链路下未发现未解决冲突；"
            "它不等同于教育考试主管部门的官方认证。含图题保留题图引用，脱离图形资源不能完整作答。",
            "",
        ]
    )
    (ROOT / "VERIFICATION_REPORT.md").write_text(text, encoding="utf-8")


def validate_final_state(summary: dict[str, Any]) -> None:
    expected_counts = [22, 22, 22, 19, 19, 19]
    total = 0
    all_ids: set[str] = set()
    bad_markers = (r"\mathrm{i}n", r"\mathrm{i}nt", r"\mathrm{i}nfty", r"\mathbb{R}ightarrow")

    for rel, expected in zip(DATA_FILES, expected_counts, strict=True):
        path = ROOT / rel
        rows = read_jsonl(path)
        if len(rows) != expected:
            raise RuntimeError(f"{rel}: 题数 {len(rows)} != {expected}")
        if [row.get("question_no") for row in rows] != list(range(1, expected + 1)):
            raise RuntimeError(f"{rel}: 题号不连续")
        for row in rows:
            qid = str(row.get("id"))
            if not qid or qid in all_ids:
                raise RuntimeError(f"{rel}: ID 缺失或重复 {qid}")
            all_ids.add(qid)
            if row.get("question_type") in {"single_choice", "multiple_choice"}:
                if set((row.get("options") or {}).keys()) != set("ABCD"):
                    raise RuntimeError(f"{qid}: 四选项不完整")
            if (row.get("verification") or {}).get("status") not in {
                "verified", "verified_with_figure_dependency"
            }:
                raise RuntimeError(f"{qid}: 单题校验状态未收口")
        content = path.read_text(encoding="utf-8")
        for marker in bad_markers:
            if marker in content:
                raise RuntimeError(f"{rel}: 仍含旧版 LaTeX 命令破坏标记 {marker}")
        total += len(rows)

    if total != 123 or len(all_ids) != 123:
        raise RuntimeError(f"总题数异常：{total}/{len(all_ids)}")
    if summary.get("status") != "verified":
        raise RuntimeError(f"总校验状态未收口：{summary.get('status')}")
    if int(summary.get("unresolved_secondary_disagreement_count", -1)) != 0:
        raise RuntimeError("仍有未解决的二来源分歧")


def main() -> None:
    normalization = normalize_dataset()
    resolved_2025 = resolve_2025_report()
    reports = normalize_other_reports()
    # Replace the in-memory 2025 copy with the adjudicated version.
    reports = [resolved_2025 if int(report["year"]) == 2025 else report for report in reports]
    update_metadata(reports)
    summary = update_summary(reports)
    write_resolution_log()
    update_readme(summary)
    write_markdown_report(reports, summary)
    dump_json(
        ROOT / "verification/normalization-report.json",
        {"normalized_at": TODAY, **normalization},
    )
    validate_final_state(summary)
    print(
        f"最终校验通过：{summary['paper_count']} 套、{summary['question_count']} 道题；"
        f"已裁决 {summary['resolved_secondary_disagreement_count']} 个第三方分歧，未解决 0 个。"
    )


if __name__ == "__main__":
    main()
