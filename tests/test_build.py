# -*- coding: utf-8 -*-
"""图谱构建、BOM、同名笔记、record、check 的端到端测试（全部在临时 vault 内）。"""
import argparse
import json
import unittest

from helpers import (
    graph, NOTE_EDGES, NOTE_OK, NOTE_RED_LINK, capture, make_note, temp_vault, write_note
)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_vault(self)

    def test_counts_every_markdown_file(self):
        write_note(self.root, "AI记忆/a.md", NOTE_OK)
        write_note(self.root, "AI记忆/b.md", NOTE_OK)
        write_note(self.root, "用户笔记.md", "# 用户自己的笔记\n")
        self.assertEqual(len(graph.build(verbose=False)), 3)

    def test_same_name_notes_coexist(self):
        """锁住 B 修复：同名笔记不再互相覆盖。"""
        write_note(self.root, "AI记忆/重试策略.md", NOTE_OK)
        write_note(self.root, "AI记忆/子目录/重试策略.md", NOTE_OK)
        g = graph.build(verbose=False)
        self.assertEqual(len(g), 2)
        self.assertEqual(sorted(g.by_name["重试策略"]),
                         ["AI记忆/子目录/重试策略.md", "AI记忆/重试策略.md"])
        self.assertEqual(len(g.resolve("重试策略")), 2)

    def test_resolve_unknown_name_is_empty(self):
        write_note(self.root, "AI记忆/a.md", NOTE_OK)
        self.assertEqual(graph.build(verbose=False).resolve("不存在"), [])

    def test_cache_keyed_by_relative_path(self):
        write_note(self.root, "AI记忆/a.md", NOTE_OK)
        graph.build(verbose=False)
        cache = json.loads(graph.CACHE.read_text(encoding="utf-8"))
        self.assertEqual(list(cache), ["AI记忆/a.md"])

    def test_note_has_relative_path(self):
        write_note(self.root, "AI记忆/深/一层/a.md", NOTE_OK)
        g = graph.build(verbose=False)
        self.assertEqual(g["AI记忆/深/一层/a.md"].rel, "AI记忆/深/一层/a.md")


class BomTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_vault(self)

    def test_bom_note_parses_like_plain(self):
        """锁住 A 修复：BOM 与无 BOM 的同一篇内容，解析结果必须一致。"""
        write_note(self.root, "plain.md", NOTE_OK, bom=False)
        write_note(self.root, "bom.md", NOTE_OK, bom=True)
        g = graph.build(verbose=False)
        plain, bom = g["plain.md"], g["bom.md"]
        self.assertEqual(plain.tags, bom.tags)
        self.assertEqual(plain.edges, bom.edges)
        self.assertEqual(plain.body, bom.body)
        self.assertEqual(plain.tags, ["alpha", "beta"])

    def test_bom_body_does_not_contain_frontmatter(self):
        write_note(self.root, "bom.md", NOTE_OK, bom=True)
        note = graph.build(verbose=False)["bom.md"]
        self.assertNotIn("source:", note.body)
        self.assertTrue(note.body.lstrip().startswith("# 主题"))


class TypedEdgeTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_vault(self)

    def test_typed_edges_survive_bom(self):
        """锁住 A 的连锁影响：BOM 不得把类型化边降级成 wikilink。"""
        write_note(self.root, "a.md", NOTE_EDGES, bom=True)
        note = graph.build(verbose=False)["a.md"]
        types = {edge["type"] for edge in note.edges}
        self.assertEqual(types, {"related", "solved_by"})
        self.assertNotIn("wikilink", types)

    def test_body_wikilinks_become_wikilink_edges(self):
        text = NOTE_OK + "\n见 [[另一篇]]。\n"
        write_note(self.root, "a.md", text)
        note = graph.build(verbose=False)["a.md"]
        self.assertEqual([e for e in note.edges if e["type"] == "wikilink"],
                         [{"to": "另一篇", "type": "wikilink"}])

    def test_code_block_links_ignored(self):
        text = NOTE_OK + "\n```\n[[不该算边]]\n```\n"
        write_note(self.root, "a.md", text)
        note = graph.build(verbose=False)["a.md"]
        self.assertEqual(note.edges, [])


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_vault(self)

    def test_increments_from_zero(self):
        path = write_note(self.root, "AI记忆/a.md", NOTE_OK)
        code, _ = capture(graph.cmd_record, argparse.Namespace(notes=["a"]))
        self.assertEqual(code, 0)
        self.assertIn("recall_count: 1", path.read_text(encoding="utf-8"))

    def test_increments_existing_value(self):
        text = NOTE_OK.replace("updated: 2026-01-02", "updated: 2026-01-02\nrecall_count: 4")
        path = write_note(self.root, "AI记忆/a.md", text)
        capture(graph.cmd_record, argparse.Namespace(notes=["a"]))
        self.assertIn("recall_count: 5", path.read_text(encoding="utf-8"))

    def test_body_untouched(self):
        path = write_note(self.root, "AI记忆/a.md", NOTE_OK)
        before = path.read_text(encoding="utf-8").split("\n---", 1)[1]
        capture(graph.cmd_record, argparse.Namespace(notes=["a"]))
        after = path.read_text(encoding="utf-8").split("\n---", 1)[1]
        self.assertEqual(before, after)

    def test_bom_preserved(self):
        path = write_note(self.root, "AI记忆/a.md", NOTE_OK, bom=True)
        capture(graph.cmd_record, argparse.Namespace(notes=["a"]))
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_bom_note_is_recordable(self):
        """BOM 文件以前连 frontmatter 都认不出来，record 会直接跳过。"""
        path = write_note(self.root, "AI记忆/a.md", NOTE_OK, bom=True)
        code, out = capture(graph.cmd_record, argparse.Namespace(notes=["a"]))
        self.assertEqual(code, 0)
        self.assertNotIn("无 frontmatter", out)
        self.assertIn("recall_count: 1", path.read_text(encoding="utf-8-sig"))

    def test_same_name_notes_all_counted(self):
        p1 = write_note(self.root, "AI记忆/dup.md", NOTE_OK)
        p2 = write_note(self.root, "AI记忆/sub/dup.md", NOTE_OK)
        capture(graph.cmd_record, argparse.Namespace(notes=["dup"]))
        self.assertIn("recall_count: 1", p1.read_text(encoding="utf-8"))
        self.assertIn("recall_count: 1", p2.read_text(encoding="utf-8"))

    def test_unknown_note_returns_1(self):
        code, out = capture(graph.cmd_record, argparse.Namespace(notes=["nope"]))
        self.assertEqual(code, 1)
        self.assertIn("笔记不存在", out)


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_vault(self)

    def test_clean_vault(self):
        write_note(self.root, "AI记忆/a.md", NOTE_OK)
        code, out = capture(graph.cmd_check, argparse.Namespace())
        self.assertEqual(code, 0)
        self.assertIn("链接健康", out)

    def test_red_link_reported(self):
        write_note(self.root, "AI记忆/a.md", NOTE_RED_LINK)
        _, out = capture(graph.cmd_check, argparse.Namespace())
        self.assertIn("红链", out)
        self.assertIn("不存在的笔记", out)

    def test_existing_target_is_not_red(self):
        write_note(self.root, "AI记忆/a.md", NOTE_RED_LINK)
        write_note(self.root, "AI记忆/不存在的笔记.md", NOTE_OK)
        _, out = capture(graph.cmd_check, argparse.Namespace())
        self.assertIn("链接健康", out)
        self.assertNotIn("发现", out)

    def test_cross_directory_link_reported(self):
        write_note(self.root, "AI记忆/a.md", NOTE_RED_LINK)
        write_note(self.root, "用户自己的笔记.md", NOTE_OK)
        # 让 a.md 指向用户目录下的笔记
        note = (self.root / "AI记忆/a.md")
        note.write_text(NOTE_RED_LINK.replace("不存在的笔记", "用户自己的笔记"), encoding="utf-8")
        _, out = capture(graph.cmd_check, argparse.Namespace())
        self.assertIn("跨目录", out)


class DisplayNameTests(unittest.TestCase):
    def test_unique_name_stays_plain(self):
        g = graph.Graph()
        g.add(make_note("唯一"))
        self.assertEqual(graph.display_name(g["唯一.md"], g), "唯一")

    def test_duplicate_name_gets_path(self):
        g = graph.Graph()
        g.add(make_note("x/dup"))
        g.add(make_note("y/dup"))
        self.assertEqual(graph.display_name(g["x/dup.md"], g), "dup（x/dup.md）")


if __name__ == "__main__":
    unittest.main()
