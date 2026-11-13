# -*- coding: utf-8 -*-
"""格式校验（validate.py）测试：frontmatter / 文件名 / 编码。"""
import os
import unittest

from helpers import NOTE_OK, temp_dir, validate, write_note


class ValidateNoteTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_dir(self)

    def check(self, text, name="a.md", bom=False):
        path = write_note(self.root, name, text, bom=bom)
        return validate.validate_note(path)

    def test_clean_note_has_no_errors(self):
        errors, _ = self.check(NOTE_OK)
        self.assertEqual(errors, [])

    def test_missing_frontmatter(self):
        errors, _ = self.check("# 只有标题\n")
        self.assertTrue(any("frontmatter" in e for e in errors))

    def test_missing_required_field(self):
        errors, _ = self.check(NOTE_OK.replace("source: claude-code\n", ""))
        self.assertTrue(any("source" in e for e in errors))

    def test_too_few_tags(self):
        errors, _ = self.check(NOTE_OK.replace("tags: [alpha, beta]", "tags: [alpha]"))
        self.assertTrue(any("tags" in e for e in errors))

    def test_too_many_tags(self):
        errors, _ = self.check(NOTE_OK.replace("tags: [alpha, beta]", "tags: [a, b, c, d, e, f]"))
        self.assertTrue(any("tags" in e for e in errors))

    def test_bom_is_an_error(self):
        errors, _ = self.check(NOTE_OK, bom=True)
        self.assertTrue(any("BOM" in e for e in errors))

    def test_overlong_name(self):
        errors, _ = self.check(NOTE_OK, name="x" * 60 + ".md")
        self.assertTrue(any("50" in e for e in errors))

    def test_numeric_prefix_name(self):
        errors, _ = self.check(NOTE_OK, name="2026-11-08笔记.md")
        self.assertTrue(any("数字" in e for e in errors))

    def test_generic_word_warns_but_passes(self):
        errors, warnings = self.check(NOTE_OK, name="笔记.md")
        self.assertEqual(errors, [])
        self.assertTrue(any("泛词" in w for w in warnings))

    def test_recall_count_must_be_integer(self):
        text = NOTE_OK.replace("updated: 2026-01-02",
                               "updated: 2026-01-02\nrecall_count: abc")
        errors, _ = self.check(text)
        self.assertTrue(any("recall_count" in e for e in errors))

    @unittest.skipIf(os.name == "nt", "Windows 无法创建含非法字符的文件名")
    def test_illegal_characters_in_name(self):
        errors, _ = self.check(NOTE_OK, name="a:b.md")
        self.assertTrue(any("非法字符" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
