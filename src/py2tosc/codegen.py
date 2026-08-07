"""Turn a layout back into the Python that would build it.

The rest of the library reads a `.tosc` into objects and writes objects back
out. This writes them out as source instead, which is what you want when the
layout already exists and the thing you are short of is a script:

```python
print(py2tosc.to_python(py2tosc.load("mixer.tosc")))
```

The output is flat -- one variable per control, then the tree, then the
bindings -- rather than one nested expression. A nested one reads better for
five controls and is unusable at a hundred and forty, and local bindings
address their destination by identity, so the destination has to be something
the generated code can name.

What comes back is equal to what went in, with one documented exception: a
property the file leaves out but the control's type provides a default for
will be present in the rebuild. That is how `Control` works -- it applies the
type's defaults before anything else -- and it accounts for ten combinations
across the corpus, all of them properties added to the format after the file
was written.
"""

from __future__ import annotations

import keyword
import math
from dataclasses import fields
from typing import TYPE_CHECKING, Any

from .control import Control
from .defaults import default_values_for, defaults_for
from .messages import (
    LocalMessage,
    MidiCommand,
    MidiValue,
    Partial,
    Trigger,
    Value,
)
from .properties import Color, Frame, Property, to_camel, to_snake

if TYPE_CHECKING:  # pragma: no cover
    from .document import Document

__all__ = ["to_python"]

#: How many leading fields of each helper read better without their keyword.
#: `Trigger("x", "RISE")` says as much as the long form and takes a line
#: rather than four.
_POSITIONAL = {
    Trigger: 2,
    Partial: 3,
    MidiValue: 2,
    MidiCommand: 1,
    Value: 1,
}

#: Names the generated module already uses, which no control may take.
_RESERVED = frozenset(
    {"py2tosc", "doc", "Control", "Value", "Partial", "Trigger", "MidiCommand"}
    | {"Color"}
    | {"MidiValue", "OscMessage", "MidiMessage", "LocalMessage", "GamepadMessage"}
)


def _literal(value: Any) -> str:
    """Source for one property value.

    Frames and colours go out as plain tuples, which is what every constructor
    in the package accepts and what a reader would have typed.
    """
    if isinstance(value, Color):
        # Not a bare tuple: `to_color` reads one of those as 0-255 whenever a
        # component exceeds 1, which silently rescales the out-of-range
        # colours the corpus deliberately preserves.
        return "Color(" + ", ".join(_number(v) for v in value) + ")"
    if isinstance(value, Frame):
        return "(" + ", ".join(_number(v) for v in value) + ")"
    if isinstance(value, bool) or value is None:
        return repr(value)
    if isinstance(value, float):
        return _number(value)
    return repr(value)


def _number(value: float) -> str:
    """Whole floats as integers, so a frame reads as `(0, 0, 320, 480)`.

    Anything else keeps every digit it had: rounding for looks would change
    the file.

    Infinities and not-a-number are spelled out. `repr` gives `inf` and `nan`,
    which are names Python does not define, so the generated module would fail
    to run -- and the corpus does hold both.
    """
    number = float(value)
    if math.isnan(number):
        return 'float("nan")'
    if math.isinf(number):
        return 'float("-inf")' if number < 0 else 'float("inf")'
    return str(int(number)) if number.is_integer() else repr(value)


def _call(name: str, positional: list[str], keywords: list[tuple[str, str]]) -> str:
    parts = positional + [f"{key}={value}" for key, value in keywords]
    return f"{name}({', '.join(parts)})"


def _dataclass_source(obj: Any) -> str:
    """One dataclass as a call, with anything left at its default omitted."""
    blank = type(obj)()
    lead = _POSITIONAL.get(type(obj), 0)

    positional: list[str] = []
    keywords: list[tuple[str, str]] = []
    for index, field in enumerate(fields(obj)):
        mine = getattr(obj, field.name)
        if isinstance(mine, list):
            if [_dataclass_source(v) for v in mine] == [
                _dataclass_source(v) for v in getattr(blank, field.name)
            ]:
                continue
            rendered = "[" + ", ".join(_dataclass_source(v) for v in mine) + "]"
        elif isinstance(mine, (Trigger, Partial, MidiValue, MidiCommand, Value)):
            if _dataclass_source(mine) == _dataclass_source(getattr(blank, field.name)):
                continue
            rendered = _dataclass_source(mine)
        else:
            mine = str(mine) if hasattr(mine, "value") else mine
            other = getattr(blank, field.name)
            other = str(other) if hasattr(other, "value") else other
            if mine == other and index >= lead:
                continue
            rendered = _literal(mine)

        if index < lead and not keywords:
            positional.append(rendered)
        else:
            keywords.append((field.name, rendered))

    return _call(type(obj).__name__, positional, keywords)


def _identifier(control: Control, taken: set[str]) -> str:
    """A variable name for a control, from its own name where that can work."""
    raw = str(control.get("name") or "")
    cleaned = "".join(c if c.isalnum() else "_" for c in raw).strip("_")
    if not cleaned or cleaned[0].isdigit() or keyword.iskeyword(cleaned):
        cleaned = f"{control.control_type.value.lower()}_{cleaned}".strip("_")
    if cleaned in _RESERVED:
        cleaned = f"{cleaned}_"

    candidate, suffix = cleaned, 2
    while candidate in taken:
        candidate, suffix = f"{cleaned}_{suffix}", suffix + 1
    taken.add(candidate)
    return candidate


def _properties(control: Control) -> tuple[list[tuple[str, str]], list[str]]:
    """Split a control's properties into constructor keywords and `set` calls.

    A key survives the round trip through `to_snake` and back for everything
    the format defines, so those go in the call. A custom key need not --
    `CustomProperty` comes back as `customProperty` -- and those are set by
    their exact name afterwards.
    """
    defaults = defaults_for(control.control_type)
    keywords: list[tuple[str, str]] = []
    calls: list[str] = []

    for key in sorted(control.properties):
        prop = control.properties[key]
        if key in defaults and defaults[key] == prop.value:
            continue
        if to_camel(to_snake(key)) == key:
            keywords.append((to_snake(key), _literal(prop.value)))
        else:
            declared = Property(key, prop.value).type
            kind = "" if declared is prop.type else f", type={prop.type.value!r}"
            calls.append(f".set({key!r}, {_literal(prop.value)}{kind})")
    return keywords, calls


def _values(control: Control) -> str | None:
    """The control's values, if they are not the ones its type already has."""
    expected = [
        Value(key, default=default)
        for key, default in default_values_for(control.control_type)
    ]
    if [_dataclass_source(v) for v in control.values] == [
        _dataclass_source(v) for v in expected
    ]:
        return None
    return "[" + ", ".join(_dataclass_source(v) for v in control.values) + "]"


def _defers(control: Control) -> bool:
    """Whether this control's messages have to be written after the tree."""
    return any(isinstance(m, LocalMessage) for m in control.messages)


def _control_source(control: Control, variable: str) -> list[str]:
    """The statements that build one control, without its children."""
    keywords, calls = _properties(control)
    values = _values(control)
    if values is not None:
        keywords.append(("values", values))

    # Messages go inline unless one of them is local, in which case the whole
    # list is deferred: a local binding has to wait for its destination to
    # exist, and splitting the list would reorder it. The file keeps them in
    # the order they are written.
    if control.messages and not _defers(control):
        keywords.append(
            (
                "messages",
                "[" + ", ".join(_dataclass_source(m) for m in control.messages) + "]",
            )
        )

    factory = control.control_type.value.lower()
    lines = [
        f"{variable} = py2tosc.{factory}("
        if keywords
        else f"{variable} = py2tosc.{factory}()"
    ]
    if keywords:
        lines += [f"    {key}={value}," for key, value in keywords]
        lines.append(")")
    lines += [f"{variable}{call}" for call in calls]
    return lines


def to_python(target: Document | Control, *, variable: str = "doc") -> str:
    """Write the Python that rebuilds a layout.

    Args:
        target: A [`Document`][py2tosc.Document] or a
            [`Control`][py2tosc.Control] to rebuild.
        variable: The name to bind the finished document to.

    Returns:
        A module's worth of source. Running it produces the same layout, with
        fresh node ids and any type defaults the original file omitted.
    """
    root = target if isinstance(target, Control) else target.root
    version = None if isinstance(target, Control) else target.version

    names: dict[str, str] = {}
    taken: set[str] = set()
    body: list[str] = []
    wiring: list[str] = []

    def emit(control: Control, parent: str | None) -> None:
        variable_name = _identifier(control, taken)
        names[control.id] = variable_name
        body.extend(_control_source(control, variable_name))
        if parent is not None:
            body.append(f"{parent}.add({variable_name})")
        body.append("")
        for child in control.children:
            emit(child, variable_name)

    emit(root, None)

    # Local bindings come last: they name their destination, which may be
    # anywhere in the tree, including somewhere not yet built.
    for control in root.walk():
        if not _defers(control):
            continue
        for message in control.messages:
            source = _dataclass_source(message)
            if isinstance(message, LocalMessage):
                target_name = names.get(message.dst_id)
                if target_name is not None:
                    source = source.replace(
                        f"dst_id={message.dst_id!r}", f"dst_id={target_name}.id"
                    )
            wiring.append(f"{names[control.id]}.messages.append({source})")

    header = [
        '"""Generated by py2tosc. Edit freely: this is ordinary Python."""',
        "",
        "import py2tosc",
        "from py2tosc import (",
        "    Color,",
        "    GamepadMessage,",
        "    LocalMessage,",
        "    MidiCommand,",
        "    MidiMessage,",
        "    MidiValue,",
        "    OscMessage,",
        "    Partial,",
        "    Trigger,",
        "    Value,",
        ")",
        "",
        "",
    ]
    lines = header + body
    if wiring:
        lines += [
            "# every binding that addresses another control by identity",
            *wiring,
            "",
        ]
    if version is not None:
        lines.append(
            f"{variable} = py2tosc.Document(root={names[root.id]}, version={version!r})"
        )
    else:
        lines.append(f"{variable} = {names[root.id]}")
    return "\n".join(lines) + "\n"
