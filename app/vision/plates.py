from __future__ import annotations

import re

_CONFUSION = {"O": "0", "Q": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"}


def normalize_plate(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _apply_confusion(s: str) -> str:
    return "".join(_CONFUSION.get(c, c) for c in s)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (0 if ca == cb else 1)))
        prev = cur
    return prev[-1]


def plates_match(a: str | None, b: str | None) -> bool:
    na, nb = normalize_plate(a), normalize_plate(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return _levenshtein(_apply_confusion(na), _apply_confusion(nb)) <= 1
