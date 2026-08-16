"""The exception types this package raises.

Two rules decide what belongs here. An error the library defines is one a
caller might reasonably want to catch as a group -- "this file is not a
layout", "this document will not save" -- and those inherit from
`Py2toscError`. An error caused by passing a bad argument stays on the
builtins, because `ValueError` and `TypeError` already say exactly that and
wrapping them would only make ordinary Python code harder to read.
"""

from __future__ import annotations

__all__ = ["FormatError", "Py2toscError"]


class Py2toscError(Exception):
    """Base class for every error py2tosc defines.

    Catching this catches anything the library treats as its own failure,
    without also catching the `ValueError` a caller gets for handing a
    function a bad argument.
    """


class FormatError(Py2toscError, ValueError):
    """Raised when input cannot be read as a TouchOSC layout.

    Reading a layout can fail in three unrelated ways -- the bytes are not
    XML, a `.tosc` stream will not decompress, or the XML parses but is not a
    `lexml` root holding one node -- and each of those used to reach the
    caller as a different type from a different module. None of them was a
    py2tosc type, so no single `except` clause could express "that file is not
    a layout", which is the only distinction most callers want.

    It also inherits `ValueError`, which is what `load` and `loads` have always
    documented themselves as raising. Code written against that contract keeps
    working, and code that wants the narrower type can ask for it.
    """
