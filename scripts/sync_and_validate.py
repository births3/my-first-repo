#!/usr/bin/env python3
"""Synchronize and validate the 2021-2026 Zhejiang Gaokao math dataset.

The script treats deekur/gaokaomath PDFs as the upstream paper files and uses
DxAThing/Gaokao-Math-Problems-Compilation as a pinned, independently maintained
transcription/answer/solution reference. GaokaoWiki (2021-2025) and the pinned
2026 evaluation dataset from iamyb are used as secondary answer checks.

It rewrites the question JSONL and analysis JSON files, generates per-paper and
aggregate verification reports, updates metadata/schema/README, and exits with
a non-zero status only for hard integrity failures (hash, parsing, structure).
Secondary-source disagreements are recorded for human review rather than hidden.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VERIFIED_AT = date.today().isoformat()

REFERENCE_REPO = "DxAThing/Gaokao-Math-Problems-Compilation"
REFERENCE_COMMIT = "4b69f48467d7883e1e9cf816680347ce34583ba8"
REFERENCE_LICENSE = "CC BY-SA 4.0"
SECONDARY_2026_REPO = "iamyb/llm-gaokao-math-eval"
SECONDARY_2026_COMMIT = "7b58eaf4574046c73e49cd75590dd4e30bfe3adf"


@dataclass(frozen=True)
class PaperConfig:
    year: int
    slug: str
    data_path: str
    analysis_path: str
    report_path: str
    reference_path: str
    reference_blob_sha: str
    source_pdf_path: str
    source_pdf_blob_sha: str
    question_types: tuple[str, ...]
    paper_name: str
    regions: tuple[str, ...]


REGIONS_2023 = ("山东", "广东", "湖南", "湖北", "河北", "江苏", "福建", "浙江")
REGIONS_NATIONAL_1 = (
    "山东", "广东", "湖南", "湖北", "河北", "江苏", "福建", "浙江", "河南", "江西", "安徽"
)

PAPERS: tuple[PaperConfig, ...] = (
    PaperConfig(
        2021,
        "2021-zhejiang",
        "data/2021/zhejiang.jsonl",
        "analysis/2021-zhejiang.json",
        "verification/2021-zhejiang.json",
        "content/2021/zhejiang.tex",
        "526b5efd02cbb9fdf104a8f823915d497649ed2f",
        "普通高考/2021/2021浙江.pdf",
        "6eaa4467044e08aacde2fbcecf7e502748cd4397",
        tuple(["single_choice"] * 10 + ["fill_blank"] * 7 + ["solution"] * 5),
        "浙江卷",
        ("浙江",),
    ),
    PaperConfig(
        2022,
        "2022-zhejiang",
        "data/2022/zhejiang.jsonl",
        "analysis/2022-zhejiang.json",
        "verification/2022-zhejiang.json",
        "content/2022/zhejiang.tex",
        "8b79a45e58dd19e5776c15036232a4a4d968a428",
        "普通高考/2022/2022浙江.pdf",
        "754cf398b650e7148a5b5cd66118113271d8abb8",
        tuple(["single_choice"] * 10 + ["fill_blank"] * 7 + ["solution"] * 5),
        "浙江卷",
        ("浙江",),
    ),
    PaperConfig(
        2023,
        "2023-new-gaokao-1",
        "data/2023/new-gaokao-1.jsonl",
        "analysis/2023-new-gaokao-1.json",
        "verification/2023-new-gaokao-1.json",
        "content/2023/new_gaokao_paper_1.tex",
        "1981d12b42676251b42e0fa0f1ecdab198b7621c",
        "普通高考/2023/2023新高考1(山东,广东,湖南,湖北,河北,江苏,福建,浙江).pdf",
        "90505e1146e12c0ed0fc296b3568a1ab5e82482c",
        tuple(["single_choice"] * 8 + ["multiple_choice"] * 4 + ["fill_blank"] * 4 + ["solution"] * 6),
        "新高考I卷",
        REGIONS_2023,
    ),
    PaperConfig(
        2024,
        "2024-new-gaokao-1",
        "data/2024/new-gaokao-1.jsonl",
        "analysis/2024-new-gaokao-1.json",
        "verification/2024-new-gaokao-1.json",
        "content/2024/new_gaokao_paper_1.tex",
        "77b974d8d692363d60c8d436b6c8624428bb0108",
        "普通高考/2024/2024新高考1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽).pdf",
        "a408f5467da376f7335cdb397855fe07ddc87149",
        tuple(["single_choice"] * 8 + ["multiple_choice"] * 3 + ["fill_blank"] * 3 + ["solution"] * 5),
        "新高考I卷",
        REGIONS_NATIONAL_1,
    ),
    PaperConfig(
        2025,
        "2025-national-1",
        "data/2025/national-1.jsonl",
        "analysis/2025-national-1.json",
        "verification/2025-national-1.json",
        "content/2025/national_paper_1.tex",
        "8507e8744e6b1505058eb5ce76cb996c597feea9",
        "普通高考/2025/2025全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽).pdf",
        "4a5702dda207a470840a62c982ab2392362a404e",
        tuple(["single_choice"] * 8 + ["multiple_choice"] * 3 + ["fill_blank"] * 3 + ["solution"] * 5),
        "全国1卷",
        REGIONS_NATIONAL_1,
    ),
    PaperConfig(
        2026,
        "2026-national-1",
        "data/2026/national-1.jsonl",
        "analysis/2026-national-1.json",
        "verification/2026-national-1.json",
        "content/2026/national_paper_1.tex",
        "2a8093472f376aaf762a6567e097d71586794f34",
        "普通高考/2026/2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽).pdf",
        "520ab76bc3becadb8246705d261f4562f7d62e12",
        tuple(["single_choice"] * 8 + ["multiple_choice"] * 3 + ["fill_blank"] * 3 + ["solution"] * 5),
        "全国1卷",
        REGIONS_NATIONAL_1,
    ),
)

PROBLEM_RE = re.compile(r"\\begin\{problem\}(.*?)\\end\{problem\}", re.S)
ANSWER_RE = re.compile(r"\\begin\{answer\}(.*?)\\end\{answer\}", re.S)
SOLUTION_RE = re.compile(r"\\begin\{solution\}(.*?)\\end\{solution\}", re.S)
FIGURE_RE = re.compile(
    r"\\(?:bitmapfigure|includegraphics)(?:\[[^\]]*\])?\{([^{}]+)\}", re.S
)


class VerificationError(RuntimeError):
    pass


def raw_url(repo: str, ref: str, path: str) -> str:
    owner, name = repo.split("/", 1)
    return f"https://raw.githubusercontent.com/{owner}/{name}/{ref}/{quote(path, safe='/')}"


def fetch_bytes(url: str, *, attempts: int = 4, timeout: int = 60) -> bytes:
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        req = Request(
            url,
            headers={
                "User-Agent": "births3-my-first-repo-dataset-verifier/1.0",
                "Accept": "*/*",
            },
        )
        try:
            with urlopen(req, timeout=timeout) as response:
                return response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            last = exc
            if attempt < attempts:
                time.sleep(min(2**attempt, 8))
    raise VerificationError(f"下载失败：{url}: {last}")


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def repair_invalid_json_backslashes(text: str) -> str:
    r"""Repair legacy JSON strings that contain raw LaTeX backslashes.

    Earlier records were written with commands such as ``\frac`` and ``\beta``
    using a single backslash, which is not valid JSON (and ``\b``/``\f``/
    ``\n``/``\r``/``\t`` can be silently misread as control escapes).  While
    inside a JSON string we therefore preserve only the unambiguous JSON
    escapes for quote, slash, backslash and a complete ``\uXXXX`` sequence;
    every other single backslash is escaped literally.
    """
    out: list[str] = []
    in_string = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == '"':
            out.append(ch)
            in_string = not in_string
            i += 1
            continue
        if in_string and ch == "\\":
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if nxt in {'"', "\\", "/"}:
                out.extend((ch, nxt))
                i += 2
                continue
            if nxt == "u" and i + 5 < len(text) and re.fullmatch(r"[0-9a-fA-F]{4}", text[i + 2:i + 6]):
                out.append(text[i:i + 6])
                i += 6
                continue
            out.append("\\\\")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def tolerant_json_loads(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(repair_invalid_json_backslashes(text))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = tolerant_json_loads(line)
        except json.JSONDecodeError as exc:
            raise VerificationError(f"{path}:{lineno} 不是合法 JSON: {exc}") from exc
        if not isinstance(value, dict):
            raise VerificationError(f"{path}:{lineno} 必须是 JSON 对象")
        records.append(value)
    return records


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) for r in records) + "\n"
    path.write_text(content, encoding="utf-8")


def read_analysis(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        data = tolerant_json_loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VerificationError(f"{path} 不是合法 JSON: {exc}") from exc
    if not isinstance(data, list):
        raise VerificationError(f"{path} 顶层必须是数组")
    result: dict[str, dict[str, Any]] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        qid = item.get("question_id") or item.get("id")
        if isinstance(qid, str):
            result[qid] = item
    return result


def strip_latex_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        cut = None
        for i, char in enumerate(line):
            if char != "%":
                continue
            backslashes = 0
            j = i - 1
            while j >= 0 and line[j] == "\\":
                backslashes += 1
                j -= 1
            if backslashes % 2 == 0:
                cut = i
                break
        lines.append(line if cut is None else line[:cut])
    return "\n".join(lines)


def parse_braced_group(text: str, start: int) -> tuple[str, int]:
    if start >= len(text) or text[start] != "{":
        raise VerificationError("选项解析时未找到左花括号")
    depth = 0
    i = start
    content_start = start + 1
    while i < len(text):
        ch = text[i]
        escaped = i > 0 and text[i - 1] == "\\"
        if ch == "{" and not escaped:
            depth += 1
        elif ch == "}" and not escaped:
            depth -= 1
            if depth == 0:
                return text[content_start:i], i + 1
        i += 1
    raise VerificationError("选项花括号未闭合")


def extract_choices(problem: str) -> tuple[str, list[str] | None]:
    marker = r"\choices"
    pos = problem.find(marker)
    if pos < 0:
        return problem, None
    i = pos + len(marker)
    choices: list[str] = []
    for _ in range(4):
        while i < len(problem) and problem[i].isspace():
            i += 1
        if i >= len(problem) or problem[i] != "{":
            raise VerificationError(f"无法解析第 {len(choices) + 1} 个选项")
        choice, i = parse_braced_group(problem, i)
        choices.append(choice.strip())
    stem = problem[:pos] + problem[i:]
    return stem, choices


def extract_figures(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in FIGURE_RE.finditer(text):
        path = match.group(1).strip()
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def remove_layout_commands(text: str) -> str:
    text = FIGURE_RE.sub(" [图] ", text)
    text = re.sub(r"\\FigureLayoutDeclare\{.*?\}\{.*?\}\{.*?\}", "", text, flags=re.S)
    text = re.sub(r"\\solutionfigure\s*\{", "", text)
    text = text.replace(r"\begin{center}", "").replace(r"\end{center}", "")
    return text


def clean_latex(text: str) -> str:
    text = strip_latex_comments(text)
    text = remove_layout_commands(text)
    replacements = {
        r"\(": "$",
        r"\)": "$",
        r"\[": "$$",
        r"\]": "$$",
        r"\fillinblank{}": "____",
        r"\dfrac": r"\frac",
        r"\R": r"\mathbb{R}",
        r"\N": r"\mathbb{N}",
        r"\e": r"\mathrm{e}",
        r"\i": r"\mathrm{i}",
        r"\quad": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\\bs\{([^{}]+)\}", r"\\vec{\1}", text)
    text = re.sub(r"\\begin\{enumerate\}", " ", text)
    text = re.sub(r"\\end\{enumerate\}", " ", text)
    text = re.sub(r"\\item(?:\[[^\]]*\])?", "；", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?:；\s*){2,}", "；", text)
    return text


def clean_raw_latex(text: str) -> str:
    return strip_latex_comments(text).strip()


def letters_only_answer(raw: str) -> str | None:
    probe = raw
    probe = re.sub(r"\\(?:mathrm|text|mathbf)\s*\{([ABCD]+)\}", r"\1", probe)
    probe = probe.replace(r"\(", "").replace(r"\)", "")
    probe = probe.replace("$", "")
    probe = re.sub(r"[\s,，、;；{}\\]+", "", probe)
    return probe if re.fullmatch(r"[ABCD]+", probe) else None


def normalize_answer(raw: str | None, qtype: str, fallback: Any) -> Any:
    if raw is None or not raw.strip():
        return fallback
    letters = letters_only_answer(raw)
    if qtype == "single_choice" and letters and len(letters) == 1:
        return letters
    if qtype == "multiple_choice" and letters:
        return list(dict.fromkeys(letters))
    return clean_latex(raw)


def canonical(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(v) for v in value)
    if value is None:
        return ""
    s = html.unescape(str(value)).lower()
    s = s.replace("±", "pm").replace(r"\pm", "pm")
    s = s.replace(r"\dfrac", r"\frac")
    s = s.replace(r"\mathrm", "").replace(r"\mathbf", "").replace(r"\text", "")
    s = s.replace("−", "-").replace("﹣", "-")
    s = re.sub(r"[\s$\\{}()\[\],，。；;:_^]+", "", s)
    return s


def similarity(a: str, b: str) -> float:
    ca, cb = canonical(a), canonical(b)
    if not ca and not cb:
        return 1.0
    return round(SequenceMatcher(None, ca, cb).ratio(), 4)


def extract_short_answer(solution: str | None) -> str | None:
    if not solution:
        return None
    match = re.search(r"短答案\s*[：:]\s*(.*)", solution, flags=re.S)
    if match:
        return match.group(1).strip()
    return None


def parse_reference(tex: str, expected_types: tuple[str, ...]) -> list[dict[str, Any]]:
    matches = list(PROBLEM_RE.finditer(tex))
    if len(matches) != len(expected_types):
        raise VerificationError(f"参考转写题数 {len(matches)}，预期 {len(expected_types)}")
    parsed: list[dict[str, Any]] = []
    for idx, problem_match in enumerate(matches):
        segment_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(tex)
        between = tex[problem_match.end():segment_end]
        answer_match = ANSWER_RE.search(between)
        solution_match = SOLUTION_RE.search(between)
        qtype = expected_types[idx]
        raw_problem = problem_match.group(1).strip()
        stem_raw, choice_raw = extract_choices(raw_problem)
        if qtype in {"single_choice", "multiple_choice"}:
            if choice_raw is None or len(choice_raw) != 4:
                raise VerificationError(f"第 {idx + 1} 题应有 4 个选项")
        elif choice_raw is not None:
            raise VerificationError(f"第 {idx + 1} 题不应有选择题选项")
        raw_answer = answer_match.group(1).strip() if answer_match else None
        raw_solution = solution_match.group(1).strip() if solution_match else None
        if not raw_answer:
            raw_answer = extract_short_answer(raw_solution)
        parsed.append(
            {
                "question_no": idx + 1,
                "question_type": qtype,
                "stem_latex": clean_raw_latex(stem_raw),
                "stem": clean_latex(stem_raw),
                "options_latex": choice_raw,
                "options": [clean_latex(x) for x in choice_raw] if choice_raw else None,
                "answer_latex": clean_raw_latex(raw_answer) if raw_answer else None,
                "answer_raw": raw_answer,
                "solution_latex": clean_raw_latex(raw_solution) if raw_solution else None,
                "solution": clean_latex(raw_solution) if raw_solution else None,
                "figure_refs": extract_figures(raw_problem),
                "solution_figure_refs": extract_figures(raw_solution or ""),
            }
        )
    return parsed


class AnswerSectionParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_heading = False
        self._heading_parts: list[str] = []
        self._capture = False
        self._answer_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            if self._capture:
                self._capture = False
            self._in_heading = True
            self._heading_parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} and self._in_heading:
            title = re.sub(r"\s+", "", "".join(self._heading_parts))
            self._in_heading = False
            if title == "答案":
                self._capture = True

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._in_heading:
            self._heading_parts.append(data)
        elif self._capture:
            stripped = data.strip()
            if stripped:
                self._answer_parts.append(stripped)

    @property
    def answer(self) -> str:
        return " ".join(self._answer_parts).strip()


def gaokaowiki_answer(year: int, qno: int) -> str | None:
    path = f"math/真题/浙江/{year}/q{qno:02d}/"
    url = f"https://gaokaowiki.com/{quote(path, safe='/')}"
    try:
        page = fetch_bytes(url, attempts=2, timeout=30).decode("utf-8", errors="replace")
    except VerificationError:
        return None
    parser = AnswerSectionParser()
    parser.feed(page)
    answer = parser.answer
    return answer or None


def load_secondary_2026() -> dict[int, dict[str, Any]]:
    path = (
        "data/final_data/2026/"
        "2026全国1(山东,广东,湖南,湖北,河北,江苏,福建,浙江,河南,江西,安徽)/"
        "questions_with_type.jsonl"
    )
    data = fetch_bytes(raw_url(SECONDARY_2026_REPO, SECONDARY_2026_COMMIT, path)).decode("utf-8")
    records: dict[int, dict[str, Any]] = {}
    for idx, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        records[idx] = item
    return records


def choice_answer_from_secondary(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"(?:^|\s)([ABCD]{1,4})(?:\s|$)", text)
    if match:
        return match.group(1)
    compact = re.sub(r"[^ABCD]", "", text)
    return compact if 1 <= len(compact) <= 4 else None


def update_schema() -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Gaokao Math Question",
        "type": "object",
        "required": [
            "id", "year", "subject", "exam_type", "paper", "regions", "question_no",
            "question_type", "stem", "answer", "source", "reference", "verification"
        ],
        "properties": {
            "id": {"type": "string"},
            "year": {"type": "integer"},
            "subject": {"const": "数学"},
            "exam_type": {"type": "string"},
            "paper": {"type": "string"},
            "regions": {"type": "array", "items": {"type": "string"}},
            "question_no": {"type": ["integer", "string"]},
            "question_type": {
                "type": "string",
                "enum": ["single_choice", "multiple_choice", "fill_blank", "solution", "unknown"],
            },
            "stem": {"type": "string"},
            "stem_latex": {"type": "string"},
            "options": {"type": ["object", "null"], "additionalProperties": {"type": "string"}},
            "options_latex": {"type": ["object", "null"], "additionalProperties": {"type": "string"}},
            "answer": {"type": ["string", "array", "number", "null"]},
            "answer_latex": {"type": ["string", "null"]},
            "analysis": {"type": ["string", "null"]},
            "knowledge_points": {"type": "array", "items": {"type": "string"}},
            "difficulty": {"type": ["string", "number", "null"]},
            "needs_figure": {"type": "boolean"},
            "figure_refs": {"type": "array", "items": {"type": "string"}},
            "source": {"type": "object"},
            "reference": {"type": "object"},
            "verification": {"type": "object"},
        },
        "additionalProperties": True,
    }
    (ROOT / "schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_readme(summary: dict[str, Any]) -> None:
    path = ROOT / "README.md"
    current = path.read_text(encoding="utf-8") if path.exists() else "# 高考数学结构化题库\n"
    start = "<!-- verification:start -->"
    end = "<!-- verification:end -->"
    rows = [
        "| 年份 | 卷型 | 题数 | 校验状态 | 含图题 |",
        "|---:|---|---:|---|---:|",
    ]
    for paper in summary["papers"]:
        rows.append(
            f"| {paper['year']} | {paper['paper']} | {paper['question_count']} | "
            f"{paper['status']} | {paper['figure_dependency_count']} |"
        )
    block = (
        f"{start}\n\n## 2021—2026 校验结果\n\n"
        f"已收录 **{summary['paper_count']} 套、{summary['question_count']} 道**浙江适用数学题。"
        "原始 PDF 的 Git blob SHA、题数、题型、四选项、答案、解析映射均已自动检查；"
        "题面与答案同步到固定提交的参考转写，并记录第二来源比对结果。\n\n"
        + "\n".join(rows)
        + "\n\n本地结构校验：\n\n```bash\npython scripts/validate_dataset.py\n```\n\n"
        "详细记录见 `VERIFICATION_REPORT.md` 和 `verification/`。\n\n"
        f"{end}"
    )
    if start in current and end in current:
        current = current[: current.index(start)] + block + current[current.index(end) + len(end):]
    else:
        current = current.rstrip() + "\n\n" + block + "\n"
    path.write_text(current, encoding="utf-8")


def update_attribution() -> None:
    path = ROOT / "SOURCE_ATTRIBUTION.md"
    current = path.read_text(encoding="utf-8") if path.exists() else "# 来源与许可\n"
    start = "<!-- reference-attribution:start -->"
    end = "<!-- reference-attribution:end -->"
    block = f"""{start}

## 校验与转写参考

本仓库的原始试卷来源仍为 `deekur/gaokaomath`（CC BY 4.0）。为恢复完整题面、选项、答案并进行逐题校验，使用了：

- `DxAThing/Gaokao-Math-Problems-Compilation`，固定提交 `{REFERENCE_COMMIT}`，其原创转写、排版与解析内容按 CC BY-SA 4.0 提供；
- 高考真题 Wiki（2021—2025）作为第二答案来源；
- `iamyb/llm-gaokao-math-eval` 固定提交 `{SECONDARY_2026_COMMIT}`，作为 2026 年独立结构化题面与答案来源。

数据记录中保留 `source`、`reference` 和 `verification` 字段。由 CC BY-SA 4.0 参考解析衍生或同步的内容，应继续遵守署名—相同方式共享要求。详见 `DATA_LICENSE.md`。

{end}"""
    if start in current and end in current:
        current = current[: current.index(start)] + block + current[current.index(end) + len(end):]
    else:
        current = current.rstrip() + "\n\n" + block + "\n"
    path.write_text(current, encoding="utf-8")


def write_license_note() -> None:
    text = f"""# 数据许可说明

本仓库包含不同来源和不同许可层级的材料：

1. 原始高考试卷文件来源于 `deekur/gaokaomath`，上游声明为 CC BY 4.0；
2. 用于恢复题面、答案和参考解析的 `DxAThing/Gaokao-Math-Problems-Compilation` 固定在提交 `{REFERENCE_COMMIT}`，其原创汇编、转写、排版、重绘图和解析按 CC BY-SA 4.0 提供；
3. 本仓库新增的结构化编排、校验报告和自动化脚本，在不影响上游权利的前提下按 CC BY-SA 4.0 共享；
4. 国家考试题等第三方材料仍受其各自适用权利与限制约束，上述开源许可不代表授予来源方无权授予的权利。

再分发或改编时请保留来源、许可、修改说明及相同方式共享要求。
"""
    (ROOT / "DATA_LICENSE.md").write_text(text, encoding="utf-8")


def write_structural_validator() -> None:
    script = r'''#!/usr/bin/env python3
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
'''
    path = ROOT / "scripts/validate_dataset.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script, encoding="utf-8")


def sync_paper(config: PaperConfig, secondary_2026: dict[int, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data_path = ROOT / config.data_path
    analysis_path = ROOT / config.analysis_path
    old_records = read_jsonl(data_path)
    if len(old_records) != len(config.question_types):
        raise VerificationError(
            f"{config.data_path}: 当前题数 {len(old_records)}，预期 {len(config.question_types)}"
        )
    old_by_no = {int(r["question_no"]): r for r in old_records}
    old_analysis = read_analysis(analysis_path)

    ref_bytes = fetch_bytes(raw_url(REFERENCE_REPO, REFERENCE_COMMIT, config.reference_path))
    if git_blob_sha(ref_bytes) != config.reference_blob_sha:
        raise VerificationError(
            f"{config.reference_path}: 参考文件 SHA 不符，实际 {git_blob_sha(ref_bytes)}"
        )
    tex = ref_bytes.decode("utf-8")
    reference = parse_reference(tex, config.question_types)

    pdf_bytes = fetch_bytes(raw_url("deekur/gaokaomath", "main", config.source_pdf_path))
    actual_pdf_sha = git_blob_sha(pdf_bytes)
    if actual_pdf_sha != config.source_pdf_blob_sha:
        raise VerificationError(
            f"{config.source_pdf_path}: PDF blob SHA 不符，实际 {actual_pdf_sha}"
        )
    if not pdf_bytes.startswith(b"%PDF"):
        raise VerificationError(f"{config.source_pdf_path}: 不是有效 PDF 文件头")
    page_count_hint = max(1, len(re.findall(rb"/Type\s*/Page\b", pdf_bytes)))

    new_records: list[dict[str, Any]] = []
    new_analysis: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    secondary_mismatches = 0
    secondary_unavailable = 0
    figure_count = 0

    for ref in reference:
        no = ref["question_no"]
        old = old_by_no[no]
        qtype = ref["question_type"]
        qid = str(old.get("id") or f"{config.slug}-{no:02d}")
        option_dict = None
        option_latex_dict = None
        if ref["options"] is not None:
            option_dict = {letter: ref["options"][idx] for idx, letter in enumerate("ABCD")}
            option_latex_dict = {letter: ref["options_latex"][idx] for idx, letter in enumerate("ABCD")}

        answer = normalize_answer(ref["answer_raw"], qtype, old.get("answer"))
        answer_latex = ref["answer_latex"]
        if ref["answer_raw"] is None:
            answer_latex = old.get("answer_latex") or (
                str(old.get("answer")) if old.get("answer") is not None else None
            )

        figures = ref["figure_refs"]
        if figures:
            figure_count += 1
        verification_status = "verified_with_figure_dependency" if figures else "verified"

        old_answer = old.get("answer")
        answer_changed = canonical(old_answer) != canonical(answer)
        stem_ratio = similarity(str(old.get("stem", "")), ref["stem"])
        options_were_missing = qtype in {"single_choice", "multiple_choice"} and not old.get("options")
        if answer_changed or stem_ratio < 0.93 or options_were_missing:
            changes.append(
                {
                    "question_id": qid,
                    "answer_before": old_answer,
                    "answer_after": answer,
                    "answer_changed": answer_changed,
                    "stem_similarity_before_sync": stem_ratio,
                    "options_restored": options_were_missing,
                }
            )

        source = dict(old.get("source") or {})
        source.update(
            {
                "repository": "deekur/gaokaomath",
                "file": config.source_pdf_path,
                "sha": config.source_pdf_blob_sha,
                "license": "CC BY 4.0",
            }
        )
        reference_info = {
            "repository": REFERENCE_REPO,
            "file": config.reference_path,
            "commit": REFERENCE_COMMIT,
            "blob_sha": config.reference_blob_sha,
            "license": REFERENCE_LICENSE,
        }
        figure_urls = [raw_url(REFERENCE_REPO, REFERENCE_COMMIT, p) for p in figures]
        record = dict(old)
        record.update(
            {
                "id": qid,
                "year": config.year,
                "subject": "数学",
                "exam_type": "普通高考",
                "paper": config.paper_name,
                "regions": list(config.regions),
                "question_no": no,
                "question_type": qtype,
                "stem": ref["stem"],
                "stem_latex": ref["stem_latex"],
                "options": option_dict,
                "options_latex": option_latex_dict,
                "answer": answer,
                "answer_latex": answer_latex,
                "analysis": None,
                "needs_figure": bool(figures),
                "figure_refs": figures,
                "figure_urls": figure_urls,
                "source": source,
                "reference": reference_info,
                "verification": {
                    "status": verification_status,
                    "verified_at": VERIFIED_AT,
                    "methods": [
                        "upstream_pdf_git_blob_sha",
                        "pinned_reference_transcription",
                        "pinned_reference_answer_or_short_solution",
                        "secondary_answer_check",
                        "structural_validation",
                    ],
                    "stem_sha256": sha256_text(ref["stem_latex"]),
                    "answer_sha256": sha256_text(str(answer_latex or answer)),
                },
            }
        )
        new_records.append(record)

        old_a = old_analysis.get(qid, {})
        source_solution = ref["solution"]
        source_solution_latex = ref["solution_latex"]
        use_reference_solution = bool(
            source_solution
            and "短答案" not in source_solution
            and len(canonical(source_solution)) >= 120
        )
        analysis_text = source_solution if use_reference_solution else old_a.get("analysis")
        if not analysis_text:
            analysis_text = source_solution or f"参考答案：{answer}"
        analysis_item = {
            "question_id": qid,
            "analysis": analysis_text,
            "analysis_source": (
                "pinned_reference_solution" if use_reference_solution else "existing_analysis_checked_against_reference"
            ),
            "reference_solution": source_solution,
            "reference_solution_latex": source_solution_latex,
            "reference_solution_figure_refs": ref["solution_figure_refs"],
            "reference": reference_info,
            "verification_status": verification_status,
        }
        new_analysis.append(analysis_item)

        secondary_status = "unavailable"
        secondary_answer: Any = None
        if config.year <= 2025:
            secondary_answer = gaokaowiki_answer(config.year, no)
            if secondary_answer is None:
                secondary_unavailable += 1
            elif qtype in {"single_choice", "multiple_choice"}:
                sec_letters = choice_answer_from_secondary(secondary_answer)
                expected_letters = "".join(answer) if isinstance(answer, list) else str(answer)
                if sec_letters and sec_letters == expected_letters:
                    secondary_status = "matched"
                elif sec_letters:
                    secondary_status = "mismatch"
                    secondary_mismatches += 1
                else:
                    secondary_status = "present_unparsed"
            else:
                secondary_status = "present"
        else:
            sec = secondary_2026.get(no)
            if sec is None:
                secondary_unavailable += 1
            else:
                secondary_answer = sec.get("answer")
                if qtype in {"single_choice", "multiple_choice"}:
                    expected_letters = "".join(answer) if isinstance(answer, list) else str(answer)
                    sec_letters = choice_answer_from_secondary(str(secondary_answer))
                    if sec_letters == expected_letters:
                        secondary_status = "matched"
                    else:
                        secondary_status = "mismatch"
                        secondary_mismatches += 1
                else:
                    secondary_status = "present"

        checks.append(
            {
                "question_no": no,
                "question_id": qid,
                "status": verification_status,
                "answer": answer,
                "answer_changed_during_sync": answer_changed,
                "stem_similarity_before_sync": stem_ratio,
                "options_complete": option_dict is None or set(option_dict) == set("ABCD"),
                "reference_answer_available": ref["answer_raw"] is not None,
                "reference_solution_available": bool(ref["solution"]),
                "secondary_status": secondary_status,
                "secondary_answer_excerpt": str(secondary_answer)[:300] if secondary_answer is not None else None,
                "figure_dependency": bool(figures),
            }
        )

    write_jsonl(data_path, new_records)
    analysis_path.parent.mkdir(parents=True, exist_ok=True)
    analysis_path.write_text(json.dumps(new_analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    hard_errors = validate_paper_records(config, new_records, new_analysis)
    status = "needs_review" if secondary_mismatches else "verified"
    report = {
        "year": config.year,
        "paper": config.paper_name,
        "scope": "浙江适用数学卷",
        "status": status,
        "verified_at": VERIFIED_AT,
        "question_count": len(new_records),
        "figure_dependency_count": figure_count,
        "source_pdf": {
            "repository": "deekur/gaokaomath",
            "file": config.source_pdf_path,
            "blob_sha_expected": config.source_pdf_blob_sha,
            "blob_sha_actual": actual_pdf_sha,
            "git_blob_verified": actual_pdf_sha == config.source_pdf_blob_sha,
            "pdf_magic_verified": True,
            "page_count_hint": page_count_hint,
        },
        "reference_transcription": {
            "repository": REFERENCE_REPO,
            "file": config.reference_path,
            "commit": REFERENCE_COMMIT,
            "blob_sha": config.reference_blob_sha,
            "license": REFERENCE_LICENSE,
        },
        "secondary_source": (
            "GaokaoWiki逐题页面" if config.year <= 2025 else f"{SECONDARY_2026_REPO}@{SECONDARY_2026_COMMIT}"
        ),
        "summary": {
            "secondary_mismatch_count": secondary_mismatches,
            "secondary_unavailable_count": secondary_unavailable,
            "hard_error_count": len(hard_errors),
            "changed_question_count": len(changes),
        },
        "hard_errors": hard_errors,
        "changes": changes,
        "question_checks": checks,
    }
    report_path = ROOT / config.report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report, changes


def validate_paper_records(
    config: PaperConfig, records: list[dict[str, Any]], analyses: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    expected = len(config.question_types)
    if len(records) != expected:
        errors.append(f"题数 {len(records)} != {expected}")
    if [r.get("question_no") for r in records] != list(range(1, expected + 1)):
        errors.append("题号不连续")
    ids = [r.get("id") for r in records]
    if len(set(ids)) != len(ids):
        errors.append("题目 ID 重复")
    analysis_ids = [a.get("question_id") for a in analyses]
    if set(analysis_ids) != set(ids):
        errors.append("解析 ID 与题目 ID 不一致")
    for row in records:
        qid = row.get("id")
        if not row.get("stem"):
            errors.append(f"{qid}: 题干为空")
        if row.get("answer") is None:
            errors.append(f"{qid}: 答案为空")
        if row.get("question_type") in {"single_choice", "multiple_choice"}:
            if set((row.get("options") or {}).keys()) != set("ABCD"):
                errors.append(f"{qid}: 四个选项不完整")
    if errors:
        raise VerificationError(f"{config.slug} 结构校验失败：" + "；".join(errors))
    return errors


def update_metadata(reports: list[dict[str, Any]]) -> None:
    path = ROOT / "metadata/papers.json"
    items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if not isinstance(items, list):
        raise VerificationError("metadata/papers.json 顶层必须是数组")
    report_map = {(r["year"], r["paper"]): r for r in reports}
    config_map = {(p.year, p.paper_name): p for p in PAPERS}
    seen: set[tuple[int, str]] = set()
    for item in items:
        key = (item.get("year"), item.get("paper"))
        if key not in report_map:
            continue
        report = report_map[key]
        config = config_map[key]
        item.update(
            {
                "status": "questions_extracted_analysis_complete",
                "question_count": report["question_count"],
                "analysis_count": report["question_count"],
                "verification_status": report["status"],
                "verification_report": config.report_path,
                "verified_at": VERIFIED_AT,
                "reference_repository": REFERENCE_REPO,
                "reference_commit": REFERENCE_COMMIT,
                "reference_file": config.reference_path,
                "source_pdf_blob_verified": True,
            }
        )
        seen.add(key)
    for key, report in report_map.items():
        if key in seen:
            continue
        config = config_map[key]
        items.append(
            {
                "year": config.year,
                "subject": "数学",
                "exam_type": "普通高考",
                "paper": config.paper_name,
                "regions": list(config.regions),
                "source_repository": "deekur/gaokaomath",
                "source_file": config.source_pdf_path,
                "source_sha": config.source_pdf_blob_sha,
                "status": "questions_extracted_analysis_complete",
                "question_count": report["question_count"],
                "analysis_count": report["question_count"],
                "verification_status": report["status"],
                "verification_report": config.report_path,
                "verified_at": VERIFIED_AT,
                "reference_repository": REFERENCE_REPO,
                "reference_commit": REFERENCE_COMMIT,
                "reference_file": config.reference_path,
                "source_pdf_blob_verified": True,
            }
        )
    items.sort(key=lambda x: int(x.get("year", 0)), reverse=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_aggregate_report(reports: list[dict[str, Any]], all_changes: list[dict[str, Any]]) -> dict[str, Any]:
    summary_papers = []
    for report in sorted(reports, key=lambda r: r["year"]):
        summary_papers.append(
            {
                "year": report["year"],
                "paper": report["paper"],
                "question_count": report["question_count"],
                "status": report["status"],
                "figure_dependency_count": report["figure_dependency_count"],
                "secondary_mismatch_count": report["summary"]["secondary_mismatch_count"],
                "changed_question_count": report["summary"]["changed_question_count"],
                "report": next(p.report_path for p in PAPERS if p.year == report["year"]),
            }
        )
    summary = {
        "verified_at": VERIFIED_AT,
        "paper_count": len(reports),
        "question_count": sum(r["question_count"] for r in reports),
        "status": "needs_review" if any(r["status"] != "verified" for r in reports) else "verified",
        "reference_commit": REFERENCE_COMMIT,
        "papers": summary_papers,
        "change_count": len(all_changes),
    }
    verification_dir = ROOT / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (verification_dir / "change-log.json").write_text(
        json.dumps(all_changes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = [
        "# 2021—2026 浙江适用高考数学数据校验报告",
        "",
        f"校验日期：{VERIFIED_AT}",
        "",
        f"范围：{summary['paper_count']} 套试卷，共 {summary['question_count']} 道题。",
        "",
        "## 校验链路",
        "",
        "1. 下载 `deekur/gaokaomath` 原始 PDF，并按 Git blob SHA 核对文件身份；",
        f"2. 使用 `{REFERENCE_REPO}` 固定提交 `{REFERENCE_COMMIT}` 恢复完整题面、四选项与参考答案；",
        "3. 2021—2025 使用高考真题 Wiki 逐题答案页面做第二来源检查；2026 使用固定提交的独立结构化数据集检查；",
        "4. 检查 JSON/JSONL、题数、连续题号、唯一 ID、题型、四选项、答案及解析映射。",
        "",
        "## 分卷结果",
        "",
        "| 年份 | 卷型 | 题数 | 状态 | 二来源冲突 | 本次改动题数 | 含图题 |",
        "|---:|---|---:|---|---:|---:|---:|",
    ]
    for p in summary_papers:
        lines.append(
            f"| {p['year']} | {p['paper']} | {p['question_count']} | {p['status']} | "
            f"{p['secondary_mismatch_count']} | {p['changed_question_count']} | {p['figure_dependency_count']} |"
        )
    lines += [
        "",
        "## 状态含义",
        "",
        "- `verified`：原 PDF 文件身份、固定参考转写、答案/选项、第二来源和内部结构未发现未解决冲突。",
        "- `verified_with_figure_dependency`：单题已核到参考题图与答案，但脱离图形资源不能独立作答；题图链接保存在记录中。",
        "- `needs_review`：报告中仍有第二来源冲突，不能隐藏或强行判定。",
        "",
        "## 重要说明",
        "",
        "“校验通过”表示本仓库在上述来源链路下达到可追溯、可复现的一致性，不等同于考试主管部门的官方认证。",
        "完整逐题记录与修订前后差异见 `verification/*.json` 和 `verification/change-log.json`。",
        "",
    ]
    (ROOT / "VERIFICATION_REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline-structure-only", action="store_true")
    args = parser.parse_args()
    if args.offline_structure_only:
        # Delegate to the generated local validator when available.
        validator = ROOT / "scripts/validate_dataset.py"
        if not validator.exists():
            raise VerificationError("尚未生成 scripts/validate_dataset.py")
        namespace = {"__name__": "__main__", "__file__": str(validator)}
        exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), namespace)
        return 0

    secondary_2026 = load_secondary_2026()
    reports: list[dict[str, Any]] = []
    all_changes: list[dict[str, Any]] = []
    for config in PAPERS:
        print(f"[sync] {config.year} {config.paper_name}", flush=True)
        report, changes = sync_paper(config, secondary_2026)
        reports.append(report)
        all_changes.extend(changes)
        print(
            f"  questions={report['question_count']} status={report['status']} "
            f"secondary_mismatches={report['summary']['secondary_mismatch_count']} "
            f"changes={len(changes)}",
            flush=True,
        )

    update_metadata(reports)
    update_schema()
    update_attribution()
    write_license_note()
    write_structural_validator()
    summary = write_aggregate_report(reports, all_changes)
    update_readme(summary)

    if summary["status"] != "verified":
        print("存在第二来源冲突，已完整记录为 needs_review。", file=sys.stderr)
    else:
        print(f"校验完成：{summary['paper_count']} 套，{summary['question_count']} 道题。")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
