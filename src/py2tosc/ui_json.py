"""A layout described in JSON, built by the combinators in `py2tosc.ui`.

This is the second of the two JSON dialects, and it is the opposite of the
first. [`json_codec`][py2tosc.json_codec] writes the node tree exactly as the
file holds it, frames and all, and reads it back byte for byte. This describes
a layout that does not exist yet -- what nests in what, and how the space is
divided -- and hands it to `py2tosc.ui` to build and size:

```json
{
  "format": "py2tosc.ui",
  "root": {
    "column": [
      {"row": [{"repeat": 8, "of": {"fader": "ch$i"}}], "gap": 4},
      {"grid": "BUTTON", "columns": 8, "rows": 2, "name": "mutes"}
    ],
    "sizes": [3, 1], "gap": 8, "pad": 8, "frame": [0, 0, 1024, 768]
  }
}
```

It is read and never written. A resolved layout has frames and no memory of the
`row` that placed them, so there is no `to_ui_json` and `save` always writes the
faithful encoding. `py2tosc.load` tells the two apart by the envelope's
`format`, which is why it is required here and optional there.

Four rules are the whole of it.

- **One key names the thing.** Every node carries exactly one key from the tag
  table -- a combinator or a control -- and everything else is an argument to
  it. `{"row": [...], "gap": 4}` is `ui.row(*children, gap=4)`, mechanically.
- **The value is the tag's one positional argument.** Children for the
  combinators that arrange them, the control type for `grid`, the control being
  wrapped for `labelled` and `inset`, and the name for a plain control, since a
  name is what a control almost always has.
- **`repeat` expands in place.** It is a child rather than a property of its
  parent, so it works anywhere children are accepted.
- **A sibling key that is not an argument is a property.** Checked against what
  the type accepts, so `gpa` is a message rather than a custom property nobody
  asked for. Genuinely custom keys go under `props`.

Being a dialect over `py2tosc.ui`, it inherits that module's carve-out from the
[stability policy](https://shakfu.github.io/py2tosc/stability/): it may change
in a minor release, where the rest of the format work may not. Nothing it
builds is unusual -- the documents that come out are ordinary `Control` trees,
and if this ever becomes inconvenient they remain valid.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields
from typing import Any

from . import ui
from ._reading import as_list, as_object, check_keys, describe
from .control import (
    Control,
    box,
    button,
    encoder,
    fader,
    group,
    label,
    radar,
    radial,
    radio,
    text,
    xy,
)
from .defaults import allowed_properties
from .document import Document
from .enums import ControlType
from .errors import FormatError
from .messages import LocalMessage, Message, Value
from .properties import to_camel

__all__ = ["DIALECT", "SCHEMA", "build", "from_json"]

#: What the envelope must call itself. Unlike the faithful encoding's marker
#: this one is required, because it is what tells the two dialects apart.
DIALECT = "py2tosc.ui"

#: The dialect version. A change that would stop an already written file from
#: reading gets a new one.
SCHEMA = 1

#: The canvas a root with no frame of its own gets, matching `Document.new`.
CANVAS = (0, 0, 1024, 768)

_ENVELOPE_KEYS = frozenset({"format", "schema", "lexml", "root"})

#: Keys any node may carry, whatever its tag.
_COMMON_KEYS = frozenset({"id", "messages", "values", "props"})

#: Tags whose value is a list of children.
_ARRANGE: dict[str, Any] = {
    "row": ui.row,
    "column": ui.column,
    "tiles": ui.tiles,
    "stack": ui.stack,
    "pager": ui.pager,
}

#: Tags whose value is the control's name.
_CONTROLS: dict[str, Any] = {
    "box": box,
    "button": button,
    "encoder": encoder,
    "fader": fader,
    "label": label,
    "radar": radar,
    "radial": radial,
    "radio": radio,
    "text": text,
    "xy": xy,
}

#: The keyword arguments each tag takes, beyond properties. `labelled` calls
#: its text `caption` here: `text` is the name of a control, and a key that
#: could be either would make the tag ambiguous for no gain.
_OPTIONS: dict[str, frozenset[str]] = {
    "row": frozenset({"sizes", "gap", "pad"}),
    "column": frozenset({"sizes", "gap", "pad"}),
    "tiles": frozenset({"columns", "rows", "gap", "pad"}),
    "stack": frozenset({"pad"}),
    "pager": frozenset({"pad"}),
    "grid": frozenset({"columns", "rows"}),
    "labelled": frozenset({"caption", "size", "inset"}),
    "inset": frozenset({"by"}),
    "group": frozenset(),
}

#: What each tag produces, for checking that a property belongs on it. `inset`
#: returns the control it was handed, so it takes no properties of its own.
_PRODUCES: dict[str, ControlType] = {
    "row": ControlType.GROUP,
    "column": ControlType.GROUP,
    "tiles": ControlType.GROUP,
    "stack": ControlType.GROUP,
    "group": ControlType.GROUP,
    "labelled": ControlType.GROUP,
    "pager": ControlType.PAGER,
    "grid": ControlType.GRID,
    **{tag: ControlType(tag.upper()) for tag in _CONTROLS},
}

_TAGS = frozenset(_PRODUCES) | {"inset"}

#: Tags that are also the name of a property or of another tag's argument:
#: `grid` is a GRID control and the switch that draws grid lines on a fader,
#: and `inset` is a combinator and an argument of `labelled`. A node holding
#: one of these plus a real tag is not ambiguous, it just has a property with
#: an awkward name, so these lose the tie in `_tag`.
_AMBIGUOUS = _TAGS & (
    frozenset().union(*_OPTIONS.values())
    | frozenset().union(*(allowed_properties(t) for t in ControlType))
)

#: The bindings a control can carry, and the argument each takes by position.
_MESSAGES: dict[str, Any] = {
    "osc": ui.osc,
    "midi_cc": ui.midi_cc,
    "midi_note": ui.midi_note,
    "connect": ui.connect,
}

#: Arguments a binding takes that are partials rather than plain values. They
#: have no notation here and are not worth inventing one for: a layout that
#: needs them is one to build in Python, or to write in the faithful encoding.
_PARTIAL_ONLY = frozenset({"args", "triggers"})

_PLACEHOLDER = re.compile(r"\$(?:\$|\{(\w+)\}|(\w+))")


@dataclass
class _Deferred:
    """A `connect` waiting for the control it names to exist."""

    message: LocalMessage
    name: str
    where: str


# -- repetition --------------------------------------------------------------


def _counters(entry: dict[str, Any]) -> frozenset[str]:
    """The two names one repeat binds: `i` and `i0`, or whatever `as` calls them."""
    named = entry.get("as", "i")
    name = named if isinstance(named, str) else "i"
    return frozenset({name, f"{name}0"})


def _lookup(
    name: str, bindings: dict[str, int], inner: frozenset[str], where: str
) -> int | None:
    """What a counter stands for, or `None` if a nested repeat will bind it."""
    if name in bindings:
        return bindings[name]
    if name in inner:
        return None
    known = ", ".join(f"${key}" for key in sorted(bindings))
    raise FormatError(
        f"{where}: ${name} is not one of this repeat's counters ({known}); "
        f"write $$ for a literal dollar sign"
    )


def _interpolate(
    source: str, bindings: dict[str, int], inner: frozenset[str], where: str
) -> Any:
    """Substitute a repeat's counters into one string.

    A string that is nothing but a counter keeps its type, so `"$i0"` is the
    number a controller number wants while `"ch$i"` is the name a control
    wants. A counter a nested repeat will bind is left as it was written, so
    the inner pass can fill it in.
    """
    whole = _PLACEHOLDER.fullmatch(source)
    if whole is not None and (whole.group(1) or whole.group(2)):
        found = _lookup(whole.group(1) or whole.group(2), bindings, inner, where)
        return source if found is None else found

    def replace(match: re.Match[str]) -> str:
        name = match.group(1) or match.group(2)
        if name is None:
            return "$"
        found = _lookup(name, bindings, inner, where)
        return match.group(0) if found is None else str(found)

    return _PLACEHOLDER.sub(replace, source)


def _substitute(
    value: Any,
    bindings: dict[str, int],
    where: str,
    inner: frozenset[str] = frozenset(),
) -> Any:
    """A copy of one repeated node with the counters filled in.

    Values only. A property key holding a counter would be a different
    property each time round, which is never what anyone means.

    A nested repeat is descended into with its own counter names held back,
    since those are the inner pass's to fill: `{"repeat": 2, "as": "bank",
    "of": {"row": [{"repeat": 3, "of": {"button": "b$bank-$i"}}]}}` has to
    leave `$i` alone while replacing `$bank`.
    """
    if isinstance(value, str):
        return _interpolate(value, bindings, inner, where)
    if isinstance(value, list):
        return [_substitute(item, bindings, where, inner) for item in value]
    if isinstance(value, dict):
        nested = _counters(value) if "repeat" in value else frozenset()
        return {
            key: _substitute(
                item, bindings, where, inner | nested if key == "of" else inner
            )
            for key, item in value.items()
        }
    return value


def _count(entry: dict[str, Any], key: str, where: str, low: int) -> int:
    number = entry.get(key, low)
    if isinstance(number, bool) or not isinstance(number, int):
        raise FormatError(
            f"{where}: {key} should be a number, found {describe(number)}"
        )
    if number < low:
        raise FormatError(f"{where}: {key} is {number}, which is less than {low}")
    return number


def _repeat(
    entry: dict[str, Any], where: str, deferred: list[_Deferred]
) -> list[Control]:
    """Expand one `repeat` into the controls it stands for."""
    check_keys(entry, {"repeat", "of", "from", "as"}, where)
    if "of" not in entry:
        raise FormatError(f"{where}: a repeat needs an `of` to repeat")

    count = _count(entry, "repeat", where, 1)
    start = _count(entry, "from", where, 0) if "from" in entry else 1
    counter = entry.get("as", "i")
    if not isinstance(counter, str) or not counter.isidentifier():
        raise FormatError(f"{where}: as should name a counter, found {counter!r}")

    built = []
    for step in range(count):
        bindings = {counter: start + step, f"{counter}0": step}
        spot = f"{where}#{step + 1}"
        built.append(_node(_substitute(entry["of"], bindings, spot), spot, deferred))
    return built


# -- nodes -------------------------------------------------------------------


def _tag(entry: dict[str, Any], where: str) -> str:
    """Which key names the thing, of the ones that could."""
    found = [key for key in entry if key in _TAGS]
    if len(found) > 1:
        # A property that shares a tag's name loses: `{"fader": "ch1",
        # "grid": false}` is a fader with grid lines off, not two tags.
        found = [key for key in found if key not in _AMBIGUOUS] or found
    if len(found) == 1:
        return found[0]
    if not found:
        raise FormatError(
            f"{where}: nothing here names a control or a layout; "
            f"expected one of {', '.join(sorted(_TAGS))}"
        )
    raise FormatError(
        f"{where}: {' and '.join(repr(f) for f in found)} both name something; "
        f"a node is one thing"
    )


def _split(
    entry: dict[str, Any], tag: str, where: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Sort a node's remaining keys into arguments and properties."""
    options: dict[str, Any] = {}
    props: dict[str, Any] = {}
    accepts = allowed_properties(_PRODUCES[tag]) if tag in _PRODUCES else frozenset()

    for key, value in entry.items():
        if key == tag or key in _COMMON_KEYS:
            continue
        if key in _OPTIONS.get(tag, frozenset()):
            options[key] = value
        elif to_camel(key) in accepts:
            props[key] = value
        else:
            allowed = _OPTIONS.get(tag, frozenset()) | _COMMON_KEYS | accepts
            check_keys({key: value}, allowed, where)

    for key, value in as_object(entry.get("props", {}), f"{where}.props").items():
        props[key] = value
    return options, props


def _control(
    tag: str,
    value: Any,
    options: dict[str, Any],
    props: dict[str, Any],
    where: str,
    deferred: list[_Deferred],
) -> Control:
    """Build the control one tag stands for."""
    if tag in _ARRANGE:
        children = _children(value, f"{where}.{tag}", deferred)
        built: Control = _ARRANGE[tag](*children, **options, **props)
        return built

    if tag == "group":
        return group(children=_children(value, f"{where}.{tag}", deferred), **props)

    if tag == "grid":
        if not isinstance(value, str):
            raise FormatError(
                f"{where}: grid takes the control type to replicate, "
                f"found {describe(value)}"
            )
        try:
            kind = ControlType(value)
        except ValueError:
            types = ", ".join(t.value for t in ControlType)
            raise FormatError(
                f"{where}: {value!r} is not a control type; expected one of {types}"
            ) from None
        return ui.grid(kind, **options, **props)

    if tag == "labelled":
        if "caption" not in options:
            raise FormatError(f"{where}: labelled needs a caption")
        inner = _node(value, f"{where}.labelled", deferred)
        return ui.labelled(inner, options.pop("caption"), **options, **props)

    if tag == "inset":
        if "by" not in options:
            raise FormatError(f"{where}: inset needs a `by` to shrink it by")
        return ui.inset(_node(value, f"{where}.inset", deferred), options["by"])

    if value is not None and not isinstance(value, (str, dict)):
        raise FormatError(f"{where}: {tag} takes its name, found {describe(value)}")
    if isinstance(value, str):
        props.setdefault("name", value)
    control: Control = _CONTROLS[tag](**props)
    return control


def _children(data: Any, where: str, deferred: list[_Deferred]) -> list[Control]:
    """Every child of one node, with any `repeat` expanded where it stood."""
    built: list[Control] = []
    for index, item in enumerate(as_list(data, where)):
        spot = f"{where}[{index}]"
        entry = as_object(item, spot)
        if "repeat" in entry:
            built.extend(_repeat(entry, spot, deferred))
        else:
            built.append(_node(entry, spot, deferred))
    return built


def _node(data: Any, where: str, deferred: list[_Deferred]) -> Control:
    """Read one node: the tag, its argument, and everything hanging off it."""
    entry = as_object(data, where)
    tag = _tag(entry, where)
    options, props = _split(entry, tag, where)

    try:
        control = _control(tag, entry[tag], options, props, where, deferred)
    except FormatError:
        raise
    except (TypeError, ValueError) as exc:
        # A combinator refusing what it was given: a row that cannot fit its
        # children, a property that will not coerce, a bad argument type.
        raise FormatError(f"{where}: {exc}") from exc

    identifier = entry.get("id")
    if identifier is not None:
        if not isinstance(identifier, str):
            raise FormatError(
                f"{where}: id should be a string, found {describe(identifier)}"
            )
        control.id = identifier

    if "values" in entry:
        control.values = [
            _value(item, f"{where}.values[{index}]")
            for index, item in enumerate(as_list(entry["values"], f"{where}.values"))
        ]

    for index, item in enumerate(
        as_list(entry.get("messages", []), f"{where}.messages")
    ):
        control.messages.append(
            _message(item, control, f"{where}.messages[{index}]", deferred)
        )
    return control


def _value(data: Any, where: str) -> Value:
    entry = as_object(data, where)
    check_keys(entry, {field.name for field in fields(Value)}, where)
    return Value(**entry)


# -- bindings ----------------------------------------------------------------


def _message(
    data: Any, control: Control, where: str, deferred: list[_Deferred]
) -> Message:
    """Read one binding, deferring a `connect` until its destination exists."""
    entry = as_object(data, where)
    found = [key for key in entry if key in _MESSAGES]
    if len(found) != 1:
        kinds = ", ".join(sorted(_MESSAGES))
        raise FormatError(
            f"{where}: a binding is one of {kinds}"
            + (f", found {' and '.join(repr(f) for f in found)}" if found else "")
        )

    kind = found[0]
    for key in entry:
        if key in _PARTIAL_ONLY:
            raise FormatError(
                f"{where}: {key} takes partials, which this dialect has no "
                f"notation for; build that binding in Python, or write the "
                f"layout in the faithful encoding"
            )

    builder = _MESSAGES[kind]
    accepted = {
        name for name in builder.__kwdefaults__ or {} if name not in _PARTIAL_ONLY
    }
    check_keys(entry, accepted | {kind}, where)

    options = {key: item for key, item in entry.items() if key != kind}
    target = entry[kind]

    if kind == "connect":
        if not isinstance(target, str):
            raise FormatError(
                f"{where}: connect takes the name of the control it writes to, "
                f"found {describe(target)}"
            )
        binding = ui.connect("", **options)
        deferred.append(_Deferred(binding, target, where))
        return binding

    try:
        message: Message = builder(target, **options)
    except (TypeError, ValueError) as exc:
        raise FormatError(f"{where}: {exc}") from exc
    return message


def _resolve_connections(doc: Document, deferred: list[_Deferred]) -> None:
    """Point every `connect` at the control it named, now that all of them exist."""
    for pending in deferred:
        matches = doc.find_all(pending.name)
        if not matches:
            raise FormatError(f"{pending.where}: no control is named {pending.name!r}")
        if len(matches) > 1:
            raise FormatError(
                f"{pending.where}: {len(matches)} controls are named "
                f"{pending.name!r}, so the binding cannot say which"
            )
        pending.message.dst_id = matches[0].id


# -- the document ------------------------------------------------------------


def build(data: Any) -> Document:
    """Build a layout from already-parsed JSON.

    The tree is built, every `connect` is pointed at the control it named, and
    the whole thing is resolved, so what comes back is sized and ready to save.

    Args:
        data: The decoded JSON.

    Returns:
        The document.

    Raises:
        FormatError: If the envelope is not this dialect, declares a schema
            this release does not read, or holds a node that cannot be built.
            The message names the node it gave up on.
    """
    document = as_object(data, "the layout")
    check_keys(document, _ENVELOPE_KEYS, "the layout")

    declared = document.get("format")
    if declared != DIALECT:
        raise FormatError(f"{declared!r} is not a {DIALECT} layout")

    schema = document.get("schema", SCHEMA)
    if isinstance(schema, bool) or not isinstance(schema, int) or schema > SCHEMA:
        raise FormatError(
            f"schema {schema!r} is newer than this release reads (schema {SCHEMA})"
        )

    if "root" not in document:
        raise FormatError("the layout holds no root node")

    version = document.get("lexml", "6")
    if not isinstance(version, str):
        raise FormatError(f"lexml should be a string, found {describe(version)}")

    deferred: list[_Deferred] = []
    described = as_object(document["root"], "root")
    root = _node(described, "root", deferred)

    # Every control type defaults a frame, so the root having one says nothing
    # about whether the layout asked for a canvas. What the file wrote does.
    given = as_object(described.get("props", {}), "root.props")
    if "frame" not in described and "frame" not in given:
        root.set("frame", CANVAS)

    doc = Document(root=root, version=version)
    _resolve_connections(doc, deferred)
    try:
        return doc.resolve()
    except ValueError as exc:
        raise FormatError(f"the layout will not resolve: {exc}") from exc


def from_json(source: str | bytes) -> Document:
    """Build a layout from JSON text.

    Args:
        source: The description, as text or UTF-8 bytes.

    Returns:
        The document, built and resolved.

    Raises:
        FormatError: If the source is not JSON, or is not a layout this can
            build.
    """
    try:
        return build(json.loads(source))
    except json.JSONDecodeError as exc:
        raise FormatError(f"not valid JSON: {exc}") from exc
