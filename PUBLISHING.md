# 发布检查清单（GitHub）

发布前逐项确认；打勾后再创建远程仓库。**本文件不参与 skill 运行，发布完成后可保留或删除。**

## 1. 身份与占位符

- [x] README 中的 GitHub 地址已写死为 `blsssed/obsidian-memory-skill`（中文/English 安装段各一处 `git clone`、各一处 `claude plugin marketplace add`）
- [x] `LICENSE`、`plugin.json`、`marketplace.json`、`SKILL.md` 的署名已统一为 `blsssed`
- [x] git 提交身份已确认：保持 `mason <mason@qq.com>` 不变（2026-11-09 用户决定）

## 2. 内容检查

- [ ] `git status` 干净，无 `*.log`、`save-memory.json`、`__pycache__/`
- [ ] 仓库内无敏感信息：`grep -rn "sk-ant\|ANTHROPIC_AUTH_TOKEN\|api[_-]key" --include="*.md" --include="*.py" --include="*.json" .`
- [ ] 版本号一致：`skills/save-memory/SKILL.md`、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`、`CHANGELOG.md` 均为 `0.3.0`
- [ ] `claude plugin validate .` 通过
- [ ] `openspec validate add-v3-productization` 通过

## 3. 功能冒烟（发布前最后一遍）

```bash
# 在 repo 根执行
py -3 skills/save-memory/scripts/graph.py build
py -3 skills/save-memory/scripts/validate.py
claude plugin validate .
```

- [ ] README 的 plugin 安装命令在一个干净环境可用（本地替代验证：`claude plugin marketplace add <绝对路径>` + `claude plugin install save-memory@save-memory`，技能名应为 `save-memory:save-memory`）
- [ ] 手动复制路径可用：`cp -r skills/save-memory/* ~/.claude/skills/save-memory/`

## 4. 仓库设置（创建后）

- 描述建议：
  > Claude Code skill: capture conversation learnings into your Obsidian vault — extract, dedupe, graph recall, spring-cleaning.
- Topics 建议：`claude-code` `claude-code-skill` `claude-code-plugin` `obsidian` `knowledge-graph` `memory` `second-brain`
- 勾选 Issues；License 选 MIT（与 LICENSE 文件一致）
- 打 tag：`git tag -a v0.3.0 -m "v0.3.0"` 并随分支推送（`git push origin main --tags`），Release 说明可直接取自 CHANGELOG 对应小节

## 5. 发布后自测

- [ ] `claude plugin marketplace add <账号>/obsidian-memory-skill` 能拉取
- [ ] `claude plugin install save-memory@save-memory` 后技能可触发（新会话中技能列表出现 `save-memory:save-memory`）
- [ ] README 中的 hooks opt-in JSON 片段照抄可注册成功
- [ ] 在无 `~/.claude/save-memory.json` 的机器上首次运行会引导 `/save-memory-setup`

## 已知非阻断项

- Windows 下 git 会提示 LF→CRLF，`.gitattributes` 已统一为 `text=auto`，忽略即可
- plugin 缓存路径带版本号，hooks 注册路径在 plugin 升级后需重注册（README 已注明）
- 语义检索未实现（触发条件：500+ 篇笔记），README 路线图已标注
