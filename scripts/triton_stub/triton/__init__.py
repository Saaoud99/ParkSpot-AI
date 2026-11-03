"""Import-time stand-in for `triton` on machines without CUDA (macOS, CPU-only Linux).

The `sam3` package imports Triton GPU kernels at module import even though
the image-segmentation path never calls them (they are used by the video
tracker and perf helpers). This stub only makes `import triton` succeed;
calling any kernel raises so nothing silently runs wrong. It is added to
sys.path by scripts/local_sam_server.py only when the real Triton is absent.
"""
from __future__ import annotations

from . import language  # noqa: F401

__version__ = "0.0.0-stub"


class _Kernel:
    def __init__(self, fn):
        self.fn = fn
        self.__name__ = getattr(fn, "__name__", "kernel")
        self.__doc__ = getattr(fn, "__doc__", None)

    def __getitem__(self, _grid):
        return self

    def __call__(self, *_a, **_k):
        raise RuntimeError("Triton GPU kernels are unavailable on this machine (triton stub).")


def jit(fn=None, **_kw):
    if fn is None:
        return lambda f: _Kernel(f)
    return _Kernel(fn)


def autotune(*_a, **_k):
    return lambda f: f


def heuristics(*_a, **_k):
    return lambda f: f


def cdiv(a, b):
    return -(-a // b)


def next_power_of_2(n: int) -> int:
    return 1 << (int(n) - 1).bit_length()


class Config:
    def __init__(self, *a, **k):
        self.args, self.kwargs = a, k
