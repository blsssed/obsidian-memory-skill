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
  4. 日志写 ~/.claude/save-memory.log；失败用 systemMessage 提示用户
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

MIN_ROUNDS = 5
TIMEOUT_SEC = 280                      # 复杂会话的总结需要数分钟；settings 里 hook timeout 应设 300
LOG_FILE = Path.home() / ".claude" / "save-memory.log"
VAULT = os.environ.get("SAVE_MEMORY_VAULT", r"C:\Users\HONOR\Documents\Obsidian Vault")
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
        return  # 嵌套会话的 SessionEnd，防递归直接退出

    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return  # 无合法 payload（手动运行等），静默退出

    transcript_path = payload.get("transcript_path")
    reason = payload.get("reason", "other")
    if not transcript_path or not os.path.isfile(transcript_path):
        log("skip: no transcript (reason=%s)" % reason)
        return

    try:
        rounds = count_rounds(transcript_path)
    except OSError as e:
        log("error: parse transcript failed: %s" % e)
        return

    log("session end (reason=%s, rounds=%d)" % (reason, rounds))
    if rounds < MIN_ROUNDS:
        return  # 短会话，静默跳过

    try:
        result = run_nested(transcript_path)
        log("nested done: rc=%s, output=%s" % (
            result.returncode, (result.stdout or "")[:300].replace("\n", " ")))
        if result.returncode != 0:
            print(json.dumps({"systemMessage": "save-memory 自动总结未成功，详见 ~/.claude/save-memory.log"},
                             ensure_ascii=False))
    except subprocess.TimeoutExpired:
        log("error: nested call timeout (%ds)" % TIMEOUT_SEC)
    except Exception as e:  # noqa: BLE001 —— hook 里任何异常都不能影响会话退出
        log("error: nested call failed: %s" % e)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    main()
