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

VAULT = Path(os.environ.get("SAVE_MEMORY_VAULT", r"C:\Users\HONOR\Documents\Obsidian Vault"))
MEM_DIR = VAULT / "AI记忆"
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
    if not MEM_DIR.is_dir():
        return  # 没有记忆目录，静默跳过
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
