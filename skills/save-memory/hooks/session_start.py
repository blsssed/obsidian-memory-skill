#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SessionStart hook：生成记忆索引注入会话上下文。

用法（settings.json 注册，matcher: startup|resume）：
  py -3 "$HOME/.claude/skills/save-memory/hooks/session_start.py"

输出结构化 JSON（additionalContext），Claude Code 会注入为新会话上下文。
索引只做 awareness（标题|tags|updated 清单），内容深读留给 /recall。
"""
import json
import os
import sys
from pathlib import Path

# ── 配置副本：与 scripts/memory_config.py（canonical）保持同步，改动需三处同步 ──
CONFIG_PATH = Path.home() / ".claude" / "save-memory.json"
DEFAULTS = {"vault": "", "memory_dir": "AI记忆"}


def load_config():
    """优先级链副本：环境变量 > 配置文件 > 内置默认。坏 JSON 静默降级。"""
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if v})
    except (OSError, ValueError):
        pass
    env_vault = os.environ.get("SAVE_MEMORY_VAULT")
    if env_vault:
        cfg["vault"] = env_vault
    return cfg


CFG = load_config()
VAULT = Path(CFG["vault"])
MEM_DIR = VAULT / CFG["memory_dir"]
MAX_ROWS = 40


def parse_note_meta(path):
    """轻量解析 frontmatter 的 tags 与 updated（不做全文解析）。"""
    tags, updated = [], ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if text.startswith("---"):
        nl = text.find("\n")
        end = text.find("\n---", nl)
        if end != -1:
            for line in text[nl + 1:end].splitlines():
                if line.startswith("tags:"):
                    raw = line[5:].strip().strip("[]")
                    tags = [t.strip().strip("\"'") for t in raw.split(",") if t.strip()]
                elif line.startswith("updated:"):
                    updated = line[8:].strip().strip("\"'")
    return tags, updated


def main():
    if not CFG["vault"] or not MEM_DIR.is_dir():
        return  # 未配置 vault 或没有记忆目录，静默跳过
    rows = []
    for p in sorted(MEM_DIR.glob("*.md")):   # 不递归 snippets/
        meta = parse_note_meta(p)
        if meta is None:
            continue
        tags, updated = meta
        rows.append((updated, p.stem, tags))
    if not rows:
        return  # 空，不注入

    rows.sort(key=lambda r: r[0], reverse=True)
    lines = ["[save-memory 记忆索引] 共 %d 篇经验笔记（按更新时间倒序，前 %d 篇）。"
             "相关任务出现时，用 /recall 或 graph.py recall 深读具体内容：" % (len(rows), min(MAX_ROWS, len(rows)))]
    for updated, title, tags in rows[:MAX_ROWS]:
        lines.append("- %s | tags: %s | updated: %s" % (title, ",".join(tags) or "-", updated or "-"))

    out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                  "additionalContext": "\n".join(lines)}}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
