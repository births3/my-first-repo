# 高考数学结构化题库

本仓库用于将 `deekur/gaokaomath` 中的历年高考数学 PDF 试卷整理为题目级结构化数据，便于题库检索、RAG、AI 讲题、错题分析和自动组卷。

## 数据结构

- `data/<year>/<paper>.jsonl`：逐题数据，每行一道题
- `metadata/papers.json`：试卷元数据索引
- `schema.json`：题目字段规范
- `SOURCE_ATTRIBUTION.md`：来源与许可说明

## 单题字段

核心字段包括：

- `id`
- `year`
- `subject`
- `exam_type`
- `paper`
- `regions`
- `question_no`
- `question_type`
- `stem`
- `options`
- `answer`
- `analysis`
- `knowledge_points`
- `difficulty`
- `source`

## 当前进度

已建立基础结构，并登记 2024 年新高考 I 卷（适用地区包含浙江）的源文件信息。题目内容将按试卷逐步拆分并校验后写入 JSONL。

## 数据来源

原始试卷来源：`deekur/gaokaomath`。具体许可和署名要求见 `SOURCE_ATTRIBUTION.md`。
