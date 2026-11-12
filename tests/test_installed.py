from ctypes import string_at
from importlib.resources import files
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


    def test_build_receipt_and_parsanol_notice(self):
        native = files("asciiunits").joinpath("_native")
        info = json.loads(native.joinpath("build-info.json").read_bytes())
        self.assertEqual(info["native_source_commit"], "1f771caef878b9d383a5f29b02f434b8b614b780")
        self.assertEqual(info["parsanol"], "5206a33b5417b4ecd3a601930461ed2967c871e7")
        self.assertEqual(info["cargo_lock_sha256"], "714aad1f4ff4ef003ea791fff8bff062edb76f966fb6a699979b2bf28b01ee3b")
        notices = json.loads(native.joinpath("licenses", "manifest.json").read_bytes())
        parsanol = [row for row in notices if row["name"] == "parsanol"]
        self.assertEqual([row["version"] for row in parsanol], ["0.20.14"])
        self.assertTrue(parsanol[0]["notices"])
        for path in parsanol[0]["notices"]:
            self.assertTrue(native.joinpath("licenses", *path.replace("\\", "/").split("/")).is_file())

if __name__ == "__main__":
    unittest.main()
