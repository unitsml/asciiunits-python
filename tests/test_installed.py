from ctypes import string_at
import json
from pathlib import Path
import unittest

import asciiunits


class InstalledRuntimeTests(unittest.TestCase):
    def test_corpus_raw_models_and_syntax(self):
        corpus = json.loads(Path(__file__).with_name("corpus.json").read_bytes())
        models = iter(json.loads(Path(__file__).with_name("models.json").read_bytes()))
        self.assertEqual(len(corpus["cases"]), 143)
        count = 0
        for row in corpus["cases"]:
            text = row["input"]
            with self.subTest(text=text):
                if row["kind"] == "accept":
                    model = next(models)
                    self.assertEqual(model["input"], text)
                    self.assertEqual(asciiunits.parse_shape(text), row["parsanol_tree"])
                    self.assertEqual(asciiunits.parse(text), model["model"])
                    count += 1
                else:
                    self.assertEqual(row["kind"], "reject")
                    with self.assertRaises(asciiunits.ParseError):
                        asciiunits.parse_shape(text)
        self.assertEqual(count, 92)
        self.assertEqual(list(models), [])

    def test_typed_refusal_budget_and_reuse(self):
        with self.assertRaises(asciiunits.ParseError) as refusal:
            asciiunits.parse("")
        self.assertEqual(refusal.exception.byte_offset, 0)
        self.assertIsNone(asciiunits.try_parse(""))
        for call in (asciiunits.parse, asciiunits.parse_shape, asciiunits.try_parse):
            with self.assertRaises(asciiunits.ResourceLimitError) as resource:
                call("m/" * 256 + "m")
            self.assertEqual(resource.exception.category, "recursion_limit")
            self.assertGreaterEqual(resource.exception.depth, resource.exception.max_depth)
        self.assertEqual(asciiunits.parse("m"), {"unitName": "m"})

    def test_c_abi_rejects_bad_buffers_and_modes(self):
        library = asciiunits._library()
        for data, size, mode in [(None, 0, 0), (b"\xff", 1, 0), (b"m", 1, 42)]:
            pointer = library.asciiunits_parse_json_v1(data, size, mode)
            self.assertTrue(pointer)
            try:
                reply = json.loads(string_at(pointer))
                self.assertFalse(reply["ok"])
                self.assertEqual(reply["error"]["category"], "invalid_argument")
            finally:
                library.asciiunits_free_json_v1(pointer)
        self.assertEqual(asciiunits.parse("m"), {"unitName": "m"})


if __name__ == "__main__":
    unittest.main()
