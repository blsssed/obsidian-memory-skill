# Proposal: add-v3-productization

## Why

v2 完成了自动化闭环与图谱召回，但项目要发布给他人使用还差三块地基：**配置硬编码**在 SKILL.md 与 3 个脚本共 4 处，别人装完要手动改多个文件且改漏静默失败；**格式规则靠 prompt 约束**，黑链事故（目标存在但语义错误的链接入库）已证明"靠自觉会漏"；**hooks 默认开启的形态**在真实使用中暴露了成本与可观测性顾虑，自动化必须从默认行为改为 opt-in。此外项目缺少使用数据：哪些笔记真的被召回过、哪些是噪音，无从得知，提取规则无法数据化迭代。

## What Changes

- **配置外置**：新增 `~/.claude/save-memory.json`（vault/memory_dir/snippet_dir），优先级链 `--vault 命令行 > 环境变量 > 配置文件 > 内置默认`，坏 JSON 静默降级；配套对话式安装 `/save-memory-setup`（问路径→验证→写配置→build 验证），零 GUI 零新依赖
- **写入校验下沉**：新增 `scripts/validate.py`（frontmatter 必填字段、文件名合法性含高频泛词警告、UTF-8 无 BOM），流程一写入后即跑，园艺纳入报告
- **召回使用统计**：frontmatter 可选字段 `recall_count`，graph.py 新增 `record` 子命令（只改 frontmatter），/recall 命中的种子笔记计数，园艺报告零召回老笔记建议归档
- **plugin 打包**：`.claude-plugin/plugin.json` 布局，一条命令安装；hooks 不随包分发，README 提供显式开启片段（opt-in 落地）
- **规格修正**：自动总结与会话启动注入两个需求改为默认关闭、配置显式开启，并增加可观测性要求

## Capabilities

### conversation-memory
MODIFIED：`自动总结`（opt-in 默认关闭 + 可观测性）、`会话启动注入`（opt-in）、`记忆园艺`（增加零召回报告项）
ADDED：`配置外置`、`写入校验`、`召回使用统计`

## Impact

- 代码：新增 scripts/memory_config.py、scripts/validate.py；graph.py 加 --vault 与 record 子命令；两 hooks 配置改读优先级链；SKILL.md/note-template.md/README/ROADMAP 更新
- 兼容性：现有 vault 与笔记无需迁移；未创建配置文件时行为与 v2 默认一致；hooks 停用状态不变
- 版本 0.2.0 → 0.3.0
