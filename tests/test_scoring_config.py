# -*- coding: utf-8 -*-
"""打分配置测试：scoring 段的外置、坏值回落，以及参数真的影响召回排名。

分两层：

- 纯函数层直接测 ``memory_config.get_scoring``，快且能覆盖各种坏输入；
- 子进程层跑真实的 ``mem.py params`` / ``mem.py recall``，证明「改了配置 →
  引擎行为变了」，而不是只有那个函数自己自说自话。

子进程层刻意不 import 引擎模块：reload 会把 W_TITLE 之类的模块级常量改掉，
污染同一进程里后面的用例（顺序一变就飘）。
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ENGINE, write_note

import memory_config


def run_engine(args, home, vault=None, cwd=None):
    """在隔离的状态目录里跑一次引擎，返回 (退出码, stdout, stderr)。"""
    env = dict(os.environ)
    env["SAVE_MEMORY_HOME"] = str(home)
    env.pop("SAVE_MEMORY_VAULT", None)      # 别让外部环境变量盖掉测试用的 vault
    cmd = [sys.executable, str(ENGINE / "mem.py")]
    if vault is not None:
        # --vault 是顶层可选参数，argparse 要求它出现在子命令之前
        cmd += ["--vault", str(vault)]
    cmd += list(args)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=str(cwd or ENGINE),
    )
    return proc.returncode, proc.stdout, proc.stderr


class ScoringDefaultsTests(unittest.TestCase):
    def test_missing_section_equals_v040_constants(self):
        """没有 scoring 段时，六个参数必须逐项等于 v0.4.0 的硬编码常量。"""
        self.assertEqual(
            memory_config.get_scoring({}),
            {
                "title_weight": 3.0,
                "tag_weight": 2.0,
                "body_weight": 1.0,
                "body_occ_cap": 3,
                "min_tag_coverage": 0.6,
                "hop_decay": 0.5,
            },
        )

    def test_empty_section_equals_defaults(self):
        self.assertEqual(
            memory_config.get_scoring({"scoring": {}}),
            memory_config.get_scoring({}),
        )

    def test_returns_copy_not_shared_dict(self):
        """调用方改动返回值不能污染默认值 —— 否则一次面板保存就能改掉全进程默认。"""
        first = memory_config.get_scoring({})
        first["title_weight"] = 99.0
        self.assertEqual(memory_config.get_scoring({})["title_weight"], 3.0)


class ScoringOverrideTests(unittest.TestCase):
    def test_partial_override_keeps_other_defaults(self):
        scoring = memory_config.get_scoring({"scoring": {"title_weight": 5.0}})
        self.assertEqual(scoring["title_weight"], 5.0)
        self.assertEqual(scoring["tag_weight"], 2.0)

    def test_integer_is_accepted_as_float(self):
        self.assertEqual(
            memory_config.get_scoring({"scoring": {"title_weight": 4}})["title_weight"],
            4.0,
        )

    def test_body_occ_cap_is_int(self):
        value = memory_config.get_scoring({"scoring": {"body_occ_cap": 5}})["body_occ_cap"]
        self.assertEqual(value, 5)
        self.assertIsInstance(value, int)

    def test_full_override(self):
        scoring = memory_config.get_scoring(
            {
                "scoring": {
                    "title_weight": 0,
                    "tag_weight": 0,
                    "body_weight": 1,
                    "body_occ_cap": 1,
                    "min_tag_coverage": 1.0,
                    "hop_decay": 0.0,
                }
            }
        )
        self.assertEqual(scoring["title_weight"], 0.0)
        self.assertEqual(scoring["min_tag_coverage"], 1.0)
        self.assertEqual(scoring["hop_decay"], 0.0)


class ScoringRejectsBadValuesTests(unittest.TestCase):
    """坏值一律回落默认，且**不夹紧** —— 夹紧会让用户以为存进去的 100 生效了。"""

    def assert_falls_back(self, scoring_section, key):
        scoring = memory_config.get_scoring({"scoring": scoring_section})
        self.assertEqual(scoring[key], memory_config.SCORING_DEFAULTS[key])

    def test_string_value(self):
        self.assert_falls_back({"title_weight": "5.0"}, "title_weight")

    def test_bool_value(self):
        self.assert_falls_back({"title_weight": True}, "title_weight")

    def test_null_value(self):
        self.assert_falls_back({"title_weight": None}, "title_weight")

    def test_negative_out_of_range(self):
        self.assert_falls_back({"title_weight": -1}, "title_weight")

    def test_too_large_not_clamped(self):
        self.assert_falls_back({"title_weight": 1000}, "title_weight")

    def test_coverage_above_one(self):
        self.assert_falls_back({"min_tag_coverage": 1.5}, "min_tag_coverage")

    def test_body_occ_cap_below_one(self):
        self.assert_falls_back({"body_occ_cap": 0}, "body_occ_cap")

    def test_section_not_a_dict(self):
        for value in ("oops", [1, 2], None, 7):
            self.assertEqual(
                memory_config.get_scoring({"scoring": value}),
                memory_config.get_scoring({}),
            )

    def test_unknown_key_ignored(self):
        scoring = memory_config.get_scoring({"scoring": {"nope": 1}})
        self.assertNotIn("nope", scoring)


class ParamsCommandTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.home = Path(self._tmp.name) / "state"
        self.home.mkdir()

    def write_config(self, payload):
        (self.home / "save-memory.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    def test_params_works_without_vault(self):
        """没配 vault 也要能看参数 —— 面板第一次打开时通常还没配。"""
        code, out, err = run_engine(["params"], self.home)
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        self.assertEqual(payload["effective"]["title_weight"], 3.0)
        self.assertIn("limits", payload)
        self.assertIn("defaults", payload)

    def test_params_reports_effective_values(self):
        self.write_config({"vault": "", "scoring": {"title_weight": 7.5, "hop_decay": 0.2}})
        code, out, err = run_engine(["params"], self.home)
        self.assertEqual(code, 0, err)
        effective = json.loads(out)["effective"]
        self.assertEqual(effective["title_weight"], 7.5)
        self.assertEqual(effective["hop_decay"], 0.2)
        self.assertEqual(effective["tag_weight"], 2.0)

    def test_params_limits_match_defaults(self):
        code, out, _ = run_engine(["params"], self.home)
        payload = json.loads(out)
        for key, value in payload["defaults"].items():
            low, high = payload["limits"][key]["min"], payload["limits"][key]["max"]
            self.assertLessEqual(low, value)
            self.assertGreaterEqual(high, value)


class ScoringAffectsRecallTests(unittest.TestCase):
    """端到端：改了 title_weight，同一批笔记的排名必须跟着变。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.home = root / "state"
        self.home.mkdir()
        vault = root / "vault"
        (vault / "AI记忆").mkdir(parents=True)
        self.vault = vault

        # 标题命中：文件名（引擎的 title = 文件 stem）含关键词，正文里没有
        write_note(
            vault,
            "AI记忆/重试策略.md",
            "---\ntags: []\nsource: test\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n"
            "# 备忘\n\n这里没有那个关键词。\n",
        )
        # 正文命中：文件名不含关键词，正文里出现一次
        write_note(
            vault,
            "AI记忆/另一篇.md",
            "---\ntags: []\nsource: test\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n"
            "# 另一篇\n\n只有正文提到重试一次。\n",
        )

    def write_config(self, scoring):
        (self.home / "save-memory.json").write_text(
            json.dumps({"vault": str(self.vault), "scoring": scoring}, ensure_ascii=False),
            encoding="utf-8",
        )

    def recall_order(self):
        code, out, err = run_engine(["recall", "重试"], self.home, vault=self.vault)
        self.assertEqual(code, 0, err)
        titles = []
        for line in out.splitlines():
            # 标题行形如：## ★1.00 另一篇  [tags: alpha]
            match = re.match(r"^##\s+★[\d.]+\s+(.*)$", line)
            if not match:
                continue
            titles.append(match.group(1).split("  [tags:")[0].strip())
        return titles

    def test_default_prefers_title_hit(self):
        self.write_config({})
        self.assertEqual(self.recall_order()[0], "重试策略")

    def test_zero_title_weight_flips_order(self):
        """title_weight 归零、body_weight 保持 1：正文命中的那篇必须反超。"""
        self.write_config({"title_weight": 0, "body_weight": 1})
        self.assertEqual(self.recall_order()[0], "另一篇")

    def test_bad_value_is_ignored_not_clamped(self):
        """写个越界的 1000 进去，行为必须与默认一致（回落，而不是放大标题分）。"""
        self.write_config({"title_weight": 1000})
        self.assertEqual(self.recall_order()[0], "重试策略")


if __name__ == "__main__":
    unittest.main()
