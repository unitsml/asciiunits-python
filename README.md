# AsciiUnits for Python

`parse_shape(text)` exposes the sealed edition-2 Parsanol captures.
`parse(text)` returns the AsciiUnits structural model as JSON-compatible
values. `try_parse(text)` returns `None` for a grammar refusal.
`ParseError` includes original UTF-8 byte offsets. `ResourceLimitError`
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
