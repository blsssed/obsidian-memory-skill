"""锁住 skill 元数据契约：宿主加载器不容忍 BOM。

背景：Claude Code 读 SKILL.md 时会跳过 UTF-8 BOM，Codex CLI 0.119.0 不会 ——
文件头是 EF BB BF 时它报
    failed to load skill ...: missing YAML frontmatter delimited by ---
于是同一份 skill 在 Claude 侧一直正常，在 Codex 侧其实从未加载成功。
"""

import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_MD = os.path.join(ROOT, "skills", "save-memory", "SKILL.md")
COMMANDS_DIR = os.path.join(ROOT, "commands")

BOM = b"\xef\xbb\xbf"


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


class SkillFrontmatterTest(unittest.TestCase):
    def test_skill_md_has_no_bom(self):
        data = read_bytes(SKILL_MD)
        self.assertFalse(
            data.startswith(BOM),
            "SKILL.md 带 UTF-8 BOM，Codex CLI 会拒绝加载整个 skill",
        )

    def test_skill_md_starts_with_frontmatter(self):
        text = read_bytes(SKILL_MD).decode("utf-8")
        lines = text.splitlines()
        self.assertTrue(lines, "SKILL.md 是空文件")
        self.assertEqual(lines[0], "---", "第一行必须是 ---，前面不能有空行或 BOM")

    def test_skill_md_frontmatter_has_required_fields(self):
        text = read_bytes(SKILL_MD).decode("utf-8")
        lines = text.splitlines()
        self.assertEqual(lines[0], "---")
        try:
            end = lines.index("---", 1)
        except ValueError:
            self.fail("frontmatter 没有结束的 ---")
        front = "\n".join(lines[1:end])
        for key in ("name:", "description:"):
            self.assertIn(key, front, "frontmatter 缺少 " + key)

    def test_commands_have_no_bom(self):
        # commands/*.md 会被原样复制到宿主的命令目录，同样不能带 BOM。
        paths = glob.glob(os.path.join(COMMANDS_DIR, "*.md"))
        if not paths:
            self.skipTest("没有 commands 目录")
        offending = [p for p in paths if read_bytes(p).startswith(BOM)]
        self.assertEqual(offending, [], "这些命令文件带 BOM")


if __name__ == "__main__":
    unittest.main()
