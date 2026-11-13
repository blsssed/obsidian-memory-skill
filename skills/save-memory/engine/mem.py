#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""save-memory 引擎：图谱构建、混合召回、体检与格式校验的 CLI。

所有与宿主无关的能力都在这里；宿主（Claude Code / Codex / …）只需要让模型
知道有这么一条命令，不必各自实现一遍逻辑。

子命令：
  build                     扫描 vault 构建邻接表（缓存写状态目录，见 state.py）
  recall <关键词...>        混合召回：同义词扩词 → 双通道种子计分 → 一跳扩展
                            （跳数衰减×边系数）→ 总分排序 → 字数预算输出
                            --record  顺带给本次输出的种子笔记 recall_count +1
  expand <笔记名> [-d N]    从某篇笔记 BFS 扩展，输出邻居标题/首行/边类型
  find <关键词...>          只出标题与路径，不注入正文（轻量定位）
  brief [-n N]              记忆索引（标题 | tags | updated），会话开始时喂给模型
  check                     全库体检：红链 / 跨目录链接 / 可疑别名
  check-links <笔记...>     校验指定笔记的双链目标是否真实存在
  record <笔记名...>        种子笔记 recall_count +1（只改 frontmatter）

打分参数全部集中在下方常量区，实测后一处调参。
零第三方依赖，仅标准库。
"""
import argparse
import contextlib
import json
import os
import re
import sys
from pathlib import Path

from memory_config import get_config   # 同目录模块，脚本运行时 sys.path[0] 即本目录
from state import state_home, state_path
import validate                        # 同目录模块

# ── 配置常量区（调参只改这里） ─────────────────────────────
_cfg = get_config()                     # vault 可被 --vault 参数覆盖（见 main）
VAULT = Path(_cfg["vault"]) if _cfg["vault"] else None   # None = 未配置
MEM_DIR = _cfg.get("memory_dir") or "AI记忆"             # 记忆目录名（vault 内相对路径前缀）
CACHE = state_home() / "save-memory-graph.json"
CACHE_VERSION = 4  # v4：缓存 key 由 stem 改为 vault 内相对路径 + BOM 安全读取

W_TAG, W_TITLE, W_BODY = 2.0, 3.0, 1.0   # 标签/标题/正文 命中基础分
BODY_OCC_CAP = 3                           # 正文同一关键词出现次数计分上限
MIN_TAG_COVERAGE = 0.6                     # 标签通道最低覆盖率：低于它视为弱包含（env→environment）不计分
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

LINK_RE = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]*))?\]\]")  # 排除 ![[嵌入]]，捕获目标与别名
FENCE_RE = re.compile(r"```.*?(?:```|\Z)", re.S)   # 围栏代码块（含未闭合）
CODE_SPAN_RE = re.compile(r"`[^`\n]+`")            # 行内代码


def strip_code(text):
    """剥掉代码段，防止 `` `[[` `` 等代码内的方括号被解析成链接。"""
    return CODE_SPAN_RE.sub("", FENCE_RE.sub("", text))
EDGE_KEYS = ("related", "solved_by", "solves", "supersedes", "superseded_by", "part_of")


def write_atomic(path, data):
    """写同目录临时文件再原子替换。

    另一个进程读这个文件时，要么看到旧的完整内容，要么看到新的完整内容，
    不会读到写了一半的 JSON（那会让 load_cached 白白丢弃整份缓存）。
    """
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, bytes):
        tmp.write_bytes(data)
    else:
        tmp.write_text(data, encoding="utf-8")
    os.replace(tmp, path)


@contextlib.contextmanager
def exclusive_lock():
    """跨进程排他锁，保护「读-改-写」序列。

    拿不到锁 / 平台不支持 / 状态目录不可写时**静默降级为无锁**：正确性由
    write_atomic 兜底，锁只负责避免两个 agent 同时改 recall_count 丢计数。
    所以它绝不能让主流程失败。
    """
    handle = None
    try:
        lock_path = CACHE.parent / ".save-memory.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(lock_path, "a+b")
    except OSError:
        handle = None

    if handle is None:
        yield
        return

    locked = False
    try:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        except OSError:
            locked = False
        yield
    finally:
        if locked:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        handle.close()


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
    return [m[0].strip() for m in LINK_RE.findall(str(value))]


def parse_tags(value):
    if value is None:
        return []
    items = value if isinstance(value, list) else [v for v in str(value).strip().strip("[]").split(",")]
    return [clean_tag(v) for v in items if clean_tag(v)]


class Note:
    __slots__ = ("name", "rel", "path", "tags", "edges", "body", "first_line", "updated", "mtime")

    def __init__(self, path, rel, mtime):
        self.path, self.rel, self.mtime = path, rel, mtime
        self.name = path.stem
        self.tags, self.edges, self.body = [], [], ""
        self.first_line, self.updated = "", ""


class Graph(dict):
    """key = vault 内相对路径（posix 形式）。同名笔记各占一个 key，不再互相覆盖。

    Obsidian 的 [[名字]] 本来就有歧义；by_name 保留全部候选 rel，
    而不是任选其一、把另一个静默丢掉（旧实现用 stem 做 key，后者覆盖前者）。
    """

    def __init__(self):
        super().__init__()
        self.by_name = {}

    def add(self, note):
        self[note.rel] = note
        self.by_name.setdefault(note.name, []).append(note.rel)

    def resolve(self, name):
        """链接名 → Note 列表（可能多篇同名）。"""
        return [self[rel] for rel in self.by_name.get(name, ())]

    def has_name(self, name):
        return name in self.by_name


def parse_note(path, rel, mtime):
    note = Note(path, rel, mtime)
    try:
        # utf-8-sig：Windows 记事本 / 旧版 PowerShell Set-Content 写出的文件带 BOM。
        # 用 utf-8 读会让首字符变成 \ufeff，startswith("---") 直接失败，
        # 整段 frontmatter 混进正文，类型化边退化成 wikilink（过时标注随之失效）。
        text = path.read_text(encoding="utf-8-sig", errors="replace")
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
    # 正文双链（去重；别名存入边，供 check 检测自动补全误链；代码段内不解析）
    seen = {(e["to"], e["type"]) for e in note.edges}
    for target, alias in LINK_RE.findall(strip_code(note.body)):
        target = target.strip()
        if (target, "wikilink") not in seen:
            edge = {"to": target, "type": "wikilink"}
            if alias.strip():
                edge["alias"] = alias.strip()
            note.edges.append(edge)
            seen.add((target, "wikilink"))

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
    """扫描 vault（mtime 增量），返回 Graph（key = vault 内相对路径）。"""
    cache = load_cached()
    graph = Graph()
    changed = False
    files = {p: p.stat().st_mtime for p in VAULT.rglob("*.md")}

    for path, mtime in files.items():
        rel = path.relative_to(VAULT).as_posix()
        cached = cache.get(rel)
        if cached and cached.get("mtime") == mtime and cached.get("v") == CACHE_VERSION:
            note = Note(path, rel, mtime)
            note.tags = cached["tags"]
            note.edges = cached["edges"]
            note.body = cached.get("body", "")
            note.first_line = cached.get("first_line", "")
            note.updated = cached.get("updated", "")
        else:
            note = parse_note(path, rel, mtime)
            changed = True
        graph.add(note)

    # 清理已删除文件
    for rel in set(cache) - set(graph):
        changed = True

    if changed and graph:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({
            n.rel: {"v": CACHE_VERSION, "mtime": n.mtime, "tags": n.tags, "edges": n.edges,
                    "body": n.body, "first_line": n.first_line, "updated": n.updated}
            for n in graph.values()
        }, ensure_ascii=False)
        with exclusive_lock():
            try:
                write_atomic(CACHE, payload)
            except OSError:
                pass    # 缓存写不进去（只读沙箱等）不该让召回整条失败
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


_ASCII_BOUNDARY_RE = {}


def count_hits(kw, text):
    """关键词命中次数。

    纯 ASCII 关键词按 ASCII 词边界匹配，避免 "ai" 命中 "email" / "wait_exponential"。
    边界只认 [A-Za-z0-9_]，所以 "用429重试" 这类中文邻接仍能命中 429；
    含非 ASCII 的关键词（中文等）按原样子串匹配——中文没有词边界概念。
    """
    if not kw or not text:
        return 0
    if all(ord(ch) < 128 for ch in kw):
        pattern = _ASCII_BOUNDARY_RE.get(kw)
        if pattern is None:
            pattern = re.compile(
                r"(?<![A-Za-z0-9_])" + re.escape(kw) + r"(?![A-Za-z0-9_])", re.IGNORECASE)
            _ASCII_BOUNDARY_RE[kw] = pattern
        return len(pattern.findall(text))
    return text.lower().count(kw.lower())


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
    """双通道产种子：标签（覆盖率加权 + 最低阈值）+ 标题/正文（词边界命中）。"""
    scores = {}
    for note in graph.values():
        s = 0.0
        for kw in keywords:
            for tag in note.tags:                       # 标签通道：覆盖率公式
                cov = coverage(kw, tag)
                if cov >= MIN_TAG_COVERAGE:             # 弱包含（env→environment）不计分
                    s += W_TAG * cov
            if count_hits(kw, note.name):               # 标题通道：命中即全额
                s += W_TITLE
            occ = count_hits(kw, note.body)             # 正文通道：出现次数封顶
            if occ:
                s += W_BODY * min(occ, BODY_OCC_CAP)
        if s > 0:
            scores[note.rel] = s
    return scores


def hop_scores(graph, seeds, depth=1):
    """BFS：邻居分 = 起点种子分 × 衰减^跳数 × 边类型系数。

    返回 {相对路径: {"score": 总分, "via": 到达边类型, "hop": 跳数}}。
    种子的 via/hop 为自身；同一节点多条路径到达取最大增益，避免分数爆炸。
    一个链接名可能对应多篇同名笔记，逐个计入，不任选其一。
    """
    result = {rel: {"score": s, "via": None, "hop": 0} for rel, s in seeds.items()}
    frontier = dict(seeds)
    for hop in range(1, depth + 1):
        nxt = {}
        for src, src_score in frontier.items():
            note = graph.get(src)
            if not note:
                continue
            for edge in note.edges:
                coef = EDGE_COEF.get(edge["type"], 1.0)
                gain = src_score * (HOP_DECAY ** hop) * coef
                for dst in graph.by_name.get(edge["to"], ()):   # 同名多篇都是邻居
                    if dst in seeds:
                        continue
                    if gain > nxt.get(dst, 0.0):
                        nxt[dst] = gain
                        result[dst] = {"score": gain, "via": edge["type"], "hop": hop}
        frontier = dict(nxt)
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
    seed_rels = set(seeds)
    shown_seeds = []
    for rel, info in ranked:
        note = graph.get(rel)
        if note is None:
            continue
        block = render(note, info, is_seed=rel in seed_rels, graph=graph)
        if used + len(block) > args.budget:
            truncated += 1
            continue
        out.append(block)
        used += len(block)
        if rel in seed_rels:
            shown_seeds.append(rel)

    header = "# save-memory 召回结果\n关键词：%s\n\n" % ", ".join(keywords)
    print(header + "\n".join(out))
    if truncated:
        print("\n（已按字数预算 %d 截断，省略 %d 篇）" % (args.budget, truncated))
    if getattr(args, "record", False) and shown_seeds:
        bumped = 0
        for rel in shown_seeds:
            if bump_recall_count(graph.get(rel), quiet=True) is not None:
                bumped += 1
        if bumped:
            print("\n（已记录召回计数：%d 篇）" % bumped)
    return 0


def display_name(note, graph):
    """同名笔记补上相对路径，避免读者以为只有一篇。"""
    if len(graph.by_name.get(note.name, ())) > 1:
        return "%s（%s）" % (note.name, note.rel)
    return note.name


def render(note, info, is_seed, graph):
    """渲染单篇：种子出全文（截断），邻居出标题+首行+到达边。"""
    label = display_name(note, graph)
    if is_seed:
        body = note.body.strip()[:SEED_TRUNC]
        more = "…（已截断）" if len(note.body.strip()) > SEED_TRUNC else ""
        return "## ★%.2f %s  [tags: %s]\n%s%s\n" % (
            info["score"], label, ", ".join(note.tags), body, more)
    stale = " ⚠️已过时" if info["via"] in STALE_EDGES else ""
    via = " ←%s" % info["via"] if info["via"] else ""
    return "## ☆%.2f%s%s %s\n%s\n" % (
        info["score"], via, stale, label, note.first_line)


def cmd_expand(args):
    graph = build(verbose=False)
    targets = graph.resolve(args.note)
    if not targets:
        print("笔记不存在：%s" % args.note)
        return 1
    for start in targets:
        totals = hop_scores(graph, {start.rel: 1.0}, depth=args.depth)
        print("从《%s》扩展（depth=%d）：" % (display_name(start, graph), args.depth))
        for rel, info in sorted(totals.items(), key=lambda x: -x[1]["score"]):
            if rel == start.rel:
                continue
            other = graph.get(rel)
            label = display_name(other, graph) if other else rel
            fl = other.first_line if other else ""
            stale = " ⚠️已过时" if info["via"] in STALE_EDGES else ""
            via = " ←%s" % info["via"] if info["via"] else ""
            print("  %.2f%s%s %s — %s" % (info["score"], via, stale, label, fl))
    return 0


def cmd_check(args):
    graph = build(verbose=False)
    mem_prefix = MEM_DIR.rstrip("/") + "/"
    red, cross, alias_bad = [], [], []
    for note in graph.values():
        in_mem = note.rel.startswith(mem_prefix)
        for edge in note.edges:
            target = edge["to"]
            if not graph.has_name(target):
                red.append((note.rel, target))
            elif in_mem and any(
                    not t.rel.startswith(mem_prefix) for t in graph.resolve(target)):
                if (note.rel, target) not in cross:
                    cross.append((note.rel, target))
            alias = edge.get("alias", "")
            if alias and coverage(alias, target) < 0.5:
                if (note.rel, target, alias) not in alias_bad:
                    alias_bad.append((note.rel, target, alias))
    if not (red or cross or alias_bad):
        print("链接健康：无红链、无可疑跨目录链接、无可疑别名链接")
        return 0
    if red:
        print("发现 %d 条红链（目标不存在）：" % len(red))
        for src, target in red:
            best, best_cov = "", 0.0
            for name in graph.by_name:
                cov = coverage(target, name)
                if cov > best_cov:
                    best, best_cov = name, cov
            hint = "（最接近：%s %.2f）" % (best, best_cov) if best_cov >= 0.5 else ""
            print("  %s → [[%s]] %s" % (src, target, hint))
    if cross:
        print("发现 %d 条跨目录链接（%s → 其他目录；对话中明确提及的可保留）：" % (len(cross), MEM_DIR))
        for src, target in cross:
            print("  %s → [[%s]]" % (src, target))
    if alias_bad:
        print("发现 %d 条可疑别名链接（别名与目标名差异过大，疑似自动补全误链）：" % len(alias_bad))
        for src, target, alias in alias_bad:
            print("  %s → [[%s]] 别名「%s」" % (src, target, alias))
    return 0


def bump_recall_count(note, quiet=False):
    """把一篇笔记的 recall_count +1：只重写 frontmatter 段，正文一字不动。

    返回新计数；无法处理（无 frontmatter / 未闭合 / 重写校验失败 / IO 失败）
    时返回 None。quiet=True 用于召回路径上的顺带记账，不打扰输出。

    整体持锁：两个 agent 同时召回同一篇时，避免「读-改-写」互相覆盖丢计数。
    """
    with exclusive_lock():
        return _bump_unlocked(note, quiet)


def _bump_unlocked(note, quiet=False):
    try:
        raw = note.path.read_bytes()
    except OSError as e:
        if not quiet:
            print("读取失败：%s（%s）" % (note.rel, e))
        return None

    has_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig", errors="replace")
    if not text.startswith("---"):
        if not quiet:
            print("无 frontmatter，跳过：%s" % note.rel)
        return None
    nl = text.find("\n")
    end = text.find("\n---", nl)
    if end == -1:
        if not quiet:
            print("frontmatter 未闭合，跳过：%s" % note.rel)
        return None

    body = text[end + 4:]                       # 正文原样保留
    lines = text[nl + 1:end].splitlines()
    new_lines, count, found = [], 0, False
    for line in lines:
        if line.strip().startswith("recall_count:"):
            val = line.split(":", 1)[1].strip()
            count = int(val) + 1 if val.isdigit() else 1
            new_lines.append("recall_count: %d" % count)
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append("recall_count: 1")
        count = 1
    new_text = "---\n" + "\n".join(new_lines) + "\n---" + body
    # 安全校验：新文件必须以未动的原正文结尾，且长度只增不减
    if not (new_text.endswith(body) and len(new_text) > len(body)):
        if not quiet:
            print("重写校验失败，放弃写入：%s" % note.rel)
        return None
    # 保持原文件的 BOM 状态，不擅自改变编码（write_bytes 也避免换行转换）
    payload = new_text.encode("utf-8")
    if has_bom:
        payload = b"\xef\xbb\xbf" + payload
    try:
        write_atomic(note.path, payload)
    except OSError as e:
        if not quiet:
            print("写入失败：%s（%s）" % (note.rel, e))
        return None
    return count


def cmd_record(args):
    """种子笔记 recall_count +1（命令行入口）。"""
    graph = build(verbose=False)
    done, missing = [], []
    for name in args.notes:
        targets = graph.resolve(name)
        if not targets:
            missing.append(name)
            continue
        for note in targets:
            count = bump_recall_count(note)
            if count is not None:
                done.append((note.rel, count))
    for rel, count in done:
        print("recall_count → %d：%s" % (count, rel))
    for name in missing:
        print("笔记不存在：%s" % name)
    return 1 if missing else 0


def cmd_brief(args):
    """记忆索引：只列标题 / tags / updated，不注入正文。

    给模型一个「已经存在哪些记忆」的目录视图——awareness 而非内容。
    具体内容留给 recall 按需深读，避免每次会话都把这些笔记全文塞进上下文。
    """
    graph = build(verbose=False)
    prefix = MEM_DIR.rstrip("/")
    # 只列记忆目录的**直接子文件**（经验笔记）；snippets/ 下的素材不算经验，
    # 它们没有 updated，混进来会让索引变成一列 "-"。
    rows = [(note.updated, display_name(note, graph), note.tags)
            for note in graph.values()
            if note.rel.startswith(prefix + "/") and note.rel.count("/") == 1]
    if not rows:
        print("（记忆库为空：vault 下没有 %s 目录，或其中还没有笔记）" % MEM_DIR)
        return 0
    rows.sort(key=lambda row: row[0], reverse=True)
    limit = max(1, min(args.limit, len(rows)))
    print("[save-memory 记忆索引] 共 %d 篇经验笔记（按更新时间倒序，前 %d 篇）。"
          "相关任务出现时用 recall 深读具体内容：" % (len(rows), limit))
    for updated, label, tags in rows[:limit]:
        print("- %s | tags: %s | updated: %s" % (
            label, ",".join(tags) or "-", updated or "-"))
    return 0


def cmd_find(args):
    """轻量定位：只出得分、标题、路径，不注入正文。"""
    graph = build(verbose=False)
    keywords = expand_synonyms(args.keywords)
    if not keywords:
        print("没有有效关键词（长度需 ≥%d 字符）" % MIN_KW_LEN)
        return 1
    seeds = seed_scores(graph, keywords)
    if not seeds:
        print("没有命中（关键词：%s）" % ", ".join(keywords))
        return 0
    ranked = sorted(seeds.items(), key=lambda item: -item[1])
    shown = max(1, min(args.limit, len(ranked)))
    for rel, score in ranked[:shown]:
        note = graph.get(rel)
        label = display_name(note, graph) if note else rel
        print("%6.2f  %s  (%s)" % (score, label, rel))
    if len(ranked) > shown:
        print("（共 %d 篇命中，只列前 %d 篇；要正文用 recall）" % (len(ranked), shown))
    return 0


def cmd_check_links(args):
    """校验指定笔记的双链目标是否真实存在，供写入流程落盘前自检。"""
    graph = build(verbose=False)
    bad = 0
    for name in args.notes:
        targets = graph.resolve(name)
        if not targets:
            print("笔记不存在：%s" % name)
            bad += 1
            continue
        for note in targets:
            for edge in note.edges:
                if not graph.has_name(edge["to"]):
                    print("红链：%s → [[%s]]" % (note.rel, edge["to"]))
                    bad += 1
    if bad:
        print("发现 %d 处问题" % bad)
        return 1
    print("链接全部有效")
    return 0


def cmd_validate(args):
    """格式校验：frontmatter / 文件名 / 编码（规则实现在 validate.py）。"""
    if args.note:
        target = Path(args.note)
        if not target.is_file():
            print("文件不存在：%s" % args.note)
            return 1
        targets = [target]
    else:
        mem_dir = Path(VAULT) / MEM_DIR
        if not mem_dir.is_dir():
            print("记忆目录不存在：%s" % mem_dir)
            return 1
        targets = sorted(mem_dir.glob("*.md"))
    total_err, _ = validate.check_paths(targets)
    return 1 if total_err else 0


def cmd_build(args):
    build(verbose=True)
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")   # Windows GBK 控制台下保证 UTF-8 输出
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="save-memory 引擎")
    ap.add_argument("--vault", help="覆盖 vault 路径（优先级链最高层）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("build", help="构建图谱缓存").set_defaults(func=cmd_build)

    p = sub.add_parser("record", help="种子笔记 recall_count +1（只改 frontmatter）")
    p.add_argument("notes", nargs="+")
    p.set_defaults(func=cmd_record)

    p = sub.add_parser("expand", help="从某篇笔记 BFS 扩展")
    p.add_argument("note")
    p.add_argument("-d", "--depth", type=int, default=1)
    p.set_defaults(func=cmd_expand)

    p = sub.add_parser("recall", help="混合召回")
    p.add_argument("keywords", nargs="+")
    p.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    p.add_argument("-d", "--depth", type=int, default=1)
    p.add_argument("--record", action="store_true",
                   help="顺带给本次输出的种子笔记 recall_count +1")
    p.set_defaults(func=cmd_recall)

    p = sub.add_parser("find", help="轻量定位：只出标题与路径，不注入正文")
    p.add_argument("keywords", nargs="+")
    p.add_argument("-n", "--limit", type=int, default=20)
    p.set_defaults(func=cmd_find)

    p = sub.add_parser("brief", help="记忆索引（标题 | tags | updated）")
    p.add_argument("-n", "--limit", type=int, default=40)
    p.set_defaults(func=cmd_brief)

    sub.add_parser("check", help="全库体检：红链 / 跨目录 / 可疑别名").set_defaults(func=cmd_check)

    p = sub.add_parser("check-links", help="校验指定笔记的双链目标是否存在")
    p.add_argument("notes", nargs="+")
    p.set_defaults(func=cmd_check_links)

    p = sub.add_parser("validate", help="格式校验（frontmatter / 文件名 / 编码）")
    p.add_argument("--note", help="只校验指定文件；缺省则扫整个记忆目录")
    p.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    if args.vault:
        global VAULT
        VAULT = Path(args.vault)
    if VAULT is None:
        print("未配置 vault：请运行 /save-memory-setup，或把 "
              "{\"vault\": \"<你的 Obsidian 仓库路径>\"} 写入 %s"
              % state_path("save-memory.json"))
        sys.exit(1)
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
