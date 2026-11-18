# AsciiUnits for Python

`parse_shape(text)` exposes the sealed edition-2 Parsanol captures.
`parse(text)` returns the AsciiUnits structural model as JSON-compatible
values. `try_parse(text)` returns `None` for a grammar refusal.
`parse_model(text)` returns the typed `Asciiunits::Model::Document` as its
portable JSON. The Rust core builds it with the LutaML models generated from
the Ruby model, so it holds the same captures as the Ruby gem's
`Asciiunits.parse_model`. Exact integers, such as a slice's offset, are
decimal strings. `to_portable_json(model)` writes that JSON as the Rust core
does. `ParseError` includes original UTF-8 byte offsets. `ResourceLimitError`
carries the native depth and budget. The platform wheel supplies the Rust
library and verifies its digest before loading it.

Build from source with the sibling Rust package's locked native build, an
`ASCIIUNITS_NATIVE` library path, and `ASCIIUNITS_NATIVE_RECEIPT` pointing
to the accompanying build-info JSON and dependency licenses directory.
`ASCIIUNITS_CDYLIB` can select a separately installed compatible library.


To build a host wheel with setuptools and wheel already installed:

```sh
python scripts/build-wheel.py --rust-source ../asciiunits-rs \
  --target-dir ./build/native-target --wheel-dir ./dist
```

The tests replay the shared corpus from unitsml/asciiunits-testsuite at the
commit in `tests/corpus-pin.json`, and check its bytes against the pin. Set
`ASCIIUNITS_TESTSUITE` to a checkout of that commit before running them.
