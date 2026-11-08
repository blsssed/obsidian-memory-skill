#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""save-memory 图谱工具：构建/扩展/混合召回/红链检测。

子命令：
  build                     扫描 vault 构建邻接表（写 ~/.claude/save-memory-graph.json 缓存）
  expand <笔记名> [-d N]    从种子笔记 BFS 扩展，输出邻居标题/首行/边类型
  recall <关键词...>        混合召回：同义词扩词 → 双通道产种子（覆盖率计分）
                            → 一跳扩展（跳数衰减×边系数）→ 总分排序 → 字数预算输出
  check                     红链检测（指向不存在笔记的双链）

打分参数全部集中在下方常量区，实测后一处调参。
零第三方依赖，仅标准库。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# ── 配置常量区（调参只改这里） ─────────────────────────────
VAULT = Path(os.environ.get("SAVE_MEMORY_VAULT", r"C:\Users\HONOR\Documents\Obsidian Vault"))
CACHE = Path.home() / ".claude" / "save-memory-graph.json"

W_TAG, W_TITLE, W_BODY = 2.0, 3.0, 1.0   # 标签/标题/正文 命中基础分
BODY_OCC_CAP = 3                           # 正文同一关键词出现次数计分上限
HOP_DECAY = 0.5                            # 每跳衰减
EDGE_COEF = {                              # 边类型系数
    "solved_by": 1.2, "solves": 1.2,
    "related": 1.0, "part_of": 1.0, "wikilink": 1.0,
    "supersedes": 0.3, "superseded_by": 0.3,
}
STALE_EDGES = {"supersedes", "superseded_by"}   # 到达节点标注 ⚠️ 已过时
DEFAULT_BUDGET = 3000                      # 召回输出总字数预算
SEED_TRUNC = 800                           # 种子笔记全文单篇截断
MIN_KW_LEN = 2                             # 关键词最短长度（防单字噪音）

# 同义词组：组内任一词命中，其余词进关键词池统一计分
SYNONYM_GROUPS = [
    ["重试", "retry"],
    ["限流", "rate limit", "rate-limit", "429"],
    ["报错", "错误", "error"],
    ["采样", "sampling"],
    ["温度", "temperature"],
    ["双链", "wikilink"],
    ["笔记", "note"],
    ["代理", "agent"],
    ["工作流", "workflow"],
    ["配置", "config", "settings"],
    ["环境", "env", "environment"],
    ["正则", "regex"],
]
# ───────────────────────────────────────────────────────────

LINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")  # 排除 ![[嵌入]]
EDGE_KEYS = ("related", "solved_by", "solves", "supersedes", "superseded_by", "part_of")


def split_frontmatter(text):
    """返回 (frontmatter原始文本, 正文)。"""
    if text.startswith("---"):
        nl = text.find("\n")
        end = text.find("\n---", nl)
        if end != -1:
            return text[nl + 1:end], text[end + 4:].lstrip("\n")
    return "", text


def parse_frontmatter(fm_text):
    """极简 YAML 子集解析：标量、单行列表 [a, b]、多行列表（- item）。"""
    data, current = {}, None
    for line in fm_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[0].isspace() and ":" in line:
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            current = key
            if val:
                data[key] = val
            else:
                data[key] = []
        elif current and stripped.startswith("- "):
            if not isinstance(data.get(current), list):
                data[current] = []
            data[current].append(stripped[2:].strip())
    return data


def clean_tag(v):
    return v.strip().strip("\"'").strip()


def link_names(value):
    """从标量或列表值里提取 [[链接]] 目标名。"""
    if value is None:
        return []
    if isinstance(value, list):
        return [m for item in value for m in link_names(item)]
    return [m.strip() for m in LINK_RE.findall(str(value))]


def parse_tags(value):
    if value is None:
        return []
    items = value if isinstance(value, list) else [v for v in str(value).strip().strip("[]").split(",")]
    return [clean_tag(v) for v in items if clean_tag(v)]


class Note:
    __slots__ = ("name", "path", "tags", "edges", "body", "first_line", "updated", "mtime")

    def __init__(self, path, mtime):
        self.path, self.mtime = path, mtime
        self.name = path.stem
        self.tags, self.edges, self.body = [], [], ""
        self.first_line, self.updated = "", ""


def parse_note(path, mtime):
    note = Note(path, mtime)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return note
    fm_text, note.body = split_frontmatter(text)
    fm = parse_frontmatter(fm_text)
    note.tags = [t.lower() for t in parse_tags(fm.get("tags"))]
    note.updated = clean_tag(str(fm.get("updated", "")))

    # frontmatter 类型化边
    for key in EDGE_KEYS:
        for target in link_names(fm.get(key)):
            note.edges.append({"to": target, "type": key})
    # 正文双链（去重）
    seen = {(e["to"], e["type"]) for e in note.edges}
    for target in LINK_RE.findall(note.body):
        if (target.strip(), "wikilink") not in seen:
            note.edges.append({"to": target.strip(), "type": "wikilink"})
            seen.add((target.strip(), "wikilink"))

    for line in note.body.splitlines():
        s = line.strip().lstrip("#").strip()
        if s:
            note.first_line = s[:60]
            break
    return note


def load_cached():
    if not CACHE.exists():
        return {}
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def build(verbose=True):
    """扫描 vault（mtime 增量），返回 {笔记名: Note}。"""
    cache = load_cached()
    graph, changed = {}, False
    files = {p: p.stat().st_mtime for p in VAULT.rglob("*.md")}

    for path, mtime in files.items():
        cached = cache.get(path.stem)
        if cached and cached.get("mtime") == mtime:
            note = Note(path, mtime)
            note.tags = cached["tags"]
            note.edges = cached["edges"]
            note.body = cached.get("body", "")
            note.first_line = cached.get("first_line", "")
            note.updated = cached.get("updated", "")
        else:
            note = parse_note(path, mtime)
            changed = True
        graph[note.name] = note

    # 清理已删除文件
    for name in set(cache) - set(graph):
        changed = True

    if changed and graph:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps({
            n.name: {"mtime": n.mtime, "tags": n.tags, "edges": n.edges,
                     "body": n.body, "first_line": n.first_line, "updated": n.updated}
            for n in graph.values()
        }, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print("已构建图谱：%d 篇笔记，%d 条边" % (
            len(graph), sum(len(n.edges) for n in graph.values())))
    return graph


def coverage(a, b):
    """覆盖率 = len(较短串)/len(较长串)，双向包含均命中，精确相等=1。"""
    a, b = a.lower(), b.lower()
    if a == b:
        return 1.0
    if a in b or b in a:
        return min(len(a), len(b)) / max(len(a), len(b))
    return 0.0


def expand_synonyms(keywords):
    """组内任一词命中，整组进池；去重保持顺序。"""
    pool, lowered = [], {k.lower() for k in keywords}
    for kw in keywords:
        if kw not in pool:
            pool.append(kw)
    for group in SYNONYM_GROUPS:
        gl = {g.lower() for g in group}
        if lowered & gl:
            for g in group:
                if g.lower() not in lowered and g not in pool:
                    pool.append(g)
    # 长度过滤
    return [k for k in pool if len(k) >= MIN_KW_LEN]


def seed_scores(graph, keywords):
    """双通道产种子：标签（覆盖率加权）+ 正文（标题/正文包含）。"""
    scores = {}
    for note in graph.values():
        s = 0.0
        title_l = note.name.lower()
        body_l = note.body.lower()
        for kw in keywords:
            for tag in note.tags:                       # 标签通道：覆盖率公式
                cov = coverage(kw, tag)
                if cov > 0:
                    s += W_TAG * cov
            if kw.lower() in title_l:                   # 标题通道：包含即全额
                s += W_TITLE
            occ = body_l.count(kw.lower())              # 正文通道：出现次数封顶
            if occ:
                s += W_BODY * min(occ, BODY_OCC_CAP)
        if s > 0:
            scores[note.name] = s
    return scores


def hop_scores(graph, seeds, depth=1):
    """BFS：邻居分 = 起点种子分 × 衰减^跳数 × 边类型系数。

    返回 {笔记名: {"score": 总分, "via": 到达边类型, "hop": 跳数}}。
    种子的 via/hop 为自身；同一节点多条路径到达取最大增益，避免分数爆炸。
    """
    result = {name: {"score": s, "via": None, "hop": 0} for name, s in seeds.items()}
    frontier = dict(seeds)
    for hop in range(1, depth + 1):
        nxt = {}
        for src, src_score in frontier.items():
            note = graph.get(src)
            if not note:
                continue
            for edge in note.edges:
                dst, coef = edge["to"], EDGE_COEF.get(edge["type"], 1.0)
                if dst in seeds:
                    continue
                gain = src_score * (HOP_DECAY ** hop) * coef
                if gain > nxt.get(dst, 0.0):
                    nxt[dst] = gain
                    result[dst] = {"score": gain, "via": edge["type"], "hop": hop}
        frontier = {k: v for k, v in nxt.items()}
    return result


def cmd_recall(args):
    graph = build(verbose=False)
    keywords = expand_synonyms(args.keywords)
    if not keywords:
        print("没有有效关键词（长度需 ≥%d 字符）" % MIN_KW_LEN)
        return 1
    seeds = seed_scores(graph, keywords)
    if not seeds:
        print("没有找到相关历史记忆（关键词：%s）" % ", ".join(keywords))
        return 0
    totals = hop_scores(graph, seeds, depth=args.depth)

    ranked = sorted(totals.items(), key=lambda x: -x[1]["score"])
    out, used, truncated = [], 0, 0
    seed_names = set(seeds)
    for name, info in ranked:
        note = graph.get(name)
        if note is None:
            continue
        block = render(note, info, is_seed=name in seed_names)
        if used + len(block) > args.budget:
            truncated += 1
            continue
        out.append(block)
        used += len(block)

    header = "# save-memory 召回结果\n关键词：%s\n\n" % ", ".join(keywords)
    print(header + "\n".join(out))
    if truncated:
        print("\n（已按字数预算 %d 截断，省略 %d 篇）" % (args.budget, truncated))
    return 0


def render(note, info, is_seed):
    """渲染单篇：种子出全文（截断），邻居出标题+首行+到达边。"""
    if is_seed:
        body = note.body.strip()[:SEED_TRUNC]
        more = "…（已截断）" if len(note.body.strip()) > SEED_TRUNC else ""
        return "## ★%.2f %s  [tags: %s]\n%s%s\n" % (
            info["score"], note.name, ", ".join(note.tags), body, more)
    stale = " ⚠️已过时" if info["via"] in STALE_EDGES else ""
    via = " ←%s" % info["via"] if info["via"] else ""
    return "## ☆%.2f%s%s %s\n%s\n" % (
        info["score"], via, stale, note.name, note.first_line)


def cmd_expand(args):
    graph = build(verbose=False)
    if args.note not in graph:
        print("笔记不存在：%s" % args.note)
        return 1
    totals = hop_scores(graph, {args.note: 1.0}, depth=args.depth)
    print("从《%s》扩展（depth=%d）：" % (args.note, args.depth))
    for name, info in sorted(totals.items(), key=lambda x: -x[1]["score"]):
        if name == args.note:
            continue
        note = graph.get(name)
        fl = note.first_line if note else ""
        stale = " ⚠️已过时" if info["via"] in STALE_EDGES else ""
        via = " ←%s" % info["via"] if info["via"] else ""
        print("  %.2f%s%s %s — %s" % (info["score"], via, stale, name, fl))
    return 0


def cmd_check(args):
    graph = build(verbose=False)
    red = []
    for note in graph.values():
        for edge in note.edges:
            if edge["to"] not in graph:
                red.append((note.name, edge["to"]))
    if not red:
        print("没有红链，知识库链接健康")
        return 0
    print("发现 %d 条红链：" % len(red))
    for src, target in red:
        best, best_cov = "", 0.0
        for name in graph:
            cov = coverage(target, name)
            if cov > best_cov:
                best, best_cov = name, cov
        hint = "（最接近的现有笔记：%s %.2f）" % (best, best_cov) if best_cov >= 0.5 else ""
        print("  %s → [[%s]] %s" % (src, target, hint))
    return 0


def cmd_build(args):
    build(verbose=True)
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows GBK 控制台下保证 UTF-8 输出
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="save-memory 图谱工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build").set_defaults(func=cmd_build)

    p_exp = sub.add_parser("expand", help="从种子笔记 BFS 扩展")
    p_exp.add_argument("note")
    p_exp.add_argument("-d", "--depth", type=int, default=1)
    p_exp.set_defaults(func=cmd_expand)

    p_rec = sub.add_parser("recall", help="混合召回")
    p_rec.add_argument("keywords", nargs="+")
    p_rec.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    p_rec.add_argument("-d", "--depth", type=int, default=1)
    p_rec.set_defaults(func=cmd_recall)

    sub.add_parser("check", help="红链检测").set_defaults(func=cmd_check)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
