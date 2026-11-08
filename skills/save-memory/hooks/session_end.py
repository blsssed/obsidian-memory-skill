#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SessionEnd hook：会话结束自动总结（轮数过滤 + 嵌套 headless 调用）。

用法（settings.json 注册，无 matcher——所有结束原因都值得总结）：
  py -3 "$HOME/.claude/skills/save-memory/hooks/session_end.py"

行为：
  1. 防递归：检测 SAVE_MEMORY_RUNNING 标记直接退出（hook 环境中 CLAUDECODE=1
     恒定存在，不能单独作标记；嵌套 claude -p 由本脚本设置该标记）
  2. 读 stdin payload（transcript_path / reason）
  3. 统计用户消息轮数：<5 轮静默跳过；≥5 轮嵌套 claude -p 执行提取流程
  4. 日志写 ~/.claude/save-memory.log，每行带 action=skip|done|fail 三态与轮数，可 grep 对账；失败时用 systemMessage 提示用户
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── 配置副本：与 scripts/memory_config.py（canonical）保持同步，改动需三处同步 ──
CONFIG_PATH = Path.home() / ".claude" / "save-memory.json"
DEFAULTS = {"vault": "", "memory_dir": "AI记忆"}

MIN_ROUNDS = 5
TIMEOUT_SEC = 280                      # 复杂会话的总结需要数分钟；settings 里 hook timeout 应设 300
LOG_FILE = Path.home() / ".claude" / "save-memory.log"


def load_config():
    """优先级链副本：环境变量 > 配置文件 > 内置默认（hook 无命令行层）。坏 JSON 静默降级。"""
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
VAULT = CFG["vault"]
# 嵌套 claude.exe 在 Windows 上需要 git-bash；hook 环境可能没有该变量，显式兜底
GIT_BASH = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH", r"D:\develop\Git\bin\bash.exe")


def log(msg):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("%s %s\n" % (datetime.now().isoformat(timespec="seconds"), msg))
    except OSError:
        pass


def count_rounds(transcript_path):
    """统计真实用户消息轮数（排除 tool_result、sidechain、hook 注入的 meta 消息）。"""
    rounds = 0
    with open(transcript_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "user" or rec.get("isSidechain"):
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                if not content.strip():
                    continue
            else:
                texts = [c for c in content or []
                         if isinstance(c, dict) and c.get("type") == "text"]
                if not texts:
                    continue  # tool_result 伪装的 user 记录
            origin = (rec.get("origin") or {}).get("kind")
            if origin and origin != "human":
                continue  # hook 注入的 meta 消息
            rounds += 1
    return rounds


def run_nested(transcript_path):
    env = dict(os.environ)
    env["SAVE_MEMORY_RUNNING"] = "1"
    if os.path.isfile(GIT_BASH):
        env.setdefault("CLAUDE_CODE_GIT_BASH_PATH", GIT_BASH)
    prompt = (
        "严格按照 ~/.claude/skills/save-memory/SKILL.md 的 /save-memory 流程执行"
        "（读取 references/ 下的提取规则、合并规则、笔记模板；输出提取审计表；"
        "遵守封闭白名单与素材解耦）。总结以下 transcript 文件中的对话，"
        "把值得保存的知识写入 vault。transcript 路径：%s" % transcript_path
    )
    cmd = [
        "claude", "-p",
        "--permission-mode", "acceptEdits",
        "--allowedTools", "Read,Write,Grep,Glob",
        "--add-dir", VAULT,
    ]
    # prompt 走 stdin：--add-dir 是可变参数会吞掉位置参数，且 stdin 避开编码问题
    result = subprocess.run(cmd, input=prompt, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace",
                            timeout=TIMEOUT_SEC)
    return result


def main():
    if os.environ.get("SAVE_MEMORY_RUNNING"):
        log("action=skip reason=nested_recursion")  # 嵌套会话的 SessionEnd，防递归
        return

    if not CFG["vault"]:
        log("action=skip reason=vault_not_configured")  # 未配置，先运行 /save-memory-setup
        return

    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        log("action=skip reason=no_valid_payload")  # 无合法 payload（手动运行等）
        return

    transcript_path = payload.get("transcript_path")
    reason = payload.get("reason", "other")
    if not transcript_path or not os.path.isfile(transcript_path):
        log("action=skip reason=no_transcript end_reason=%s" % reason)
        return

    try:
        rounds = count_rounds(transcript_path)
    except OSError as e:
        log("action=fail reason=parse_transcript end_reason=%s err=%s" % (reason, e))
        return

    if rounds < MIN_ROUNDS:
        log("action=skip reason=short_session end_reason=%s rounds=%d min=%d" % (reason, rounds, MIN_ROUNDS))
        return

    try:
        result = run_nested(transcript_path)
        if result.returncode == 0:
            log("action=done end_reason=%s rounds=%d output=%s" % (
                reason, rounds, (result.stdout or "")[:300].replace("\n", " ")))
        else:
            log("action=fail reason=nested_nonzero end_reason=%s rounds=%d rc=%s output=%s" % (
                reason, rounds, result.returncode, (result.stdout or "")[:300].replace("\n", " ")))
            print(json.dumps({"systemMessage": "save-memory 自动总结未成功，详见 ~/.claude/save-memory.log"},
                             ensure_ascii=False))
    except subprocess.TimeoutExpired:
        log("action=fail reason=timeout end_reason=%s rounds=%d timeout=%ds" % (reason, rounds, TIMEOUT_SEC))
    except Exception as e:  # noqa: BLE001 —— hook 里任何异常都不能影响会话退出
        log("action=fail reason=exception end_reason=%s rounds=%d err=%s" % (reason, rounds, e))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
