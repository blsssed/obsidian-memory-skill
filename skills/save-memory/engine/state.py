# -*- coding: utf-8 -*-
"""状态目录解析：缓存、日志、锁都落在同一个目录里。

为什么要单独抽出来（而不是继续硬编码 `~/.claude`）：

- 这个引擎要同时给 Claude Code、Codex 等多个宿主用，`~/.claude` 只是其中一个宿主
- 多个宿主并存在同一台机器时，缓存必须能隔离，否则会互相覆盖对方的图谱
- 用户换 vault 时缓存路径不变（这是既有缺陷），至少要让"换宿主"时可预测

优先级：`SAVE_MEMORY_HOME` > `~/.claude`（历史位置，向后兼容）> `~/.save-memory`。

选 `~/.claude` 作为第二优先级是为了零迁移：现有 Claude 用户升级后，缓存和配置
还在原地；只有没装过 Claude Code 的用户（纯 Codex 等）才会落到中性目录。
"""
import os
from pathlib import Path

# 旧版本把状态放在这里；保留它作为兼容位置
LEGACY_DIRNAME = ".claude"
NEUTRAL_DIRNAME = ".save-memory"


def state_home():
    """返回状态目录（不创建）。每次调用都重读环境变量，便于测试与多实例。"""
    override = os.environ.get("SAVE_MEMORY_HOME")
    if override:
        return Path(override).expanduser()
    legacy = Path.home() / LEGACY_DIRNAME
    if legacy.is_dir():
        return legacy
    return Path.home() / NEUTRAL_DIRNAME


def state_path(name):
    """状态目录下的某个文件路径（不创建目录）。"""
    return state_home() / name


def config_candidates():
    """配置文件候选路径，按优先级排列。

    状态目录优先，其次历史位置 —— 这样纯 Codex 用户可以写在
    `~/.save-memory/save-memory.json`，而老用户不必搬家。
    """
    primary = state_home() / "save-memory.json"
    legacy = Path.home() / LEGACY_DIRNAME / "save-memory.json"
    if primary == legacy:
        return [primary]
    return [primary, legacy]
