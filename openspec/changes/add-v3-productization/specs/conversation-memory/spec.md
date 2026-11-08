# Spec Delta

## MODIFIED Requirements

### Requirement: 自动总结

SessionEnd hook SHALL 为 opt-in 功能：默认不注册、不运行、不产生任何模型调用；仅当用户显式注册（手动配置 settings.json 或按 README 指引开启）后才运行。开启后行为不变：会话结束时读取 transcript 并统计用户消息轮数，少于 5 轮静默跳过，达到 5 轮以嵌套 headless 会话执行提取流程（继承封闭白名单与审计规则）并写入 vault。hook SHALL 通过独立环境标记防止嵌套会话结束时再次触发自身，hook SHALL 以异步方式运行且显式设置超时，不阻塞会话退出。每次执行结果（轮数、跳过/执行/失败及原因）SHALL 记录到日志文件，使用户可事后确认每次自动总结的实际行为。

#### Scenario: 默认关闭

- **WHEN** 用户未显式注册或开启 SessionEnd hook
- **THEN** 不注册任何 hook，会话结束不触发任何总结与模型调用

#### Scenario: 短会话跳过

- **WHEN** 会话的用户消息少于 5 轮
- **THEN** hook 直接退出，不触发任何模型调用

#### Scenario: 达到阈值触发

- **WHEN** 会话用户消息达到 5 轮及以上
- **THEN** 嵌套 headless 会话按提取规则总结对话并写入 vault 的 AI记忆/ 目录

#### Scenario: 防递归

- **WHEN** 嵌套 headless 会话自身结束时触发 SessionEnd hook
- **THEN** hook 检测到防递归标记并直接退出，不产生循环调用

#### Scenario: 嵌套调用失败

- **WHEN** 嵌套调用超时或返回非零
- **THEN** 异常记录到日志文件，不影响用户会话退出

### Requirement: 会话启动注入

SessionStart hook SHALL 为 opt-in 功能：默认不注册、不注入；仅当用户显式开启后，在会话启动与恢复（startup/resume）时生成记忆索引并注入会话上下文：每篇经验笔记一行（标题、tags、updated），按 updated 倒序，行数上限约 40。索引 SHALL 仅用于让 Claude 知晓已有记忆的存在，笔记内容 SHALL 留待任务出现后按需检索深读。clear 与 compact 来源 SHALL 不重复注入。

#### Scenario: 默认关闭

- **WHEN** 用户未显式注册 SessionStart hook
- **THEN** 不注册任何 hook，会话启动不注入索引

#### Scenario: 新会话启动

- **WHEN** 会话以 startup 或 resume 来源开始且 hook 已开启
- **THEN** 记忆索引以结构化 hook 输出注入会话上下文

#### Scenario: 清除与压缩后

- **WHEN** SessionStart 以 clear 或 compact 来源触发
- **THEN** 不注入索引，避免重复

#### Scenario: 记忆为空

- **WHEN** AI记忆/ 目录不存在或为空
- **THEN** 不注入任何内容，会话正常开始

### Requirement: 记忆园艺

`/garden-memory` SHALL 检测知识库健康问题并默认只报告不修改：指向不存在笔记的双链（红链）、AI记忆/ 指向其他目录的可疑跨目录链接、别名与目标名差异过大的可疑链接、主题重叠的薄笔记（少于 10 行）、同义或大小写不一致的 tags、子主题数量超限（约 5 个小节以上）的域笔记、validate.py 检出的格式问题、创建超过 14 天且 recall_count 为 0 的零召回笔记（建议归档或合并）。修复 SHALL 仅在用户对具体条目确认后执行，且 SHALL 仅作用于 AI记忆/ 目录。

#### Scenario: 红链检测

- **WHEN** 存在指向不存在笔记的双链
- **THEN** 园艺报告列出红链及其可能的修复目标

#### Scenario: 零召回报告

- **WHEN** 存在创建超过 14 天且 recall_count 为 0 的经验笔记
- **THEN** 园艺报告列出这些笔记并建议归档或合并，等待用户裁决

#### Scenario: 只报告不修改

- **WHEN** 园艺检测完成
- **THEN** 输出问题清单且未修改任何文件，等待用户逐项确认

#### Scenario: 确认后修复

- **WHEN** 用户对某条问题确认修复
- **THEN** 系统仅对该条执行修复，其余保持不动

## ADDED Requirements

### Requirement: 配置外置

系统 SHALL 支持配置文件 `~/.claude/save-memory.json`（vault、memory_dir、snippet_dir），配置解析 SHALL 按优先级链执行：命令行参数 > 环境变量 > 配置文件 > 内置默认，高层级提供有效值时 SHALL 覆盖低层级。配置文件缺失、键缺失或 JSON 损坏时 SHALL 静默降级到下一层级，不使工具崩溃。`/save-memory-setup` SHALL 以对话方式完成安装：询问 vault 路径、验证目录存在、确认记忆目录名（默认 AI记忆/）、写入配置文件、以图谱构建验证配置可用并汇报；安装过程 SHALL NOT 请求图形界面，不引入第三方依赖。

#### Scenario: 高层级覆盖低层级

- **WHEN** 命令行参数与环境变量同时提供 vault 路径
- **THEN** 命令行参数的值生效

#### Scenario: 配置文件损坏

- **WHEN** 配置文件存在但 JSON 解析失败
- **THEN** 静默降级到内置默认或环境变量，工具正常完成本次运行

#### Scenario: 对话式安装

- **WHEN** 用户运行 /save-memory-setup 且无配置文件
- **THEN** Claude 询问并验证 vault 路径，写入配置文件，运行图谱构建验证后汇报配置结果

### Requirement: 写入校验

系统 SHALL 提供确定性校验脚本，检查经验笔记格式：frontmatter 必填字段（tags 2~5 个、source、created、updated）、文件名合法性（Windows 非法字符、长度、纯数字开头，并对高频泛词标题给出警告）、UTF-8 无 BOM 编码。`/save-memory` 写入新建或更新的笔记后 SHALL 立即对写入文件运行校验，检出问题 SHALL 当次修复；校验 SHALL NOT 判断链接语义健康（链接健康由园艺检测负责）。

#### Scenario: 写入后校验

- **WHEN** /save-memory 完成笔记写入
- **THEN** 对写入的文件运行校验，frontmatter 缺字段或编码不合格被检出并当次修复

#### Scenario: 泛词文件名警告

- **WHEN** 新笔记标题命中高频泛词（如"笔记""skill""未命名"）
- **THEN** 校验输出警告，提示该命名易被 Obsidian 自动补全误链

#### Scenario: 校验不越权

- **WHEN** 校验通过但笔记存在语义错误的链接
- **THEN** 校验不报告该问题（链接健康属于园艺检测职责）

### Requirement: 召回使用统计

经验笔记 frontmatter SHALL 支持可选字段 `recall_count`（默认 0）。/recall 召回命中后，系统 SHALL 对命中的种子笔记（不含图谱邻居）递增 recall_count，递增 SHALL 只修改 frontmatter、不动正文。统计结果用于园艺报告的零召回分析，SHALL NOT 自动归档或删除任何笔记。

#### Scenario: 召回计数

- **WHEN** /recall 返回结果且某笔记为种子
- **THEN** 该笔记 frontmatter 的 recall_count 加一，正文与其余字段不变

#### Scenario: 邻居不计数

- **WHEN** 某笔记仅作为图谱邻居出现在召回结果中
- **THEN** 该笔记的 recall_count 不变

#### Scenario: 统计不自动删数据

- **WHEN** 某笔记长期零召回
- **THEN** 仅在园艺报告中作为候选列出，归档或合并由用户逐项确认
