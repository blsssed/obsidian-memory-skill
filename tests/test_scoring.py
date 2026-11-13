# -*- coding: utf-8 -*-
"""打分逻辑测试：覆盖率、关键词边界、种子分、图谱扩展。"""
import unittest

from helpers import graph, make_note


class CoverageTests(unittest.TestCase):
    def test_exact_is_one(self):
        self.assertEqual(graph.coverage("note", "note"), 1.0)

    def test_case_insensitive(self):
        self.assertEqual(graph.coverage("MCP", "mcp"), 1.0)

    def test_shorter_inside_longer(self):
        self.assertAlmostEqual(graph.coverage("note", "notes"), 0.8)

    def test_no_overlap(self):
        self.assertEqual(graph.coverage("alpha", "beta"), 0.0)

    def test_weak_containment_below_threshold(self):
        """锁住 D 修复：这两组的覆盖率必须低于阈值，否则弱包含会累乘成噪音。"""
        self.assertLess(graph.coverage("env", "environment"), graph.MIN_TAG_COVERAGE)
        self.assertLess(graph.coverage("api", "apikey"), graph.MIN_TAG_COVERAGE)


class KeywordHitTests(unittest.TestCase):
    """锁住 C 修复：纯 ASCII 关键词必须按词边界匹配。"""

    def test_ascii_not_matched_inside_word(self):
        self.assertEqual(graph.count_hits("ai", "Email 发送流程"), 0)
        self.assertEqual(graph.count_hits("ai", "wait_exponential"), 0)
        self.assertEqual(graph.count_hits("ai", "max_retries"), 0)
        self.assertEqual(graph.count_hits("go", "good morning"), 0)
        self.assertEqual(graph.count_hits("ui", "build 界面"), 0)

    def test_ascii_standalone_still_hits(self):
        self.assertEqual(graph.count_hits("ai", "用 AI 写代码"), 1)
        self.assertEqual(graph.count_hits("mcp", "MCP server"), 1)

    def test_ascii_adjacent_to_cjk_still_hits(self):
        """中文紧贴英文时词边界仍应成立：否则 "用429重试" 会漏检。"""
        self.assertEqual(graph.count_hits("429", "用429重试"), 1)

    def test_cjk_uses_substring(self):
        self.assertEqual(graph.count_hits("重试", "限流重试经验"), 1)
        self.assertEqual(graph.count_hits("重试", "限流重试与重试策略"), 2)

    def test_phrase_with_space(self):
        self.assertEqual(graph.count_hits("rate limit", "遇到 rate limit 时"), 1)

    def test_empty_inputs(self):
        self.assertEqual(graph.count_hits("", "abc"), 0)
        self.assertEqual(graph.count_hits("a", ""), 0)

    def test_underscore_is_word_internal(self):
        """`_` 算词内字符：max_retries 是一个整体标识符，不被 retries 切碎。

        这是有意选择（跟编程语境一致），不是遗漏。
        """
        self.assertEqual(graph.count_hits("retries", "max_retries"), 0)
        self.assertEqual(graph.count_hits("max_retries", "max_retries"), 1)


class SeedScoreTests(unittest.TestCase):
    def test_weak_tag_ignored(self):
        note = make_note("a", tags=["environment"])
        self.assertEqual(graph.seed_scores({note.rel: note}, ["env"]), {})

    def test_strong_tag_kept(self):
        note = make_note("a", tags=["notes"])
        self.assertIn(note.rel, graph.seed_scores({note.rel: note}, ["note"]))

    def test_title_hit_awards_full_weight(self):
        note = make_note("重试策略")
        scores = graph.seed_scores({note.rel: note}, ["重试"])
        self.assertEqual(scores[note.rel], graph.W_TITLE)

    def test_body_occurrences_are_capped(self):
        note = make_note("x", body="重试 " * 10)
        scores = graph.seed_scores({note.rel: note}, ["重试"])
        self.assertEqual(scores[note.rel], graph.W_BODY * graph.BODY_OCC_CAP)

    def test_no_hit_produces_no_entry(self):
        note = make_note("a", tags=["zzz"], body="无关内容")
        self.assertEqual(graph.seed_scores({note.rel: note}, ["重试"]), {})


class HopScoreTests(unittest.TestCase):
    def test_decay_and_edge_coefficient(self):
        graph_ = graph.Graph()
        a = make_note("a", edges=[("b", "solved_by")])
        b = make_note("b")
        graph_.add(a)
        graph_.add(b)
        result = graph.hop_scores(graph_, {"a.md": 2.0}, depth=1)
        self.assertAlmostEqual(result["b.md"]["score"],
                               2.0 * graph.HOP_DECAY * graph.EDGE_COEF["solved_by"])
        self.assertEqual(result["b.md"]["via"], "solved_by")
        self.assertEqual(result["b.md"]["hop"], 1)

    def test_stale_edge_is_discounted(self):
        graph_ = graph.Graph()
        a = make_note("a", edges=[("b", "superseded_by")])
        b = make_note("b")
        graph_.add(a)
        graph_.add(b)
        result = graph.hop_scores(graph_, {"a.md": 1.0})
        self.assertAlmostEqual(result["b.md"]["score"], graph.EDGE_COEF["superseded_by"] * graph.HOP_DECAY)
        self.assertIn(result["b.md"]["via"], graph.STALE_EDGES)

    def test_stale_is_weaker_than_related(self):
        self.assertLess(graph.EDGE_COEF["superseded_by"], graph.EDGE_COEF["related"])

    def test_same_name_notes_both_reached(self):
        """锁住 B 修复：一个 [[名字]] 要扩到所有同名笔记。"""
        graph_ = graph.Graph()
        a = make_note("a", edges=[("dup", "wikilink")])
        d1 = make_note("x/dup")
        d2 = make_note("y/dup")
        for note in (a, d1, d2):
            graph_.add(note)
        result = graph.hop_scores(graph_, {"a.md": 1.0})
        self.assertIn("x/dup.md", result)
        self.assertIn("y/dup.md", result)

    def test_seed_not_scored_as_neighbour(self):
        graph_ = graph.Graph()
        a = make_note("a", edges=[("b", "related")])
        b = make_note("b", edges=[("a", "related")])
        graph_.add(a)
        graph_.add(b)
        result = graph.hop_scores(graph_, {"a.md": 1.0, "b.md": 1.0})
        self.assertEqual(result["a.md"]["via"], None)
        self.assertEqual(result["b.md"]["via"], None)

    def test_hop_count(self):
        graph_ = graph.Graph()
        a = make_note("a", edges=[("b", "related")])
        b = make_note("b", edges=[("c", "related")])
        c = make_note("c")
        for note in (a, b, c):
            graph_.add(note)
        two = graph.hop_scores(graph_, {"a.md": 1.0}, depth=2)
        one = graph.hop_scores(graph_, {"a.md": 1.0}, depth=1)
        self.assertNotIn("c.md", one)
        self.assertIn("c.md", two)


class SynonymTests(unittest.TestCase):
    def test_expands_known_group(self):
        pool = graph.expand_synonyms(["429"])
        self.assertIn("限流", pool)
        self.assertIn("rate limit", pool)

    def test_original_keyword_kept_first(self):
        pool = graph.expand_synonyms(["重试"])
        self.assertEqual(pool[0], "重试")

    def test_drops_single_char(self):
        self.assertEqual(graph.expand_synonyms(["a"]), [])


if __name__ == "__main__":
    unittest.main()
