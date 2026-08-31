# 逐题独立解答与答案核验

本目录记录模型对 2021—2026 年浙江适用高考数学试题的逐题重新推导。

这项核验与 `verification/` 中的多源一致性校验不同：

1. 从题干和选项重新推导，不以仓库答案本身作为正确性理由；
2. 先记录 `derived_answer`，再与 `stored_answer` 比较；
3. 保存足以复查的关键推导；
4. 图形、表格或转写条件不足时标记 `needs_source_review`，不得强行判为一致；
5. 数值答案一致但推导不充分时，不计入 `independently_verified`；
6. 由于模型此前已经见过仓库答案，本次属于“非盲、但重新推导”的核验，不宣称为盲测。

## 状态

- `independently_verified`：从题面重新推导得到明确结论，且与仓库答案一致。
- `mismatch`：重新推导结果与仓库答案不同。
- `needs_source_review`：缺图、缺选项、题面转写疑似不完整或当前推导不足。
- `proof_checked`：证明题已重新建立完整证明链，并核对题目要求。

只有全部 123 道题均取得 `independently_verified` 或 `proof_checked`，且没有 `mismatch` / `needs_source_review`，才能宣布“所有题目经过独立解答核验”。
