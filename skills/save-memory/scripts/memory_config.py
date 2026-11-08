#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""save-memory 配置加载 —— canonical 实现。

优先级链：命令行 --vault 参数 > SAVE_MEMORY_VAULT 环境变量 >
~/.claude/save-memory.json > 内置默认。逐层赋值、有值才覆盖；
配置文件缺失或 JSON 损坏时静默降级到下一层（本模块服务于
hook/召回路径，不能因配置坏一行而罢工）。

注意：hooks/session_end.py 与 hooks/session_start.py 内联了本模块的
同款副本（hook 进程不依赖 sys.path，自包含优先）。改动本文件时需
同步三处。
"""
import json
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude" / "save-memory.json"

# 内置默认（最低优先级；他人安装后应运行 /save-memory-setup 覆盖）
DEFAULTS = {
    "vault": r"C:\Users\HONOR\Documents\Obsidian Vault",
    "memory_dir": "AI记忆",
    "snippet_dir": "snippets",
}


def load_file_config():
    """读配置文件；缺失或损坏返回 {}，调用方自然落到下一层。"""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if v}


def get_config(cli_vault=None):
    """返回完整配置 dict；cli_vault 为命令行 --vault 透传值（最高优先级）。"""
    cfg = dict(DEFAULTS)                            # ④ 内置默认
    cfg.update(load_file_config())                  # ③ 配置文件：有值才覆盖
    env_vault = os.environ.get("SAVE_MEMORY_VAULT") # ② 环境变量
    if env_vault:
        cfg["vault"] = env_vault
    if cli_vault:                                   # ① 命令行参数
        cfg["vault"] = cli_vault
    return cfg
