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
    "scoring": {},
}

# 打分配置的默认值 —— 与 v0.4.0 里硬编码的常量逐项相等，老用户升级后分数不变。
SCORING_DEFAULTS = {
    "title_weight": 3.0,
    "tag_weight": 2.0,
    "body_weight": 1.0,
    "body_occ_cap": 3,
    "min_tag_coverage": 0.6,
    "hop_decay": 0.5,
}

# 允许区间。越界的值不夹紧、直接回落到默认 —— 夹紧会让用户以为保存的值生效了。
SCORING_LIMITS = {
    "title_weight": (0.0, 20.0),
    "tag_weight": (0.0, 20.0),
    "body_weight": (0.0, 20.0),
    "body_occ_cap": (1, 20),
    "min_tag_coverage": (0.0, 1.0),
    "hop_decay": (0.0, 1.0),
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


def get_scoring(cfg=None):
    """把配置里的 ``scoring`` 段合并到默认值上，返回最终生效的打分参数。

    三道防线，任何一道不满足都**静默回落默认**（召回不能因为一个坏参数罢工）：

    1. ``scoring`` 不是 dict（写成字符串、列表、null）→ 整段忽略；
    2. 值不是数字（bool 也算非数字，JSON 的 true 会被读成 bool）→ 跳过这一项；
    3. 值超出 SCORING_LIMITS → 跳过这一项，不夹紧。
    """
    source = (cfg if cfg is not None else get_config()).get("scoring")
    result = dict(SCORING_DEFAULTS)
    if not isinstance(source, dict):
        return result
    for key, (low, high) in SCORING_LIMITS.items():
        if key not in source:
            continue
        value = source[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        value = int(value) if key == "body_occ_cap" else float(value)
        if value < low or value > high:   # 越界回落，不夹紧
            continue
        result[key] = value
    return result
