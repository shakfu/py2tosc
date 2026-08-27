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
  parent, so it works anywhere children are accepted. A node repeats itself --
  `{"fader": "ch$i", "repeat": 8}` -- or holds the node it repeats under `of`,
  which keeps a long template separate from the count. `each` walks a list of
  rows where `repeat` counts, binding every field of a row the way `repeat`
  binds `$i`, which is how a layout whose names and numbers follow no sequence
  is described. Substitution reaches values and never keys, so one repeat
  builds one kind of thing -- unless a `case` names a field and a `when` holds
  a complete node per value that field takes, which is how a table of mixed
  controls is written without a key ever coming from a row. A choice appears
  under a repeat's `of`, or among a node's children or bindings, where a branch
  may hold several nodes or none -- so a row can decide whether something is
  there at all, not only which thing it is.
- **A sibling key that is not an argument is a property.** Checked against what
  the type accepts, so `gpa` is a message rather than a custom property nobody
  asked for. Genuinely custom keys go under `props`. `text` is the exception
  that proves it: what a label says is a value rather than a property, and
  `{"label": "readout", "text": "Hello"}` is what anyone would write.

What a binding sends is assembled from partials, and each is an object of the
same shape as everything else: `{"value": "x"}`, `{"prop": "name"}`,
`{"const": "#7"}` or `{"index": null}`, with `conversion` and `scale` alongside.
A bare string keeps the meaning `ui` gives it -- the key of a value -- so a
constant says so, and in `args`, where neither reading is safe to guess, a bare
string is refused rather than assumed.

A key beginning with `//` is a comment, ignored wherever a key may appear.
JSON has no notation for one, and a description that exists to be reviewed
needs somewhere to say why a number is what it is.

Being a dialect over `py2tosc.ui`, it inherits that module's carve-out from the
[stability policy](https://shakfu.github.io/py2tosc/stability/): it may change
in a minor release, where the rest of the format work may not. Nothing it
builds is unusual -- the documents that come out are ordinary `Control` trees,
and if this ever becomes inconvenient they remain valid.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, fields, replace
from typing import Any

from . import ui
from ._reading import as_list, as_object, check_keys, describe, read_schema
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
from .defaults import allowed_properties, default_values_for
from .document import Document
from .enums import ControlType, TriggerCondition
from .errors import FormatError
from .messages import LocalMessage, Message, Partial, Trigger, Value
from .properties import Property, to_camel

__all__ = [
    "DIALECT",
    "SCHEMA",
    "SCHEMAS",
    "build",
    "from_json",
    "required_schema",
    "supports",
]

#: What the envelope must call itself. Unlike the faithful encoding's marker
#: this one is required, because it is what tells the two dialects apart.
DIALECT = "py2tosc.ui"

#: The dialect version. A change that would stop an already written file from
#: reading gets a new one. Schema 2 added the choice a repeat makes with `case`
#: and `when`, which an older reader would refuse as a node naming no tag;
#: schema 3 let that choice appear among children and bindings too, and let a
#: branch hold several nodes or none, so a row can decide whether a binding is
#: there at all rather than only which control carries it.
SCHEMA = 3

#: Every schema this release reads. `SCHEMA` names the newest of them and says
#: nothing about the floor, which is the half a producer needs: this dialect is
#: read and never written, so whatever writes a description is the thing that
#: has to know what the installed reader accepts, and stamp what it emits.
SCHEMAS = range(1, SCHEMA + 1)

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

#: Sibling keys that set one of the control's *values* rather than a
#: property. Only `text` so far, because a label saying something is the
#: second most common thing anyone does to one and `values` is a long way to
#: say it. A control whose type does not carry the value refuses the key, as
#: it would any other it does not know.
_VALUE_SUGAR = frozenset({"text"})

#: Tags that are also the name of a property or of another tag's argument:
#: `grid` is a GRID control and the switch that draws grid lines on a fader,
#: and `inset` is a combinator and an argument of `labelled`. A node holding
#: one of these plus a real tag is not ambiguous, it just has a property with
#: an awkward name, so these lose the tie in `_tag`.
_AMBIGUOUS = _TAGS & (
    _VALUE_SUGAR
    | frozenset().union(*_OPTIONS.values())
    | frozenset().union(*(allowed_properties(t) for t in ControlType))
)

#: The bindings a control can carry, and the argument each takes by position.
_MESSAGES: dict[str, Any] = {
    "osc": ui.osc,
    "midi_cc": ui.midi_cc,
    "midi_note": ui.midi_note,
    "connect": ui.connect,
}

#: What each binding's one positional argument is: the type it has to be,
#: and what to call it in the message when it is not. Checked here rather than
#: left to the combinator, whose own complaint is about its internals -- a
#: quoted controller number reaches for `Partial.type` and a numeric address
#: reaches for `len`, neither of which names anything the file wrote.
_TAKES: dict[str, tuple[tuple[type, ...], str]] = {
    "osc": ((str,), "an address"),
    "midi_cc": ((int, dict), "a controller number or a partial that reads one"),
    "midi_note": ((int, dict), "a note number or a partial that reads one"),
    "connect": ((str,), "the name of the control it writes to"),
}

#: The partials a binding is assembled from, and what each reads by position.
#: One key names the thing here as it does everywhere else, so a partial is an
#: object carrying one of these.
_PARTIALS: dict[str, tuple[Any, str]] = {
    "value": (ui.value, "the key of a value to read"),
    "const": (ui.const, "the text to send"),
    "prop": (ui.prop, "the name of a property to read"),
    "index": (ui.index, ""),
}

#: The arguments of each binding a partial can be written into. A bare string
#: in one of these keeps the meaning `ui` gives it -- the key of a value -- so
#: a constant has to say so: `{"const": "#7"}`.
_PARTIAL_ARGS: dict[str, frozenset[str]] = {
    "osc": frozenset({"args"}),
    "midi_cc": frozenset({"source", "channel"}),
    "midi_note": frozenset({"source", "channel"}),
    "connect": frozenset({"source", "to"}),
}

_PLACEHOLDER = re.compile(r"\$(?:\$|\{(\w+)\}|(\w+))")

#: How a comment is written. JSON has none, and a description is meant to be
#: read by the people who have to review it, so a key beginning with this is
#: ignored wherever a key may appear -- in a node, a binding, a value, the
#: envelope, and inside `props`. More than one to an object, since JSON keys
#: are unique: `"//"`, `"//why"`, `"// left at 8 because"`.
_COMMENT = "//"

#: The keys a repeat spends on itself. Everything else it carries is the node
#: being repeated, in the short form.
_REPEAT_KEYS = frozenset({"repeat", "each", "of", "from", "as"})

#: What a choice is written with, where an `of` holds one instead of a node.
_CHOICE_KEYS = frozenset({"case", "when"})

#: The lists a choice can appear in, and what its branches are checked as. A
#: choice expands where it stands, exactly as a repeat does, so these are the
#: places something can expand into.
_SLOTS: dict[str, str] = {
    **{tag: "children" for tag in _ARRANGE},
    "group": "children",
    "messages": "bindings",
}


def _object(data: Any, where: str) -> dict[str, Any]:
    """Insist on an object, and drop the comments from it.

    Every object this dialect reads goes through here rather than through
    `as_object` directly, so a comment is ignored in one place rather than
    being admitted key by key to every check in the file.
    """
    entry = as_object(data, where)
    if not any(key.startswith(_COMMENT) for key in entry):
        return entry
    return {key: item for key, item in entry.items() if not key.startswith(_COMMENT)}


@dataclass
class _Deferred:
    """A `connect` waiting for the control it names to exist."""

    message: LocalMessage
    name: str
    where: str


# -- repetition --------------------------------------------------------------


def _repeats(entry: dict[str, Any]) -> bool:
    """Whether one node stands for several: by counting, or by walking a list."""
    return "repeat" in entry or "each" in entry


def _counters(entry: dict[str, Any]) -> frozenset[str]:
    """Every name one repeat binds: its two counters, and a record's fields.

    `i` and `i0`, or whatever `as` calls them, plus each field of every record
    an `each` walks -- the union across all of them, since what the inner pass
    will bind is what the outer pass has to leave alone.
    """
    named = entry.get("as", "i")
    name = named if isinstance(named, str) else "i"
    bound = {name, f"{name}0"}

    records = entry.get("each")
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict):
                bound |= {key for key in record if isinstance(key, str)}
    return frozenset(bound)


def _template(entry: dict[str, Any]) -> frozenset[str]:
    """Which of a repeat's keys hold the node being repeated.

    The long form keeps it under `of` and the short form *is* it, so which
    keys a nested repeat's counters have to be held back from depends on
    which form it was written in.
    """
    if "of" in entry:
        return frozenset({"of"})
    return frozenset(entry) - _REPEAT_KEYS


def _lookup(
    name: str, bindings: dict[str, Any], inner: frozenset[str], where: str
) -> Any:
    """What a name stands for, or `None` if a nested repeat will bind it.

    `None` is the sentinel for "not this pass's to fill", which is why a record
    field may not hold null: the two would be indistinguishable here.

    Held-back names are checked first. Both repeats bind `$i` when neither
    names its counter with `as`, and the inner one owns it there: it is the
    pass that will fill it in.
    """
    if name in inner:
        return None
    if name in bindings:
        return bindings[name]
    known = ", ".join(f"${key}" for key in sorted(bindings))
    raise FormatError(
        f"{where}: ${name} is not one of the names this repeat binds ({known}); "
        f"write $$ for a literal dollar sign"
    )


def _spelled(value: Any) -> str:
    """How a bound value reads as text: the file's spelling, not Python's.

    Written into a longer string, or matched against the name of a branch. A
    boolean comes out `true` either way, which is what the row that holds one
    wrote, rather than the `True` Python would print.
    """
    return str(value).lower() if isinstance(value, bool) else str(value)


def _interpolate(
    source: str, bindings: dict[str, Any], inner: frozenset[str], where: str
) -> Any:
    """Substitute a repeat's names into one string.

    A string that is nothing but a name keeps its type, so `"$i0"` is the
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
        if found is None:
            return match.group(0)
        return _spelled(found)

    return _PLACEHOLDER.sub(replace, source)


def _is_choice(value: Any) -> bool:
    """Whether one object is a choice rather than a node."""
    if not isinstance(value, dict):
        return False
    return bool(_CHOICE_KEYS & {k for k in value if not k.startswith(_COMMENT)})


def _branch_list(branch: Any) -> list[Any]:
    """One branch as the list it stands for.

    A branch is a node, or a list of them spliced where the choice stood --
    including none, which is how a row says a binding is not there at all
    rather than which binding it is.
    """
    return branch if isinstance(branch, list) else [branch]


def _check_choice(entry: dict[str, Any], slot: str, where: str) -> dict[str, Any]:
    """Everything about a choice that is knowable before a row selects.

    Every branch, not only the one taken, because keys are literal and so the
    whole table is checkable against the tag table here -- which is the
    property the value-only substitution rule exists to keep. What a branch is
    checked *as* depends on where the choice stands, which is what `slot`
    carries: a list of children wants nodes, a `messages` list wants bindings.
    """
    entry = _object(entry, where)
    check_keys(entry, _CHOICE_KEYS, where)
    missing = sorted(_CHOICE_KEYS - set(entry))
    if missing:
        raise FormatError(
            f"{where}: a choice reads a field with `case` and holds the "
            f"branches it chooses between under `when`; {missing[0]!r} is missing"
        )

    if not isinstance(entry["case"], str):
        raise FormatError(
            f"{where}: case reads the field that chooses a branch, "
            f"found {describe(entry['case'])}"
        )

    table = _object(entry["when"], f"{where}.when")
    if not table:
        raise FormatError(f"{where}.when: a choice needs a branch to choose")

    for name, branch in table.items():
        spot = f"{where}.when[{name!r}]"
        if isinstance(branch, list) and slot == "node":
            raise FormatError(
                f"{spot}: a repeat builds one node per pass, so a branch here "
                f"is one node; a branch holds a list only among children or "
                f"bindings"
            )
        for index, node in enumerate(_branch_list(branch)):
            at = spot if not isinstance(branch, list) else f"{spot}[{index}]"
            written = _object(node, at)
            if slot == "bindings":
                _binding_kind(written, at)
            else:
                _tag(written, at)
    return entry


def _pick(
    entry: dict[str, Any],
    bindings: dict[str, Any],
    inner: frozenset[str],
    where: str,
) -> Any:
    """Which branch one row takes, or `None` if this pass cannot say.

    A choice inside a nested repeat selects on a name that repeat binds, so the
    outer pass leaves it alone exactly as it leaves that repeat's counters
    alone, and the inner pass does the choosing.
    """
    picked = _interpolate(entry["case"], bindings, inner, where)
    if isinstance(picked, str) and _PLACEHOLDER.search(picked):
        return None

    name = _spelled(picked)
    table = entry["when"]
    if name not in table:
        written = ", ".join(repr(key) for key in table)
        raise FormatError(
            f"{where}: case read {name!r}, and no branch is written for it; "
            f"when holds {written}"
        )
    return table[name]


def _substitute(
    value: Any,
    bindings: dict[str, Any],
    where: str,
    inner: frozenset[str] = frozenset(),
    slot: str = "node",
) -> Any:
    """A copy of one repeated node with the counters filled in.

    Values only. A property key holding a counter would be a different
    property each time round, which is never what anyone means.

    A nested repeat is descended into with its own counter names held back,
    since those are the inner pass's to fill: `{"repeat": 2, "as": "bank",
    "of": {"row": [{"repeat": 3, "of": {"button": "b$bank-$i"}}]}}` has to
    leave `$i` alone while replacing `$bank`. What is held back and where
    depends on which form the inner repeat was written in, which is what
    `_template` answers.

    Comments are dropped rather than copied. They are ignored either way, and
    substituting into one would make a `$` in a note about a layout an error
    about a counter nobody bound.
    """
    if isinstance(value, str):
        return _interpolate(value, bindings, inner, where)
    if isinstance(value, list):
        return [_substitute(item, bindings, where, inner, slot) for item in value]
    if isinstance(value, dict):
        if slot != "node" and _is_choice(value):
            entry = _check_choice(value, slot, where)
            picked = _pick(entry, bindings, inner, where)
            if picked is not None:
                # A list stays a list: `_children` and the bindings loop splice
                # it where the choice stood, the way a repeat expands in place.
                return _substitute(picked, bindings, where, inner, slot)
        held = _template(value) if _repeats(value) else frozenset()
        nested = _counters(value) if held else frozenset()
        return {
            key: _substitute(
                item,
                bindings,
                where,
                inner | nested if key in held else inner,
                _SLOTS.get(key, "node"),
            )
            for key, item in value.items()
            if not key.startswith(_COMMENT)
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


def _record(data: Any, counter: str, where: str) -> dict[str, Any]:
    """One row of an `each`, checked against what a name can stand for."""
    fields = _object(data, where)
    for key, value in fields.items():
        if not key.isidentifier():
            raise FormatError(
                f"{where}: a field is read as ${key}, and {key!r} cannot be "
                f"written that way, so nothing could reach it"
            )
        if key in (counter, f"{counter}0"):
            raise FormatError(
                f"{where}: {key!r} is this repeat's own counter; rename one of "
                f"the two with `as`"
            )
        if value is None or isinstance(value, (dict, list)):
            # Null is the sentinel `_lookup` uses for a name a nested repeat
            # will bind, and a list or an object has no reading inside a
            # string. A row holds the values a control is described with.
            raise FormatError(
                f"{where}: {key} should be a string, a number or a boolean, "
                f"found {describe(value)}"
            )
    return fields


def _rows(entry: dict[str, Any], counter: str, where: str) -> list[dict[str, Any]]:
    """What each pass of one repeat binds beyond its counters.

    A `repeat` binds nothing beyond them and says only how many passes to make;
    an `each` binds a row of fields per pass and says how many by how many rows
    it holds -- including none, since a list of nothing is what a generator
    with nothing to emit produces, where a `repeat` of 0 is a typo.
    """
    if "each" not in entry:
        return [{} for _ in range(_count(entry, "repeat", where, 1))]
    return [
        _record(record, counter, f"{where}.each[{index}]")
        for index, record in enumerate(as_list(entry["each"], f"{where}.each"))
    ]


def _repeat(
    entry: dict[str, Any], where: str, deferred: list[_Deferred]
) -> list[Control]:
    """Expand one `repeat` or `each` into the controls it stands for.

    Two axes, and they are independent. A repeat counts with `repeat` or walks
    a list of rows with `each`; and it holds the node it repeats under `of`, or
    is that node itself.
    """
    if "repeat" in entry and "each" in entry:
        raise FormatError(
            f"{where}: a repeat counts with `repeat` or walks a list with "
            f"`each`, not both; an `each` is as long as the list it holds"
        )

    if "of" in entry:
        also = [key for key in entry if key in _TAGS]
        if also:
            named = " and ".join(repr(key) for key in also)
            raise FormatError(
                f"{where}: a repeat holds the node it repeats under `of` or is "
                f"that node itself, not both; {named} names one and `of` holds "
                f"another"
            )
        check_keys(entry, _REPEAT_KEYS, where)
        described: Any = entry["of"]
    elif any(key in _TAGS for key in entry):
        described = {
            key: item for key, item in entry.items() if key not in _REPEAT_KEYS
        }
    else:
        # Nothing here names a node, so this is the long form with something
        # wrong with it. A misspelled `of` is the likeliest and worth saying.
        if _CHOICE_KEYS & set(entry):
            raise FormatError(
                f"{where}: a choice is what a repeat repeats, so it goes under "
                f"`of`; the short form is the node itself, and a choice is a "
                f"table of nodes rather than one"
            )
        check_keys(entry, _REPEAT_KEYS, where)
        raise FormatError(
            f"{where}: a repeat needs an `of` to repeat, or a tag of its own "
            f"to repeat itself"
        )

    start = _count(entry, "from", where, 0) if "from" in entry else 1
    counter = entry.get("as", "i")
    if not isinstance(counter, str) or not counter.isidentifier():
        raise FormatError(f"{where}: as should name a counter, found {counter!r}")

    # Read once, before any row is: what the branches are is a property of the
    # template, and a table with something wrong with it should say so whether
    # or not there are rows to reach it.
    choice = (
        _check_choice(described, "node", f"{where}.of")
        if "of" in entry and _is_choice(described)
        else None
    )

    built = []
    for step, row in enumerate(_rows(entry, counter, where)):
        bindings: dict[str, Any] = {counter: start + step, f"{counter}0": step}
        bindings.update(row)
        spot = f"{where}#{step + 1}"
        # Only the branch a row selects is substituted into, so a branch reads
        # the fields its own rows carry and no others.
        template = described
        if choice is not None:
            picked = _pick(choice, bindings, frozenset(), spot)
            if picked is None:
                raise FormatError(
                    f"{spot}: case reads a name no enclosing repeat binds"
                )
            template = picked
        built.append(_node(_substitute(template, bindings, spot), spot, deferred))
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
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Sort a node's remaining keys into arguments, properties and values."""
    options: dict[str, Any] = {}
    props: dict[str, Any] = {}
    defaults: dict[str, Any] = {}
    accepts = allowed_properties(_PRODUCES[tag]) if tag in _PRODUCES else frozenset()
    carries = (
        {key for key, _ in default_values_for(_PRODUCES[tag])}
        if tag in _PRODUCES
        else frozenset()
    )

    for key, value in entry.items():
        if key == tag or key in _COMMON_KEYS:
            continue
        if key in ("repeat", "each"):
            # Reaching `_split` at all means this node was not read out of a
            # list, since `_children` expands a repeat before building one.
            raise FormatError(
                f"{where}: a repeat expands where children are accepted, and "
                f"this is not one of those places"
            )
        if key in _OPTIONS.get(tag, frozenset()):
            options[key] = value
        elif key in _VALUE_SUGAR and key in carries:
            defaults[key] = value
        elif to_camel(key) in accepts:
            props[key] = value
        else:
            allowed = (
                _OPTIONS.get(tag, frozenset())
                | _COMMON_KEYS
                | accepts
                | (_VALUE_SUGAR & carries)
            )
            check_keys({key: value}, allowed, where)

    for key, value in _object(entry.get("props", {}), f"{where}.props").items():
        props[key] = value

    for key, value in props.items():
        # The same coercion the control will do, run here for the sake of the
        # message: a combinator handed a whole dictionary reports the value it
        # could not take without saying which key it came from, and a node can
        # carry twenty. The faithful encoding reads properties one at a time
        # and names them for the same reason.
        try:
            Property(key, value)
        except (TypeError, ValueError) as exc:
            raise FormatError(f"{where}: {key}: {exc}") from exc

    return options, props, defaults


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
        if props:
            # `inset` hands back the control it was given, so a property here
            # has nowhere to go. A declared one is already refused by `_split`,
            # which knows the tag produces nothing; this is the `props` escape
            # hatch, which goes round that check and would otherwise vanish.
            named = ", ".join(repr(key) for key in sorted(props))
            raise FormatError(
                f"{where}: inset returns the control it was handed and takes no "
                f"properties of its own; put {named} on that control"
            )
        return ui.inset(_node(value, f"{where}.inset", deferred), options["by"])

    if value is not None and not isinstance(value, str):
        raise FormatError(f"{where}: {tag} takes its name, found {describe(value)}")
    if isinstance(value, str):
        if "name" in props:
            # Both spellings are legal on their own, so one of the two is
            # always a mistake -- most likely a generator filling in a
            # template that already carried a name.
            raise FormatError(
                f"{where}: {tag} is named twice, {value!r} by position and "
                f"{props['name']!r} by key; keep one"
            )
        props["name"] = value
    control: Control = _CONTROLS[tag](**props)
    return control


def _spliced(data: Any, where: str) -> list[tuple[str, Any]]:
    """One list with what a choice expanded to opened out where it stood.

    A branch holding a list arrives here as a list inside a list, since
    substitution puts back what the branch held. Flattening one level is what
    makes a choice expand in place the way a repeat does, and it is only one
    level: a list nested any deeper was written that way and is a mistake the
    node reader should report.
    """
    opened: list[tuple[str, Any]] = []
    for index, item in enumerate(as_list(data, where)):
        spot = f"{where}[{index}]"
        if isinstance(item, list):
            opened.extend((f"{spot}[{inner}]", held) for inner, held in enumerate(item))
        else:
            opened.append((spot, item))
    return opened


def _refuse_bare_choice(entry: dict[str, Any], where: str) -> None:
    """A choice that no repeat ever reached, reported as what it is.

    Substitution is what selects, and substitution only runs inside a repeat.
    So a choice written outside one is never chosen from, and would otherwise
    arrive at the node reader as an object naming no tag -- a message about a
    node, for something that is not one.
    """
    if _is_choice(entry) and not _repeats(entry):
        # A repeat carrying these keys is the short form of a choice, which
        # `_repeat` refuses with a message about where a choice goes. This is
        # the other case: a choice nothing will ever select from.
        raise FormatError(
            f"{where}: a choice is selected by a value a repeat binds, and "
            f"nothing here is inside a repeat"
        )


def _children(data: Any, where: str, deferred: list[_Deferred]) -> list[Control]:
    """Every child of one node, with any `repeat` or choice expanded in place."""
    built: list[Control] = []
    for spot, item in _spliced(data, where):
        entry = _object(item, spot)
        _refuse_bare_choice(entry, spot)
        if _repeats(entry):
            built.extend(_repeat(entry, spot, deferred))
        else:
            built.append(_node(entry, spot, deferred))
    return built


def _node(data: Any, where: str, deferred: list[_Deferred]) -> Control:
    """Read one node: the tag, its argument, and everything hanging off it."""
    entry = _object(data, where)
    tag = _tag(entry, where)
    options, props, defaults = _split(entry, tag, where)

    try:
        control = _control(tag, entry[tag], options, props, where, deferred)
    except FormatError:
        raise
    except Exception as exc:
        # A combinator refusing what it was given: a row that cannot fit its
        # children, a property that will not coerce, a bad argument type. The
        # net is wide on purpose -- see `_message` for why.
        raise FormatError(f"{where}: {exc}") from exc

    identifier = entry.get("id")
    if identifier is not None:
        if not isinstance(identifier, str):
            raise FormatError(
                f"{where}: id should be a string, found {describe(identifier)}"
            )
        control.id = identifier

    if "values" in entry:
        if defaults:
            named = ", ".join(repr(key) for key in sorted(defaults))
            raise FormatError(
                f"{where}: {named} and `values` both set what this control "
                f"starts at; keep one"
            )
        control.values = [
            _value(item, f"{where}.values[{index}]")
            for index, item in enumerate(as_list(entry["values"], f"{where}.values"))
        ]

    for key, value in defaults.items():
        if not isinstance(value, str):
            raise FormatError(
                f"{where}: {key} takes the text to show, found {describe(value)}"
            )
        control.values = [
            replace(existing, default=value) if existing.key == key else existing
            for existing in control.values
        ]

    for spot, item in _spliced(entry.get("messages", []), f"{where}.messages"):
        _refuse_bare_choice(_object(item, spot), spot)
        control.messages.append(_message(item, control, spot, deferred))
    return control


def _value(data: Any, where: str) -> Value:
    entry = _object(data, where)
    check_keys(entry, {field.name for field in fields(Value)}, where)
    return Value(**entry)


# -- bindings ----------------------------------------------------------------


def _partial(data: Any, where: str) -> Partial:
    """Read one partial: what it reads, and how it is converted on the way out."""
    if isinstance(data, str):
        # The one place a string cannot be guessed at. In `source` it is the
        # key of a value, which is what `ui` reads it as; here the reading
        # wanted as often is the text itself, so neither is assumed.
        raise FormatError(
            f"{where}: a partial is an object saying what it reads; write "
            f'{{"value": {data!r}}} for one of the control\'s values, or '
            f'{{"const": {data!r}}} for the text itself'
        )

    entry = _object(data, where)
    found = [key for key in entry if key in _PARTIALS]
    if len(found) != 1:
        kinds = ", ".join(sorted(_PARTIALS))
        raise FormatError(
            f"{where}: a partial is one of {kinds}"
            + (f", found {' and '.join(repr(f) for f in found)}" if found else "")
        )

    kind = found[0]
    builder, what = _PARTIALS[kind]
    accepted = set(builder.__kwdefaults__ or {})
    check_keys(entry, accepted | {kind}, where)

    options = {key: item for key, item in entry.items() if key != kind}
    target = entry[kind]

    try:
        if kind == "index":
            # An index reads where the control sits, so there is nothing to
            # name. Insisting on `null` keeps every partial the same shape.
            if target is not None:
                raise FormatError(
                    f"{where}: index reads the control's own position and takes "
                    f"nothing of its own, so its value is null"
                )
            read: Partial = builder(**options)
        elif isinstance(target, str):
            read = builder(target, **options)
        else:
            raise FormatError(f"{where}: {kind} takes {what}, found {describe(target)}")
    except FormatError:
        raise
    except Exception as exc:
        raise FormatError(f"{where}: {exc}") from exc
    return read


def _trigger(data: Any, where: str) -> Trigger:
    """Read one trigger: the value watched, and what about it fires the binding."""
    entry = _object(data, where)
    check_keys(entry, {"var", "on"}, where)

    var = entry.get("var", "x")
    if not isinstance(var, str):
        raise FormatError(f"{where}: var names a value, found {describe(var)}")

    condition = entry.get("on", str(TriggerCondition.ANY))
    if not isinstance(condition, str):
        raise FormatError(
            f"{where}: on should be a string, found {describe(condition)}"
        )
    try:
        return Trigger(var, TriggerCondition(condition))
    except ValueError as exc:
        raise FormatError(f"{where}: {exc}") from exc


def _read_partials(kind: str, options: dict[str, Any], where: str) -> dict[str, Any]:
    """One binding's arguments, with any partial or trigger written in it read."""
    for key in sorted(_PARTIAL_ARGS[kind] & set(options)):
        spot = f"{where}.{key}"
        if key == "args":
            options[key] = [
                _partial(item, f"{spot}[{index}]")
                for index, item in enumerate(as_list(options[key], spot))
            ]
        elif isinstance(options[key], dict):
            options[key] = _partial(options[key], spot)

    if "triggers" in options:
        spot = f"{where}.triggers"
        options["triggers"] = [
            _trigger(item, f"{spot}[{index}]")
            for index, item in enumerate(as_list(options["triggers"], spot))
        ]
    return options


def _takes(kind: str, target: Any, where: str) -> None:
    """Refuse a binding's positional argument before the combinator sees it."""
    wanted, what = _TAKES[kind]
    # A boolean is an `int` to Python and a mistake in a file.
    if isinstance(target, bool) or not isinstance(target, wanted):
        raise FormatError(f"{where}: {kind} takes {what}, found {describe(target)}")


def _binding_kind(entry: dict[str, Any], where: str) -> str:
    """Which of the four a binding is. Split out so a choice can check a
    branch it holds without building it."""
    found = [key for key in entry if key in _MESSAGES]
    if len(found) != 1:
        kinds = ", ".join(sorted(_MESSAGES))
        raise FormatError(
            f"{where}: a binding is one of {kinds}"
            + (f", found {' and '.join(repr(f) for f in found)}" if found else "")
        )
    return found[0]


def _message(
    data: Any, control: Control, where: str, deferred: list[_Deferred]
) -> Message:
    """Read one binding, deferring a `connect` until its destination exists."""
    entry = _object(data, where)
    kind = _binding_kind(entry, where)
    builder = _MESSAGES[kind]
    accepted = set(builder.__kwdefaults__ or {})
    check_keys(entry, accepted | {kind}, where)

    options = {key: item for key, item in entry.items() if key != kind}
    target = entry[kind]

    _takes(kind, target, where)
    options = _read_partials(kind, options, where)
    if isinstance(target, dict):
        target = _partial(target, f"{where}.{kind}")

    if kind == "connect":
        binding = ui.connect("", **options)
        deferred.append(_Deferred(binding, target, where))
        return binding

    try:
        message: Message = builder(target, **options)
    except Exception as exc:
        # Anything at all: a combinator reaching for an attribute the file's
        # value does not have is still a file that could not be read, and a
        # message without the node it belongs to is no use to whoever wrote it.
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


def _needs(entry: dict[str, Any]) -> int:
    """The schema one node needs, ignoring what is nested inside it.

    The table `required_schema` stands on, and the one thing here that cannot
    be generated from anything the reader already knows: no table records when
    a spelling arrived, so this is a hand-written historical record, and a
    schema-bumping change that forgets to add a branch here under-reports
    silently. `tests/test_schema_corpus.py` is what makes that a failing test
    rather than a wrong answer -- adding a schema means adding a description
    there, and that description has to need exactly the schema it declares.

    The conditions mirror what the reader accepts rather than looking for the
    keys anywhere, so a custom property that happens to be called `case` is not
    mistaken for a choice.
    """
    # Schema 3: a choice among children or bindings, or a branch holding a
    # list rather than one node.
    for key in _SLOTS:
        held = entry.get(key)
        if isinstance(held, list) and any(_is_choice(item) for item in held):
            return 3
    if _is_choice(entry):
        table = entry.get("when")
        if isinstance(table, dict) and any(
            isinstance(branch, list) for branch in table.values()
        ):
            return 3

    # Schema 2: a repeat choosing among branches.
    held = entry.get("of")
    if _repeats(entry) and _is_choice(held):
        return 2
    return SCHEMAS.start


def required_schema(data: Any) -> int:
    """The lowest schema that builds a description.

    What a producer stamps. Asking rather than remembering is what keeps the
    `schema` key honest: this dialect is read and never written, so the number
    is a claim the writer makes about its own output, and nothing downstream
    audits it. A generated file whose stamp is below what it uses still builds
    on a new enough reader and fails on an older one with a message about a
    node, which is the confusion `supports` exists to prevent.

    It detects spellings, not meanings. A schema that changed what an existing
    spelling *does* -- different default sizing, say -- leaves a description
    textually identical, so this returns the older number and says nothing. For
    that class the guard is a golden file, not a version number.

    Nothing here validates. A description this cannot build gets an answer
    anyway, because the question is what spellings it uses rather than whether
    they are used correctly; `build` is what says no.

    Args:
        data: The decoded JSON. The whole envelope, or any part of one.

    Returns:
        The lowest schema in `SCHEMAS` that reads it.
    """
    needed = SCHEMAS.start
    pending: list[Any] = [data]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            needed = max(needed, _needs(item))
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return needed


def supports(schema: int) -> bool:
    """Whether this release builds a description declaring that schema.

    The question a generator has before it writes one. Asking here is what lets
    it fail with a sentence naming its own remedy -- this py2tosc reads schemas
    1 to 2, and the generator emits 3 -- rather than with a `SchemaError` raised
    from inside a file that is not the thing that is wrong.

    Args:
        schema: The schema number a description declares or would declare.

    Returns:
        True if this release reads it.
    """
    return schema in SCHEMAS


def build(data: Any) -> Document:
    """Build a layout from already-parsed JSON.

    The tree is built, every `connect` is pointed at the control it named, and
    the whole thing is resolved, so what comes back is sized and ready to save.

    Args:
        data: The decoded JSON.

    Returns:
        The document.

    Raises:
        FormatError: If the envelope is not this dialect, or holds a node that
            cannot be built. The message names the node it gave up on.
        SchemaError: If the description declares a schema this release does not
            read. `supports` answers that before a file is written.
    """
    document = _object(data, "the layout")
    check_keys(document, _ENVELOPE_KEYS, "the layout")

    declared = document.get("format")
    if declared != DIALECT:
        raise FormatError(f"{declared!r} is not a {DIALECT} layout")

    read_schema(document, SCHEMAS, DIALECT)

    if "root" not in document:
        raise FormatError("the layout holds no root node")

    version = document.get("lexml", "6")
    if not isinstance(version, str):
        raise FormatError(f"lexml should be a string, found {describe(version)}")

    deferred: list[_Deferred] = []
    described = _object(document["root"], "root")
    root = _node(described, "root", deferred)

    # Every control type defaults a frame, so the root having one says nothing
    # about whether the layout asked for a canvas. What the file wrote does.
    given = _object(described.get("props", {}), "root.props")
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
        SchemaError: If it declares a schema this release does not read.
    """
    try:
        return build(json.loads(source))
    except json.JSONDecodeError as exc:
        raise FormatError(f"not valid JSON: {exc}") from exc
