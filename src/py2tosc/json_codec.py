"""Reading and writing a layout as JSON.

The `.tosc` XML is the format TouchOSC defines. This is the same tree written
as JSON, for the two cases the XML serves badly: emitting a layout from
something that is not Python, and diffing one without reading through CDATA.
It is a second encoding of the model rather than a second model, so anything
`codec` can read can be written here and read back, and the file that comes out
the other side is byte for byte the one that went in.

```python
import py2tosc
from py2tosc import json_codec

doc = py2tosc.load("mixer.tosc")
text = json_codec.to_json(doc)
assert json_codec.from_json(text).dumps() == doc.dumps()
```

Three decisions carry that guarantee, and each of them is a decision rather
than a convenience:

- **Every property is written with the type tag the file stores it under.**
  `properties.infer_type` guesses well enough for code being written by hand,
  but a `gridX` is an element count on a GRID and a switch on an XY, and a
  custom property has no table to consult at all. A tag that is read rather
  than inferred cannot get either wrong.

- **A field is omitted only when it is identically at its default.** `0.0 ==
  False` in Python, so a plain equality test would drop the `x` default of
  every fader and write it back as `false`. See `_same`.

- **Type defaults are not applied when decoding.** `Control()` fills in the
  property set for its type; here the file is the source of truth instead,
  exactly as it is in `codec._read_control`.

Two conventions meet in the middle of a node, and the split is deliberate.
Property keys are the file's own camelCase, because they are the format's
vocabulary and translating them would make the JSON depend on a regex round
tripping perfectly. Everything on a binding is the `snake_case` name of the
field on the dataclass behind it, because those are this library's names and
nothing in the file is spelled that way.

Two things are deliberately absent from the format. Property order is not
recorded, because `codec` writes properties sorted by key and the order in a
file is therefore not information. Neither is the distinction between `15` and
`15.0`, because `codec._num` renders both as `15`.

One thing is deliberately present. A colour component of `inf` is not a
hypothetical -- `o_custom.xml` in the corpus holds ninety of them, written by
some TouchOSC build and carried faithfully by the XML codec ever since. JSON
has no such number, and `Infinity` is a Python extension that most other
parsers reject, so a non-finite value is written as `{"$float": "inf"}`. An
object never appears where a number belongs otherwise, which makes the escape
unambiguous without the reader having to know what type it was expecting.
"""

from __future__ import annotations

import difflib
import json
import math
from collections.abc import Collection
from dataclasses import MISSING, fields, is_dataclass
from enum import Enum
from typing import Any

from .control import Control
from .document import Document
from .enums import ControlType, PropertyType
from .errors import FormatError
from .messages import (
    GamepadMessage,
    LocalMessage,
    Message,
    MidiCommand,
    MidiMessage,
    MidiValue,
    OscMessage,
    Partial,
    Trigger,
    Value,
)
from .properties import Color, Frame, Property

__all__ = ["FORMAT", "SCHEMA", "decode", "encode", "from_json", "to_json"]

#: What the envelope calls itself, so a file can be told from any other JSON.
FORMAT = "py2tosc.layout"

#: The envelope version. Bumped only by a change that a reader written against
#: the previous one cannot parse; adding an optional key is not one of those.
SCHEMA = 1

#: The one-key object a non-finite number is written as, since JSON has no
#: notation for one and `Infinity` is not JSON.
NON_FINITE = "$float"

#: Every key a node may carry. Anything else is a mistake worth reporting: a
#: `childs` that is quietly ignored loses a subtree without saying so.
_NODE_KEYS = frozenset(
    {"type", "id", "includes", "properties", "values", "messages", "children"}
)

#: Every key the envelope may carry.
_ENVELOPE_KEYS = frozenset({"format", "schema", "lexml", "root"})

#: The `kind` tag on a message, and the class behind it.
_MESSAGES: dict[str, type[Any]] = {
    "osc": OscMessage,
    "midi": MidiMessage,
    "local": LocalMessage,
    "gamepad": GamepadMessage,
}

_KINDS: dict[type[Any], str] = {cls: kind for kind, cls in _MESSAGES.items()}

#: Fields written even when they are at their default, because they say what
#: the thing is rather than how it is configured. Without them a slot at its
#: defaults is an empty object, which decodes correctly and reads as a hole.
_IDENTIFYING: dict[type[Any], tuple[str, ...]] = {
    Value: ("key",),
    MidiValue: ("type",),
}

#: The dataclasses nested inside a message, by the field holding them. `values`
#: is a `MidiValue` here and a `Value` on a node; the two never meet, because a
#: node's values are read by `_read_value` and never reach this table.
_NESTED: dict[str, type[Any]] = {
    "triggers": Trigger,
    "path": Partial,
    "arguments": Partial,
    "message": MidiCommand,
    "values": MidiValue,
}


# -- writing ----------------------------------------------------------------


def _plain(value: Any) -> Any:
    """A scalar as JSON holds it: an enum by the spelling it stores, and an
    infinity or a NaN by the escape, since JSON has neither."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float) and not math.isfinite(value):
        return {NON_FINITE: repr(value)}
    return value


def _same(value: Any, default: Any) -> bool:
    """Whether a field still holds its default, without confusing `0` and `False`.

    `0.0 == False` is true in Python, and a fader whose `x` default comes back
    as `false` rather than `0` is a different file. Numbers otherwise compare
    across int and float, since that distinction cannot reach the output.
    """
    if isinstance(value, bool) != isinstance(default, bool):
        return False
    return bool(value == default)


def _thin(obj: Any) -> dict[str, Any]:
    """A dataclass as a dict, minus every field still at its default.

    Nested dataclasses and lists of them are thinned too, and compared in their
    thinned form -- which is exact, since two instances thin alike only when
    every field matches. The fields in `_IDENTIFYING` are the exception and are
    always written.

    Args:
        obj: The dataclass instance to write.

    Returns:
        The fields worth writing, in declaration order.
    """
    keep = _IDENTIFYING.get(type(obj), ())
    out: dict[str, Any] = {}
    for field in fields(obj):
        value = _reduce(getattr(obj, field.name))

        if field.default_factory is not MISSING:
            default = _reduce(field.default_factory())
        else:
            # MISSING when the field has no default at all, which is right: the
            # sentinel equals nothing, so such a field is always written.
            default = _reduce(field.default)

        if field.name not in keep and _same(value, default):
            continue
        out[field.name] = value
    return out


def _reduce(value: Any) -> Any:
    """A field value reduced to JSON: enums to strings, dataclasses to dicts."""
    if isinstance(value, list):
        return [_reduce(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _thin(value)
    return _plain(value)


def _property(prop: Property) -> list[Any]:
    """One property, as `[type tag, value]`.

    The tag is the format's own: `s`, `b`, `i`, `f`, `r` or `c`. Frames and
    colours are the two composite types, and become four-item lists.
    """
    value = prop.value
    if isinstance(value, (Frame, Color)):
        return [prop.type.value, [_plain(item) for item in value]]
    return [prop.type.value, _plain(value)]


def _message(message: Message) -> dict[str, Any]:
    """One binding, tagged with the kind of binding it is."""
    kind = _KINDS.get(type(message))
    if kind is None:
        raise TypeError(f"{type(message).__name__} is not a message type")
    return {"kind": kind, **_thin(message)}


def encode(control: Control) -> dict[str, Any]:
    """Write one control and everything under it as JSON-ready data.

    Args:
        control: The control to encode. Its children come with it.

    Returns:
        A dict of nothing but JSON types.
    """
    node: dict[str, Any] = {
        "type": control.control_type.value,
        "id": control.id,
    }
    # The root of a version 6 document carries an empty <includes/>, and so do
    # a handful of nodes beneath it. `codec` writes the root's from the format
    # version, but a child's exists only because the file said so.
    if getattr(control, "_has_includes", False):
        node["includes"] = True

    node["properties"] = {
        key: _property(control.properties[key]) for key in sorted(control.properties)
    }
    if control.values:
        node["values"] = [_thin(value) for value in control.values]
    if control.messages:
        node["messages"] = [_message(message) for message in control.messages]
    if control.children:
        node["children"] = [encode(child) for child in control.children]
    return node


def _leaf(value: Any) -> bool:
    """Whether a value reads as a single thing. The escape counts as a number."""
    if isinstance(value, dict):
        return len(value) == 1 and NON_FINITE in value
    return not isinstance(value, list)


def _inline(value: Any) -> bool:
    """Whether a value is small enough in shape to render on one line.

    `json.dumps(indent=2)` puts every item of every list on its own line, which
    turns `["c", [0, 0, 0, 1]]` into seven lines and a layout into something
    nobody can read a diff of. The rule here is structural rather than a width
    limit, so the output is the same wherever it sits: a property pair, a frame
    and a colour stay on one line, and a node, a binding and a list of them do
    not.
    """
    if _leaf(value):
        return True
    if isinstance(value, list):
        return all(
            _leaf(item)
            or (isinstance(item, list) and all(_leaf(part) for part in item))
            for item in value
        )
    return all(_leaf(item) for item in value.values())


def _render(value: Any, indent: int, level: int = 0) -> str:
    """The document as text, one line per thing worth diffing on its own."""
    if _inline(value):
        return json.dumps(value, separators=(", ", ": "), allow_nan=False)

    pad, inner = " " * (indent * level), " " * (indent * (level + 1))
    if isinstance(value, list):
        items = [inner + _render(item, indent, level + 1) for item in value]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    items = [
        f"{inner}{json.dumps(key)}: {_render(item, indent, level + 1)}"
        for key, item in value.items()
    ]
    return "{\n" + ",\n".join(items) + "\n" + pad + "}"


def to_json(document: Document, *, indent: int | None = 2) -> str:
    """Serialize a document to JSON text.

    Args:
        document: The layout to write.
        indent: Spaces per level, or `None` for the single-line form.

    Returns:
        The complete document. The indented form ends in a newline, as the
        pretty XML export does.

    Raises:
        ValueError: If the layout holds a number JSON cannot represent. Only a
            non-finite one can be, and those are escaped rather than refused,
            so this is a guard rather than something a real layout meets.
    """
    data = {
        "format": FORMAT,
        "schema": SCHEMA,
        "lexml": document.version,
        "root": encode(document.root),
    }
    if indent is None:
        return json.dumps(data, separators=(",", ":"), allow_nan=False)
    return _render(data, indent) + "\n"


# -- reading ----------------------------------------------------------------


def _expand(value: Any, where: str) -> Any:
    """The inverse of `_plain`, applied to a leaf and anything inside it.

    Only the one-key escape object is treated as a number. Everything else is
    passed through, so a label whose text is the word `inf` stays a string.
    """
    if isinstance(value, list):
        return [_expand(item, where) for item in value]
    if isinstance(value, dict):
        if len(value) == 1 and NON_FINITE in value:
            try:
                return float(value[NON_FINITE])
            except (TypeError, ValueError):
                raise FormatError(
                    f"{where}: {value[NON_FINITE]!r} is not an infinity or a NaN"
                ) from None
        return {key: _expand(item, where) for key, item in value.items()}
    return value


def _object(data: Any, where: str) -> dict[str, Any]:
    """Insist on an object, since everything below reads one."""
    if not isinstance(data, dict):
        raise FormatError(f"{where} should be an object, found {_describe(data)}")
    return data


def _sequence(data: Any, where: str) -> list[Any]:
    """Insist on a list, so a mistyped one is a message and not a strange loop."""
    if not isinstance(data, list):
        raise FormatError(f"{where} should be a list, found {_describe(data)}")
    return data


def _describe(value: Any) -> str:
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


def _keys(entry: dict[str, Any], allowed: Collection[str], where: str) -> None:
    """Refuse a key nobody will read.

    Ignoring one is the worst failure this format has: a `childs` that silently
    drops a subtree looks exactly like a layout that came back right. The
    envelope carries a `schema` for the case where a key is genuinely new.
    """
    for key in entry:
        if key in allowed:
            continue
        near = difflib.get_close_matches(key, sorted(allowed), n=1)
        hint = (
            f"did you mean {near[0]!r}?"
            if near
            else "expected one of " + ", ".join(sorted(allowed))
        )
        raise FormatError(f"{where}: unknown key {key!r}; {hint}")


def _instance(cls: type[Any], data: Any, where: str) -> Any:
    """Build one dataclass from an object, once its keys are known to be real."""
    entry = _object(data, where)
    _keys(entry, {field.name for field in fields(cls)}, where)
    return cls(**_expand(entry, where))


def _read_property(key: str, entry: Any, where: str) -> Property:
    """One `[type tag, value]` pair back into a typed property."""
    if not isinstance(entry, list) or len(entry) != 2:
        raise FormatError(
            f"{where}: a property is a [type, value] pair, found {_describe(entry)}"
        )
    tag, value = entry
    try:
        kind = PropertyType(tag)
    except ValueError:
        tags = ", ".join(t.value for t in PropertyType)
        raise FormatError(
            f"{where}: {tag!r} is not a property type; expected one of {tags}"
        ) from None
    try:
        return Property(key, _expand(value, where), kind)
    except (TypeError, ValueError) as exc:
        raise FormatError(f"{where}: {exc}") from exc


def _read_value(data: Any, where: str) -> Value:
    """One live-state entry.

    The JSON type is taken as given rather than guessed at, which is the one
    place this format carries more than the XML does: a `text` value whose
    content is `true` stays the string, where `codec._read_default` has to
    settle it from the key.
    """
    value: Value = _instance(Value, data, where)
    return value


def _read_message(data: Any, where: str) -> Message:
    """One binding, dispatched on its `kind`."""
    entry = _object(data, where)
    kind = entry.get("kind")
    cls = _MESSAGES.get(kind) if isinstance(kind, str) else None
    if cls is None:
        kinds = ", ".join(_MESSAGES)
        raise FormatError(
            f"{where}: {kind!r} is not a binding kind; expected one of {kinds}"
        )
    _keys(entry, {field.name for field in fields(cls)} | {"kind"}, where)

    arguments: dict[str, Any] = {}
    for key, value in entry.items():
        if key == "kind":
            continue
        nested = _NESTED.get(key)
        if nested is None:
            arguments[key] = _expand(value, where)
        elif key == "message":
            arguments[key] = _instance(nested, value, f"{where}.{key}")
        else:
            arguments[key] = [
                _instance(nested, item, f"{where}.{key}[{index}]")
                for index, item in enumerate(_sequence(value, f"{where}.{key}"))
            ]

    message: Message = cls(**arguments)
    return message


def decode(node: Any, where: str = "root") -> Control:
    """Read one control and everything under it.

    A node with no `id` is given one, as `Control` does. Nothing else is filled
    in: a node with no properties decodes to a control with none, rather than
    to the default set for its type.

    Args:
        node: The decoded JSON for a single node.
        where: What to call this node when something in it will not read. The
            default names the root, and children extend it, so a message says
            `root.children[2].properties.frame` rather than just `frame`.

    Returns:
        The control, with its children.

    Raises:
        FormatError: If the node is not an object, names no type or an unknown
            one, holds a key nothing reads, or holds a property, value or
            binding that cannot be read.
    """
    entry = _object(node, where)
    _keys(entry, _NODE_KEYS, where)

    if "type" not in entry:
        raise FormatError(f"{where}: a node needs a type")
    try:
        control_type = ControlType(entry["type"])
    except ValueError:
        types = ", ".join(t.value for t in ControlType)
        raise FormatError(
            f"{where}: {entry['type']!r} is not a control type; expected one of {types}"
        ) from None

    identifier = entry.get("id")
    if identifier is not None and not isinstance(identifier, str):
        raise FormatError(
            f"{where}: id should be a string, found {_describe(identifier)}"
        )

    control = Control(
        control_type,
        id=identifier,
        properties={},
        values=[],
        messages=[],
        children=[],
    )
    # Replace the type defaults wholesale, exactly as reading XML does: a
    # property the file leaves out is one the control does not have.
    control.properties.clear()

    properties = _object(entry.get("properties", {}), f"{where}.properties")
    for key, value in properties.items():
        prop = _read_property(key, value, f"{where}.properties.{key}")
        control.properties[prop.key] = prop

    for index, value in enumerate(
        _sequence(entry.get("values", []), f"{where}.values")
    ):
        control.values.append(_read_value(value, f"{where}.values[{index}]"))

    for index, message in enumerate(
        _sequence(entry.get("messages", []), f"{where}.messages")
    ):
        control.messages.append(_read_message(message, f"{where}.messages[{index}]"))

    for index, child in enumerate(
        _sequence(entry.get("children", []), f"{where}.children")
    ):
        control.children.append(decode(child, f"{where}.children[{index}]"))

    if entry.get("includes"):
        object.__setattr__(control, "_has_includes", True)

    return control


def from_json(source: str | bytes) -> Document:
    """Parse a layout from JSON text.

    Args:
        source: The document, as text or UTF-8 bytes.

    Returns:
        The parsed document.

    Raises:
        FormatError: If the source is not JSON, is not a py2tosc layout,
            declares a schema this release does not read, or holds a node that
            cannot be read. The message names the node it gave up on.
    """
    try:
        data = json.loads(source)
    except json.JSONDecodeError as exc:
        raise FormatError(f"not valid JSON: {exc}") from exc

    document = _object(data, "the layout")
    _keys(document, _ENVELOPE_KEYS, "the layout")

    # Both markers are optional on the way in, so a file written by hand or by
    # another tool is readable without ceremony. Wrong is still wrong.
    declared = document.get("format", FORMAT)
    if declared != FORMAT:
        raise FormatError(f"{declared!r} is not a py2tosc layout")

    schema = document.get("schema", SCHEMA)
    if not isinstance(schema, int) or isinstance(schema, bool) or schema > SCHEMA:
        raise FormatError(
            f"schema {schema!r} is newer than this release reads (schema {SCHEMA})"
        )

    if "root" not in document:
        raise FormatError("the layout holds no root node")

    version = document.get("lexml", "6")
    if not isinstance(version, str):
        raise FormatError(f"lexml should be a string, found {_describe(version)}")

    return Document(root=decode(document["root"]), version=version)
