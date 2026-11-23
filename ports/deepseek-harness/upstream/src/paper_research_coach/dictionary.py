"""Local word and phrase lookup using the enabled macOS dictionaries."""

import ctypes as C
import sys
from functools import lru_cache

_UTF8 = 0x08000100


class _Range(C.Structure):
    _fields_ = [("location", C.c_long), ("length", C.c_long)]


@lru_cache(maxsize=1)
def _frameworks():
    cf = C.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cs = C.CDLL("/System/Library/Frameworks/CoreServices.framework/CoreServices")
    cf.CFStringCreateWithCString.argtypes = [C.c_void_p, C.c_char_p, C.c_uint32]
    cf.CFStringCreateWithCString.restype = C.c_void_p
    cf.CFStringGetLength.argtypes = [C.c_void_p]
    cf.CFStringGetLength.restype = C.c_long
    cf.CFStringGetCString.argtypes = [C.c_void_p, C.c_char_p, C.c_long, C.c_uint32]
    cf.CFStringGetCString.restype = C.c_bool
    cf.CFRelease.argtypes = [C.c_void_p]
    cf.CFRelease.restype = None
    cs.DCSCopyTextDefinition.argtypes = [C.c_void_p, C.c_void_p, _Range]
    cs.DCSCopyTextDefinition.restype = C.c_void_p
    return cf, cs


def lookup(word: str) -> dict:
    word = " ".join(word.split())
    if not word or len(word) > 80 or "\0" in word:
        raise ValueError("请选择一个词或短语（最多 80 个字符）。")
    if sys.platform != "darwin":
        return {"available": False, "definition": None}
    try:
        cf, cs = _frameworks()
    except (OSError, AttributeError):
        return {"available": False, "definition": None}
    term = cf.CFStringCreateWithCString(None, word.encode(), _UTF8)
    if not term:
        return {"available": True, "definition": None}
    try:
        definition = cs.DCSCopyTextDefinition(None, term, _Range(0, cf.CFStringGetLength(term)))
        if not definition:
            return {"available": True, "definition": None}
        try:
            buffer = C.create_string_buffer(cf.CFStringGetLength(definition) * 4 + 1)
            found = cf.CFStringGetCString(definition, buffer, len(buffer), _UTF8)
            return {"available": True, "definition": buffer.value.decode() if found else None}
        finally:
            cf.CFRelease(definition)
    finally:
        cf.CFRelease(term)
