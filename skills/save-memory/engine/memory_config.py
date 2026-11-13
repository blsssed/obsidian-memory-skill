#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""save-memory 配置加载 —— canonical 实现。

优先级链：命令行 --vault 参数 > SAVE_MEMORY_VAULT 环境变量 >
配置文件 > 内置默认。逐层赋值、有值才覆盖；配置文件缺失或损坏时
静默降级到下一层（召回路径不能因配置坏一行而罢工）。

配置文件位置由 state.py 的 config_candidates() 决定：状态目录优先，
历史位置 `~/.claude/save-memory.json` 作为兼容回退。
"""
import json
import os
from pathlib import Path

from state import config_candidates

# 内置默认（最低优先级；vault 留空 = 未配置，工具会提示运行 /save-memory-setup）
DEFAULTS = {
    "vault": "",
    "memory_dir": "AI记忆",
    "snippet_dir": "snippets",
}


def load_file_config():
    """按候选顺序读配置文件；全部缺失或损坏时返回 {}，调用方落到下一层。"""
    for path in config_candidates():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if v}
    return {}


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
