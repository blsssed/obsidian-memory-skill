#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""save-memory 格式校验 —— 只管格式，链接健康归 graph.py check（职责边界见 spec）。

检查项：
  1. frontmatter 必填字段：tags（2~5 个）、source、created、updated
  2. 文件名：Windows 非法字符、长度 ≤50、纯数字开头；高频泛词标题 → 警告
  3. 编码：UTF-8 无 BOM、可严格解码

用法：
  py -3 validate.py [--note <文件路径>]      # 默认扫 <记忆目录>（不递归 snippets/）
退出码：有 error 退出 1，只有 warning 或干净退出 0。
"""
import argparse
import sys
from pathlib import Path

from memory_config import get_config   # 同目录模块；hooks 不用本脚本，无内联需求

# 高频泛词：标题含这些词易被 Obsidian 自动补全误链（黑链事故的命名规则落地）
GENERIC_WORDS = {"笔记", "skill", "未命名", "note", "untitled", "doc", "文档"}
ILLEGAL_CHARS = set('\\/:*?"<>|')


def split_frontmatter(text):
    if text.startswith("---"):
        nl = text.find("\n")
        end = text.find("\n---", nl)
        if end != -1:
            return text[nl + 1:end], text[end + 4:]
    return None, text


def parse_tags(fm_text):
    """极简 tags 解析：单行 [a, b] 与多行 - item 两种形态。"""
    items, in_list = [], False
    for line in fm_text.splitlines():
        s = line.strip()
        if s.startswith("tags:"):
            raw = s[5:].strip().strip("[]")
            items = [t.strip().strip("\"'") for t in raw.split(",") if t.strip()]
            in_list = raw == ""
        elif in_list and s.startswith("- "):
            items.append(s[2:].strip().strip("\"'"))
        elif s and not line[0].isspace() and ":" in s:
            in_list = False
    return [t for t in items if t]


def validate_note(path):
    """返回 (errors, warnings) 两个字符串列表。"""
    errors, warnings = [], []
    stem = path.stem

    # 编码：BOM 检查 + 严格 UTF-8 解码
    try:
        raw = path.read_bytes()
    except OSError as e:
        return ["读取失败：%s" % e], []
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("含 UTF-8 BOM，应保存为无 BOM")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("不是合法 UTF-8（可能 GBK 或其他编码）")
        return errors, warnings

    # 文件名
    if any(ch in ILLEGAL_CHARS for ch in stem):
        errors.append("文件名含 Windows 非法字符")
    if len(stem) > 50:
        errors.append("文件名超过 50 字符")
    if stem[:1].isdigit():
        errors.append("文件名纯数字开头")
    if any(w in stem.lower() for w in GENERIC_WORDS):
        warnings.append("标题含高频泛词（%s），易被 Obsidian 自动补全误链" %
                        "/".join(w for w in GENERIC_WORDS if w in stem.lower()))

    # frontmatter
    fm_text, _ = split_frontmatter(text)
    if fm_text is None:
        errors.append("缺少 frontmatter（应以 --- 开头）")
        return errors, warnings
    tags = parse_tags(fm_text)
    if not (2 <= len(tags) <= 5):
        errors.append("tags 数量 %d 个（要求 2~5）" % len(tags))
    for field in ("source", "created", "updated"):
        if not any(line.strip().startswith(field + ":") for line in fm_text.splitlines()):
            errors.append("frontmatter 缺少 %s 字段" % field)

    # recall_count：可选字段，出现则须为非负整数
    for line in fm_text.splitlines():
        if line.strip().startswith("recall_count:"):
            val = line.split(":", 1)[1].strip()
            if not val.isdigit():
                errors.append("recall_count 不是非负整数（%r）" % val)
    return errors, warnings


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser(description="save-memory 格式校验（只管格式，链接健康归 graph.py check）")
    ap.add_argument("--note", help="校验单个文件")
    args = ap.parse_args()

    cfg = get_config()
    if args.note:
        targets = [Path(args.note)]
        if not targets[0].is_file():
            print("文件不存在：%s" % args.note)
            return 1
    else:
        mem_dir = Path(cfg["vault"]) / cfg["memory_dir"]
        if not mem_dir.is_dir():
            print("记忆目录不存在：%s（先运行 /save-memory-setup 配置）" % mem_dir)
            return 1
        targets = sorted(mem_dir.glob("*.md"))

    total_err = total_warn = 0
    for path in targets:
        errors, warnings = validate_note(path)
        total_err += len(errors)
        total_warn += len(warnings)
        if errors or warnings:
            print("%s" % path.stem)
            for e in errors:
                print("  ✗ %s" % e)
            for w in warnings:
                print("  ⚠ %s" % w)
    if total_err == 0 and total_warn == 0:
        print("校验通过：%d 篇笔记格式全部合格" % len(targets))
        return 0
    print("校验完成：%d 篇，%d 个 error，%d 个 warning" % (len(targets), total_err, total_warn))
    return 1 if total_err else 0


if __name__ == "__main__":
    sys.exit(main())
