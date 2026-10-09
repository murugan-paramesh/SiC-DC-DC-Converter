"""Minimal helpers for writing KiCad 7 s-expression files."""
import uuid as _uuid


def uid():
    return str(_uuid.uuid4())


def f(v):
    """Format a number the way KiCad does (no trailing zeros)."""
    if isinstance(v, int):
        return str(v)
    s = f"{v:.4f}".rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s


def q(s):
    """Quote a string for s-expressions."""
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def font(size=1.27, hide=False, justify=None, bold=False):
    s = f"(effects (font (size {f(size)} {f(size)})"
    if bold:
        s += " bold"
    s += ")"
    if justify:
        s += f" (justify {justify})"
    if hide:
        s += " hide"
    return s + ")"
