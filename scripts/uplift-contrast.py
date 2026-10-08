#!/usr/bin/env python3
"""Uplift low-opacity Tailwind color utilities so UI items read clearly.

The Clearis design system leaned on very low opacity modifiers for muted text,
borders, dividers and washes (e.g. text-muted-foreground/50, border-border/20).
This raises them by a consistent amount while preserving the relative hierarchy.

Usage:  python uplift-contrast.py [--apply]
"""
import re
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "apps" / "web" / "src"

# Explicit per-token maps keep the hierarchy monotonic and avoid over-darkening.
# Values must stay on Tailwind's default opacity scale (multiples of 5) or the
# generated class is silently dropped.
MAP = {
    "muted-foreground": {10: 30, 15: 35, 20: 40, 25: 45, 30: 55, 35: 60, 40: 65, 45: 70, 50: 75, 60: 85, 70: 90},
    "foreground": {50: 70, 60: 80, 70: 85, 80: 90, 90: 95},
    "border": {10: 30, 20: 40, 30: 50, 40: 60, 50: 70, 60: 80, 70: 85, 80: 90},
    "muted": {10: 30, 15: 35, 20: 40, 25: 45, 30: 55, 40: 60, 50: 70, 60: 75},
    "primary": {5: 15, 10: 20, 15: 30, 20: 35, 30: 45, 40: 55, 50: 65, 55: 75, 60: 75, 70: 80, 80: 90, 90: 95},
    "accent": {40: 60, 50: 70, 60: 75},
    "destructive": {10: 25, 15: 35, 20: 40, 30: 50, 50: 70, 80: 90},
    "success": {15: 35, 30: 50, 40: 60, 55: 70},
    "warning": {20: 40, 30: 50, 40: 60, 60: 75},
    "ring": {10: 30, 30: 50},
    "secondary": {30: 45, 50: 60, 60: 75},
    "background": {50: 70, 80: 90, 85: 90, 95: 95},
    "card": {60: 75, 80: 90},
}

TOKENS = sorted(
    set(MAP) | {"muted-foreground", "primary-foreground", "secondary-foreground",
                "accent-foreground", "destructive-foreground", "card-foreground",
                "error", "info", "chart-1", "chart-2", "chart-3", "chart-4", "chart-5", "chart-6"},
    key=len, reverse=True,
)
TYPES = ["bg", "text", "border", "divide", "ring", "from", "to", "via", "fill", "stroke",
         "placeholder", "outline", "decoration", "caret", "accent"]

UTIL = re.compile(
    r"(?P<pre>(?:[a-z-]+:)*)"
    r"(?P<type>" + "|".join(TYPES) + r")"
    r"-(?P<token>" + "|".join(TOKENS) + r")/"
    r"(?P<num>\d+)"
)

INLINE = re.compile(
    r"hsl\(var\(--(?P<token>muted-foreground|foreground|border|muted|primary|secondary)\)\s*/\s*0?\.(?P<frac>\d+)\)"
)


def snap5(n: int) -> int:
    return max(5, min(100, round(n / 5) * 5))


def bump(token: str, num: int) -> int:
    if num <= 0:
        return num
    table = MAP.get(token)
    if table and num in table:
        return table[num]
    # Fallback: lift by ~15 points but never past 90 for text-ish tones.
    return snap5(min(90, num + 15))


def fix_util(m: re.Match) -> str:
    new = bump(m.group("token"), int(m.group("num")))
    return f"{m.group('pre')}{m.group('type')}-{m.group('token')}/{new}"


def fix_inline(m: re.Match) -> str:
    val = float(f"0.{m.group('frac')}")
    # 0.4 -> 0.75 etc. Lift by +35 points, capped at 0.95
    new = min(0.95, val + 0.35)
    return f"hsl(var(--{m.group('token')}) / {new:g})"


def process(path: Path) -> int:
    text = path.read_text()
    orig = text
    text, n1 = UTIL.subn(fix_util, text)
    text, n2 = INLINE.subn(fix_inline, text)
    n = n1 + n2
    if n and text != orig:
        if APPLY:
            path.write_text(text)
        print(f"{n:4d}  {path.relative_to(SRC)}")
    return n


if __name__ == "__main__":
    APPLY = "--apply" in sys.argv
    total = 0
    for p in sorted(SRC.rglob("*")):
        if p.suffix in (".tsx", ".ts") and p.is_file():
            total += process(p)
    print(f"\n{'APPLIED' if APPLY else 'DRY RUN'}: {total} replacements")
