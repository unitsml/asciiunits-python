"""AsciiUnits capture trees and structural models from one Rust runtime."""

from ctypes import CDLL, c_char_p, c_size_t, c_uint32, c_void_p, string_at
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path

__all__ = ["AsciiUnitsError", "ParseError", "ResourceLimitError", "NativeRuntimeError", "parse", "parse_shape", "try_parse"]


class AsciiUnitsError(Exception):
    """Base exception with the native structured error payload."""

    def __init__(self, error):
        self.error = error
        self.category = error["category"]
        super().__init__(error.get("message", self.category))


class ParseError(AsciiUnitsError):
    """Grammar refusal. Offsets are UTF-8 bytes in the original input."""

    @property
    def byte_offset(self):
        return self.error["byte_offset"]


class ResourceLimitError(AsciiUnitsError):
    """The engine reached a parser budget."""

    @property
    def depth(self):
        return self.error["depth"]

    @property
    def max_depth(self):
        return self.error["max_depth"]


class NativeRuntimeError(AsciiUnitsError):
    """The native runtime could not load or complete the request."""


def _runtime_error(message):
    return NativeRuntimeError({"category": "runtime", "message": message})


@lru_cache(maxsize=1)
def _library():
    override = os.environ.get("ASCIIUNITS_CDYLIB")
    try:
        if override:
            path = Path(override).resolve(strict=True)
        else:
            native = Path(__file__).parent / "_native"
            info = json.loads((native / "build-info.json").read_bytes())
            path = native / info["library"]
            if sha256(path.read_bytes()).hexdigest() != info["sha256"]:
                raise _runtime_error("Packaged native library failed checksum verification")
        lib = CDLL(str(path))
        lib.asciiunits_abi_version.argtypes = []
        lib.asciiunits_abi_version.restype = c_uint32
        if lib.asciiunits_abi_version() != 1:
            raise _runtime_error("Unsupported AsciiUnits C ABI version")
        lib.asciiunits_parse_json_v1.argtypes = [c_char_p, c_size_t, c_uint32]
        lib.asciiunits_parse_json_v1.restype = c_void_p
        lib.asciiunits_free_json_v1.argtypes = [c_void_p]
        lib.asciiunits_free_json_v1.restype = None
        return lib
    except (OSError, AttributeError, KeyError, ValueError) as error:
        raise _runtime_error(f"Could not load AsciiUnits runtime: {error}") from error


def _parse(text, mode):
    if not isinstance(text, str):
        raise TypeError("AsciiUnits input must be str")
    source = text.encode("utf-8")
    lib = _library()
    pointer = lib.asciiunits_parse_json_v1(source, len(source), mode)
    if not pointer:
        raise _runtime_error("Native runtime returned a null response")
    try:
        reply = json.loads(string_at(pointer))
    except (UnicodeError, ValueError) as error:
        raise _runtime_error("Native runtime returned invalid JSON") from error
    finally:
        lib.asciiunits_free_json_v1(pointer)
    if not isinstance(reply, dict) or reply.get("abi_version") != 1:
        raise _runtime_error("Native runtime returned an invalid ABI envelope")
    if reply.get("ok") is True and "value" in reply:
        return reply["value"]
    error = reply.get("error")
    if reply.get("ok") is not False or not isinstance(error, dict) or "category" not in error:
        raise _runtime_error("Native runtime returned an invalid error envelope")
    category = error["category"]
    if category == "syntax":
        raise ParseError(error)
    if category in ("recursion_limit", "call_depth_limit"):
        raise ResourceLimitError(error)
    raise NativeRuntimeError(error)


def parse_shape(text):
    """Return the complete edition-2 capture tree, including slice metadata."""
    return _parse(text, 0)


def parse(text):
    """Return the producer's structural model as JSON-compatible values."""
    return _parse(text, 1)


def try_parse(text):
    """Return None for a syntax refusal."""
    try:
        return parse(text)
    except ParseError:
        return None
