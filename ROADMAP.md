# Roadmap

## v2：自动化 + 图谱（✅ 已完成，v0.2.0，2026-11-08）

1. ✅ **SessionEnd hook 自动总结**
   - 关键是节流而非触发：会话 <5 轮用户消息静默跳过（零成本），≥5 轮嵌套 headless 会话走提取规则
   - 配套 SessionStart 索引注入：会话开始注入记忆索引（awareness），内容留给按需 /recall 深读
2. ✅ **graph.py 多跳召回**
   - 混合召回：同义词扩词 → 标签/正文双通道种子计分（覆盖率加权）→ 一跳扩展（跳数衰减 × 边类型系数）→ 总分排序 → 字数预算输出
   - 类型化边语义：`superseded_by` 降权且标 ⚠️、`solved_by` 优先
   - `graph.json` 缓存 + mtime 增量更新
3. ✅ **园艺命令 `/garden-memory`**
   - 红链检测、碎片笔记合并、同义 tags 归并、超载域笔记拆分
   - 只报告不动手，逐项确认后修复

## v3：工程化 + 产品化（✅ 已完成，v0.3.0，2026-11-08）

4. ✅ **配置外置**：`~/.claude/save-memory.json` + 优先级链（CLI > 环境变量 > 配置文件 > 默认）+ 对话式安装 `/save-memory-setup`；多 vault 按项目路由留待后续
5. ✅ **打包成 Claude Code plugin**：`claude plugin marketplace add` 一条命令安装；hooks 默认关闭，显式 opt-in（注册片段见 README）
6. ✅ **校验脚本下沉**：frontmatter/文件名/编码校验从 prompt 约束改为 `validate.py` 确定性保证
7. ⬜ **语义检索**：本地 embedding + sqlite-vec（500+ 篇笔记后再做；打分管线已与匹配器解耦）
8. ✅ **记忆使用统计**：frontmatter 记 `recall_count`（`graph.py record` 维护），园艺报告 >14 天零召回笔记，用数据反哺提取规则

## 不做

- 记忆衰减自动删除（删数据必须人来决定）
- 联网同步/多人协作（Obsidian Sync 的领域）
- GUI
