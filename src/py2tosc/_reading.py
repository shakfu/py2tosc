"""Shared plumbing for reading a layout out of JSON.

Two dialects are read here: [`json_codec`][py2tosc.json_codec], which is the
node tree exactly as the file holds it, and [`ui_json`][py2tosc.ui_json], which
describes a layout for the combinators to build. They have almost nothing in
common except how they should fail -- an object where an object belongs, a list
where a list belongs, a key nothing reads refused with the nearest spelling,
and every message naming the node it gave up on. Keeping that here means one
voice across both rather than two sets of nearly identical messages.
"""

from __future__ import annotations

import difflib
from collections.abc import Collection
from typing import Any

from .errors import FormatError

__all__ = ["as_list", "as_object", "check_keys", "describe"]


def describe(value: Any) -> str:
    """What a reader wants to be told they wrote instead."""
    return {
        dict: "an object",
        list: "a list",
        str: "a string",
        bool: "a boolean",
        int: "a number",
        float: "a number",
        type(None): "null",
    }.get(type(value), type(value).__name__)


def as_object(data: Any, where: str) -> dict[str, Any]:
    """Insist on an object, since most of what is read is one."""
    if not isinstance(data, dict):
        raise FormatError(f"{where} should be an object, found {describe(data)}")
    return data


def as_list(data: Any, where: str) -> list[Any]:
    """Insist on a list, so a mistyped one is a message and not a strange loop."""
    if not isinstance(data, list):
        raise FormatError(f"{where} should be a list, found {describe(data)}")
    return data


def check_keys(entry: dict[str, Any], allowed: Collection[str], where: str) -> None:
    """Refuse a key nobody will read.

    Ignoring one is the worst failure either dialect has: a `childs` that
    silently drops a subtree looks exactly like a layout that came back right.
    """
    for key in entry:
        if key in allowed:
            continue
        # Two suggestions rather than one: `gpa` is exactly as close to `gap`
        # as it is to `pad`, and picking between them on a tie-break nobody
        # can see is worse than offering both.
        near = difflib.get_close_matches(key, sorted(allowed), n=2)
        hint = (
            "did you mean " + " or ".join(repr(match) for match in near) + "?"
            if near
            else "expected one of " + ", ".join(sorted(allowed))
        )
        raise FormatError(f"{where}: unknown key {key!r}; {hint}")
