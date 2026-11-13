# -*- coding: utf-8 -*-
"""测试公用设施：把 scripts 目录挂进 sys.path，并提供造库工具。

刻意不建包（没有 __init__.py）：`py -3 -m unittest discover -s tests` 会把
tests/ 放进 sys.path，`from helpers import ...` 即可。这样测试不依赖安装方式，
也不要求 pytest —— 与项目「纯标准库」的定位一致。
"""
import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "skills" / "save-memory" / "engine"
if str(ENGINE) not in sys.path:
    sys.path.insert(0, str(ENGINE))

import mem as graph   # noqa: E402  —— 引擎模块叫 mem，测试里沿用 graph 这个名字
import validate       # noqa: E402


# 一篇格式完全合规的笔记：tags 2 个、四个必填字段齐全
NOTE_OK = """---
tags: [alpha, beta]
source: claude-code
created: 2026-01-01
updated: 2026-01-02
---
# 主题

## 一句话结论
结论正文。
"""

# 带两条类型化边（目标笔记可以不存在，解析阶段不校验存在性）
NOTE_EDGES = """---
tags: [alpha, beta]
source: claude-code
created: 2026-01-01
updated: 2026-01-02
related: ["[[目标]]"]
solved_by: "[[目标]]"
---
# 主题
"""

# 指向不存在笔记，用于红链检测
NOTE_RED_LINK = """---
tags: [alpha, beta]
source: claude-code
created: 2026-01-01
updated: 2026-01-02
related: ["[[不存在的笔记]]"]
---
# 主题
"""


def write_note(root, rel, text, bom=False):
    """在 root 下写一篇笔记；rel 可以带子目录。"""
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")
    return path


def make_note(name, tags=(), body="", edges=()):
    """直接造一个内存里的 Note，不落盘（用于打分逻辑的单元测试）。"""
    note = graph.Note(Path(name + ".md"), name + ".md", 0)
    note.tags = list(tags)
    note.body = body
    note.edges = [{"to": target, "type": edge_type} for target, edge_type in edges]
    return note


def temp_vault(case):
    """给 TestCase 装一套隔离的 vault / 缓存 / 记忆目录名，用例结束自动复原。

    必须隔离：graph.build() 用的是模块级 VAULT 与 CACHE，不隔离就会去扫用户
    真实的 Obsidian 仓库，并把结果写进 ~/.claude 缓存。
    """
    tmp = tempfile.TemporaryDirectory()
    vault = Path(tmp.name) / "vault"
    vault.mkdir()
    original = (graph.VAULT, graph.CACHE, graph.MEM_DIR)
    graph.VAULT = vault
    graph.CACHE = Path(tmp.name) / "graph-cache.json"
    graph.MEM_DIR = "AI记忆"

    def restore():
        graph.VAULT, graph.CACHE, graph.MEM_DIR = original
        tmp.cleanup()

    case.addCleanup(restore)
    return vault


def temp_dir(case):
    """只要一个干净的临时目录（不触碰 graph 的模块状态）。"""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    return Path(tmp.name)


def capture(func, *args, **kwargs):
    """跑一个会 print 的函数，返回 (退出码, 标准输出)。"""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = func(*args, **kwargs)
    return code, buffer.getvalue()
