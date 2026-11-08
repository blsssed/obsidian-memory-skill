# Proposal

## Why

v0.1.1 的手动闭环（提取审计表、封闭白名单、素材解耦、域级合并）已在真实使用中验证，但存在三个结构性缺口：一是总结依赖用户记得手动执行 `/save-memory`，遗忘即丢失；二是召回只是关键词 Grep，词面不同但语义相关的记忆捞不回来（搜"429"命中不了讲"限流"的笔记）；三是知识库长期只写不剪，红链、碎片笔记、同义标签会逐步积累。v2 用 SessionEnd/SessionStart hook 补齐自动化闭环，用图谱遍历 + 打分排序升级召回，用园艺流程防止知识库腐化。

## What Changes

- **SessionEnd hook 自动总结**：会话结束解析 transcript，用户消息 <5 轮静默跳过，≥5 轮以嵌套 headless 会话执行提取流程写入 vault（防递归标记 + 异步执行 + 日志）
- **SessionStart hook 索引注入**：会话启动/恢复时注入记忆索引（标题|tags|updated 清单），只做 awareness，不做内容检索
- **graph.py 混合召回**：新增脚本（build/expand/check/recall 子命令），召回升级为"同义词扩词 → 双通道产种子（标签/正文，覆盖率加权）→ 图谱一跳扩展（跳数衰减 × 边类型系数）→ 总分排序 → 字数预算内输出"
- **/garden-memory 园艺流程**：红链检测、碎片合并建议、tags 归并、域笔记分裂建议；只报告不修改，用户逐项确认

## Capabilities

### Modified Capabilities
- `conversation-memory`: `按需召回` requirement 从关键词 Grep 升级为图谱混合召回（覆盖率计分 + 多跳扩展 + 字数预算），并新增自动总结、会话启动注入、记忆园艺三个 requirement

## Impact

- 新增文件：`hooks/session_end.py`、`hooks/session_start.py`、`scripts/graph.py`
- 修改文件：`SKILL.md`（/recall 升级 + 流程三 /garden-memory + 配置区）
- 外部配置：用户级 `~/.claude/settings.json` 注册两个 hook（README 提供片段）
- 运行时副作用：会话结束后可能触发一次嵌套模型调用（≥5 轮时）；`~/.claude/save-memory.log` 日志写入
- 依赖：graph.py 零第三方依赖；hooks 使用 Python 标准库
