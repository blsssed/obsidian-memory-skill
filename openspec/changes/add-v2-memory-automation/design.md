# Design

## Context

v1 手动闭环已验证（含 v0.1.1 规则加固）。v2 的技术风险集中在 Claude Code hooks 的确切行为；经对本机 claude.exe v2.1.301 二进制、changelog 缓存与真实 transcript 的验证，关键机制已确认（SessionStart stdout 可注入上下文、SessionEnd payload 字段、超时下限、防递归约束），细节见下。

## Goals

- 会话结束自动总结（≥5 轮），会话启动自动注入记忆索引
- 召回从关键词 Grep 升级为双通道 + 覆盖率计分 + 图谱一跳 + 字数预算的混合召回
- 园艺流程检测红链/碎片/同义标签/域笔记膨胀，只报告不擅动

## Non-Goals

- 向量/语义匹配（v3，匹配器已解耦可整体替换）
- 二跳默认开启（保留 --depth 2 手动入口）
- 嵌套调用的模型选择配置化
- plugin 打包分发（v3）
- recall_count 使用统计（v3）

## Decisions

- **轮数阈值 5**：用户决策。短会话静默跳过，兼顾成本与覆盖
- **防递归用独立标记 `SAVE_MEMORY_RUNNING`**：hook 环境中 `CLAUDECODE=1` 恒定存在不能单独作标记；嵌套 `claude -p` 由脚本设置该标记，hook 入口检测即退出
- **嵌套调用**：`claude -p --permission-mode acceptEdits --allowedTools Read Write Grep Glob --add-dir <vault>`，不用 `--bare`（禁用 skill 加载且对 AUTH_TOKEN+自定义 BASE_URL 认证未验证）、不用 bypassPermissions
- **hook 注册**：SessionEnd 无 reason matcher（所有结束原因都值得总结）、`async: true` + `timeout: 120`（SessionEnd 有 1.5s 强杀下限，必须显式超时）；SessionStart matcher `startup|resume`；Windows 下 hook 命令经 Git Bash 执行，用 bash 语法
- **SessionStart 注入用结构化输出**：`{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ...}}`（比裸 stdout 稳）；注入上限 50k 字符，索引 ~40 行远低于此
- **transcript 解析**：用 payload 的 `transcript_path`；轮数 = `type=="user"` 且 `isSidechain==false` 且 content 含 text 项 且 `origin.kind=="human"`（排除 tool_result 与 hook 注入的 meta 消息）
- **覆盖率计分**：`覆盖率 = len(较短串)/len(较长串)`，双向包含均命中；副产品是免费词形变体匹配（retry⊂retries）；中文关键词最短 2 字
- **同义词表不特判**：同义词扩词进关键词池统一计分
- **字数预算**：默认 3000 字，种子全文单篇截断 800 字、邻居标题+首行；截断由 graph.py 内部执行并标注
- **graph.json 缓存**：记录每文件 mtime，变化的增量重解析
- **园艺只报告**：问题清单 + 建议，用户逐项确认后才动手

## Risks / Trade-offs

- [hooks 行为基于本机二进制验证，官方文档当前网络不可达] → 实现时如遇不符以 code.claude.com/docs/en/hooks 为准；hook 模拟测试覆盖关键路径
- [嵌套调用拖慢会话退出] → async: true 异步执行 + 显式 timeout；失败仅记日志
- [嵌套会话的 skill 加载在 -p 模式未 100% 确认] → 端到端验证；兜底方案：prompt 内直接内联提取规则要点
- [打分公式参数（权重、衰减、系数）拍脑袋] → 全部集中为 graph.py 顶部常量，实测后一处调参
- [覆盖率公式的英文子串误命中（art⊂smart）] → 覆盖率惩罚自然压低得分（≈0.21），可接受，不加规则
