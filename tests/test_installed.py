from ctypes import string_at
from hashlib import sha256
from importlib.resources import files
import json
import os
from pathlib import Path
import unittest

import asciiunits


def pinned_corpus():
    """The shared corpus from unitsml/asciiunits-testsuite at the pinned commit.

    CI checks the testsuite out and sets ASCIIUNITS_TESTSUITE to it. The bytes
    must match tests/corpus-pin.json.
    """
    pin = json.loads(Path(__file__).with_name("corpus-pin.json").read_bytes())
    root = os.environ.get("ASCIIUNITS_TESTSUITE")
    if not root:
        raise RuntimeError(f"set ASCIIUNITS_TESTSUITE to a {pin['repository']} checkout at {pin['commit']}")
    data = (Path(root) / pin["path"]).read_bytes()
    if sha256(data).hexdigest() != pin["sha256"]:
        raise RuntimeError(f"{pin['path']} in {root} does not match the pinned sha256")
    corpus = json.loads(data)
    if corpus["artifact_checksum"] != pin["artifact_checksum"]:
        raise RuntimeError("corpus artifact checksum does not match the pin")
    return corpus


class InstalledRuntimeTests(unittest.TestCase):
    def test_corpus_raw_models_and_syntax(self):
        corpus = pinned_corpus()
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
        self.assertEqual(info["native_source_commit"], "e6758b85166f2aa3862a81ffb6133c0786478836")
        self.assertEqual(info["parsanol"], "8f8afd878a3e91b83e43c2005459bc9dc4927851")
        self.assertEqual(info["cargo_lock_sha256"], "5efbbefeb95fba8730ad6421e13aa5c408f60d4684221445c45112f19f250b15")
        notices = json.loads(native.joinpath("licenses", "manifest.json").read_bytes())
        parsanol = [row for row in notices if row["name"] == "parsanol"]
        self.assertEqual([row["version"] for row in parsanol], ["0.20.14"])
        self.assertTrue(parsanol[0]["notices"])
        for path in parsanol[0]["notices"]:
            self.assertTrue(native.joinpath("licenses", *path.replace("\\", "/").split("/")).is_file())

if __name__ == "__main__":
    unittest.main()
