# 数据来源与许可说明

本仓库的原始高考数学试卷资料来源于：

- Repository: `deekur/gaokaomath`
- Source project: Gaokao mathematics papers archive
- License declared by source repository: Creative Commons Attribution 4.0 International (CC BY 4.0)

本仓库对原始资料进行了结构化整理与字段化处理。若分发由源项目资料转换得到的数据，应保留原始来源、许可说明，并标注已进行格式转换/结构化处理。

源文件路径会保存在每道题的 `source.file` 字段中，便于追溯。

<!-- reference-attribution:start -->

## 校验与转写参考

本仓库的原始试卷来源仍为 `deekur/gaokaomath`（CC BY 4.0）。为恢复完整题面、选项、答案并进行逐题校验，使用了：

- `DxAThing/Gaokao-Math-Problems-Compilation`，固定提交 `4b69f48467d7883e1e9cf816680347ce34583ba8`，其原创转写、排版与解析内容按 CC BY-SA 4.0 提供；
- 高考真题 Wiki（2021—2025）作为第二答案来源；
- `iamyb/llm-gaokao-math-eval` 固定提交 `7b58eaf4574046c73e49cd75590dd4e30bfe3adf`，作为 2026 年独立结构化题面与答案来源。

数据记录中保留 `source`、`reference` 和 `verification` 字段。由 CC BY-SA 4.0 参考解析衍生或同步的内容，应继续遵守署名—相同方式共享要求。详见 `DATA_LICENSE.md`。

<!-- reference-attribution:end -->
