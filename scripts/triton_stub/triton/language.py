"""Minimal `triton.language` surface so kernel *definitions* import."""
from __future__ import annotations


class constexpr:  # used only in annotations / defaults
    def __init__(self, value=None):
        self.value = value

    def __class_getitem__(cls, _item):
        return cls


class dtype:
    def __init__(self, name):
        self.name = name


int1, int8, int16, int32, int64 = (dtype(n) for n in ("int1", "int8", "int16", "int32", "int64"))
uint8, uint16, uint32, uint64 = (dtype(n) for n in ("uint8", "uint16", "uint32", "uint64"))
float16, bfloat16, float32, float64 = (dtype(n) for n in ("float16", "bfloat16", "float32", "float64"))


def __getattr__(name):  # program_id, load, store, arange, … resolve lazily and fail only if called
    def _unavailable(*_a, **_k):
        raise RuntimeError(f"triton.language.{name} is unavailable (triton stub).")
    return _unavailable
