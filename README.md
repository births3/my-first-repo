# 高考数学结构化题库

本仓库用于将 `deekur/gaokaomath` 中的历年高考数学 PDF 试卷整理为题目级结构化数据，便于题库检索、RAG、AI 讲题、错题分析和自动组卷。

## 数据结构

- `data/<year>/<paper>.jsonl`：逐题数据，每行一道题
- `analysis/<year>-<paper>.json`：逐题解题思路/解析
- `metadata/papers.json`：试卷元数据索引
- `schema.json`：题目字段规范
- `SOURCE_ATTRIBUTION.md`：来源与许可说明

## 单题字段

核心字段包括：`id`、`year`、`subject`、`exam_type`、`paper`、`regions`、`question_no`、`question_type`、`stem`、`options`、`answer`、`analysis`、`knowledge_points`、`difficulty`、`source`。

## 当前进度

### 2024 新高考 I 卷（浙江适用）
- 19 道题已完成题目级结构化：`data/2024/new-gaokao-1.jsonl`
- 19 道题已建立解析：`analysis/2024-new-gaokao-1.json`
- 第 11、17 题含原卷示意图，已保留 `needs_figure` 标记，待补图资源。

### 2023 新高考 I 卷（浙江适用）
- 已确认源卷并登记到 `metadata/papers.json`
- 已建立 `data/2023/new-gaokao-1.jsonl`
- 待进行逐题提取、答案校验和解析。

## 浙江适用卷

- 2024：新高考 I 卷
- 2023：新高考 I 卷

后续将继续向前整理 2022、2021 等浙江高考数学试卷，并逐步补齐详细解析、知识点标签和图形资源。

## 数据来源

原始试卷来源：`deekur/gaokaomath`。具体许可和署名要求见 `SOURCE_ATTRIBUTION.md`。

<!-- verification:start -->

## 2021—2026 校验结果

已收录 **6 套、123 道**浙江适用数学题。原始 PDF 的 Git blob SHA、题数、题型、四选项、答案、解析映射均已自动检查；题面与答案同步到固定提交的参考转写，并记录第二来源比对结果。

| 年份 | 卷型 | 题数 | 校验状态 | 含图题 |
|---:|---|---:|---|---:|
| 2021 | 浙江卷 | 22 | verified | 8 |
| 2022 | 浙江卷 | 22 | verified | 4 |
| 2023 | 新高考I卷 | 22 | verified | 1 |
| 2024 | 新高考I卷 | 19 | verified | 3 |
| 2025 | 全国1卷 | 19 | needs_review | 2 |
| 2026 | 全国1卷 | 19 | verified | 1 |

本地结构校验：

```bash
python scripts/validate_dataset.py
```

详细记录见 `VERIFICATION_REPORT.md` 和 `verification/`。

<!-- verification:end -->
