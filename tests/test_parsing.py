# -*- coding: utf-8 -*-
"""frontmatter / 双链 / 代码段剥离的解析测试。"""
import unittest

from helpers import graph


class SplitFrontmatterTests(unittest.TestCase):
    def test_normal(self):
        fm, body = graph.split_frontmatter("---\na: 1\n---\n# 标题\n")
        self.assertEqual(fm, "a: 1")
        self.assertEqual(body, "# 标题\n")

    def test_missing(self):
        fm, body = graph.split_frontmatter("# 标题\n")
        self.assertEqual(fm, "")
        self.assertEqual(body, "# 标题\n")

    def test_unclosed(self):
        fm, body = graph.split_frontmatter("---\na: 1\n正文")
        self.assertEqual(fm, "")
        self.assertEqual(body, "---\na: 1\n正文")

    def test_bom_text_no_longer_matters(self):
        """BOM 是旧 bug 的现场：未剥 BOM 的字符串不以 --- 开头。

        这条锁住"为什么必须用 utf-8-sig 读"，防止有人把读取改回 utf-8。
        """
        raw = "\ufeff---\na: 1\n---\n正文"
        self.assertFalse(raw.startswith("---"))
        # 剥掉 BOM 之后就正常了
        self.assertEqual(graph.split_frontmatter(raw.lstrip("\ufeff"))[0], "a: 1")


class ParseFrontmatterTests(unittest.TestCase):
    def test_scalar(self):
        fm = graph.parse_frontmatter("source: claude-code\nupdated: 2026-01-01")
        self.assertEqual(fm["source"], "claude-code")
        self.assertEqual(fm["updated"], "2026-01-01")

    def test_inline_list_kept_as_string(self):
        """内联列表在 parse_frontmatter 里保留原样，由 parse_tags 负责拆。"""
        fm = graph.parse_frontmatter("tags: [a, b, c]")
        self.assertEqual(fm["tags"], "[a, b, c]")
        self.assertEqual(graph.parse_tags(fm["tags"]), ["a", "b", "c"])

    def test_multiline_list(self):
        fm = graph.parse_frontmatter("tags:\n  - a\n  - b\nsource: x")
        self.assertEqual(fm["tags"], ["a", "b"])
        self.assertEqual(fm["source"], "x")

    def test_comment_and_blank_ignored(self):
        fm = graph.parse_frontmatter("# 注释\n\nsource: x")
        self.assertEqual(fm, {"source": "x"})


class ParseTagsTests(unittest.TestCase):
    def test_none(self):
        self.assertEqual(graph.parse_tags(None), [])

    def test_quoted(self):
        self.assertEqual(graph.parse_tags('["a", "b"]'), ["a", "b"])

    def test_plain_list_value(self):
        self.assertEqual(graph.parse_tags(["a", "b"]), ["a", "b"])

    def test_whitespace_and_empty_items(self):
        self.assertEqual(graph.parse_tags("[ a , , b ]"), ["a", "b"])


class LinkNamesTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(graph.link_names("见 [[目标]]"), ["目标"])

    def test_alias(self):
        self.assertEqual(graph.link_names("[[目标|显示文本]]"), ["目标"])

    def test_heading(self):
        self.assertEqual(graph.link_names("[[目标#小节]]"), ["目标"])

    def test_embed_excluded(self):
        """![[嵌入]] 是嵌入不是链接，不能算成边。"""
        self.assertEqual(graph.link_names("![[嵌入]]"), [])

    def test_list_value(self):
        self.assertEqual(graph.link_names(["[[a]]", "[[b]]"]), ["a", "b"])

    def test_none(self):
        self.assertEqual(graph.link_names(None), [])


class StripCodeTests(unittest.TestCase):
    def test_fenced_block(self):
        text = "```\n[[x]]\n```\n[[y]]"
        stripped = graph.strip_code(text)
        self.assertNotIn("[[x]]", stripped)
        self.assertIn("[[y]]", stripped)

    def test_unclosed_fence(self):
        text = "```\n[[x]]\n没有闭合"
        self.assertNotIn("[[x]]", graph.strip_code(text))

    def test_inline_code(self):
        stripped = graph.strip_code("`[[x]]` 和 [[y]]")
        self.assertNotIn("[[x]]", stripped)
        self.assertIn("[[y]]", stripped)


if __name__ == "__main__":
    unittest.main()
