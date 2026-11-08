# Tasks

## 1. 配置外置

- [x] 1.1 实现 `scripts/memory_config.py`：canonical 优先级链（--vault 参数 > SAVE_MEMORY_VAULT 环境变量 > ~/.claude/save-memory.json > 内置默认），坏 JSON 静默降级。验证：5 场景实测（无配置/只有文件/只有环境变量/--vault 覆盖/坏 JSON）
- [x] 1.2 graph.py 接入 memory_config 并新增 `--vault` 全局参数，移除顶部硬编码 VAULT。验证：优先级链 4 场景 + recall/check 行为回归一致
- [x] 1.3 hooks/session_end.py 与 session_start.py 内联配置副本（含 canonical 位置注释），支持 SAVE_MEMORY_VAULT 环境变量与配置文件。验证：模拟 payload 运行，配置文件路径生效
- [x] 1.4 SKILL.md 配置区改写：指向 ~/.claude/save-memory.json，流程开头读配置；无配置文件时提示运行 /save-memory-setup。验证：配置区与脚本行为一致

## 2. 对话式安装

- [x] 2.1 SKILL.md 新增"安装"小节 /save-memory-setup：询问 vault 路径 → 验证目录存在 → 确认记忆目录名（默认 AI记忆）→ 写配置文件 → graph.py build 验证 → 汇报。验证：对话演练一次，改 vault 后 build 读到新路径

## 3. 写入校验

- [x] 3.1 实现 `scripts/validate.py`：frontmatter 必填字段（tags 2~5/source/created/updated）、文件名合法性（非法字符/长度≤50/纯数字开头）+ 高频泛词警告（笔记/skill/未命名）、UTF-8 无 BOM；`--note` 单文件或默认扫 AI记忆/。验证：真实 vault 全量跑 + 故意造坏文件能抓
- [x] 3.2 SKILL.md 流程一第 4 步集成（写入后对写入文件跑 validate，检出即修）与 /garden-memory 报告项。验证：流程描述与 spec 写入校验 requirement 一致

## 4. 召回使用统计

- [x] 4.1 note-template.md frontmatter 模板增加 `recall_count: 0`（可选字段说明）。验证：模板与 spec 一致
- [x] 4.2 graph.py 新增 `record` 子命令：种子笔记名列表 → 只重写 frontmatter 段递增 recall_count，正文不动，全文行数校验防截断。验证：0→1，正文与 created 不变
- [x] 4.3 SKILL.md /recall 流程集成（命中后对种子笔记执行 record）与 /garden-memory 零召回报告项（>14 天且 recall_count==0，只报告）。验证：模拟召回后计数正确、园艺列出零召回笔记

## 5. plugin 打包

- [x] 5.1 研究 plugin 规范：claude-code-guide 子代理查官方文档 + 本地 `claude plugin --help` 双源验证，确认 .claude-plugin/plugin.json schema、marketplace 格式、hooks 分发方式。验证：结论写入本变更 design 增补
- [x] 5.2 按研究结论落 plugin 布局（.claude-plugin/plugin.json，hooks 不进 hooks.json），README 增加手动开启 hooks 的显式注册片段。验证：本地安装测试，skill 可从 plugin 加载
- [x] 5.3 session_end.py 可观测性增强：日志行标注 跳过/执行/失败 三态与轮数。验证：模拟运行后日志可对账

## 6. 文档与版本

- [x] 6.1 README 双语更新（配置文件、/save-memory-setup、plugin 安装路径、opt-in hooks 说明）、ROADMAP 勾选 v3、版本 0.3.0。验证：按 README 可在新机器完成安装
- [x] 6.2 全局安装同步（SKILL.md/references/scripts/hooks）+ git 提交。验证：~/.claude/skills/save-memory/ 与 repo 一致，status 干净

## 7. 收尾

- [x] 7.1 `openspec validate add-v3-productization` 通过，全部任务勾选。验证：validate 无 error
