"""Optional checks on a layout, for things the format allows but TouchOSC won't like.

Validation is deliberately advisory and never raises. TouchOSC accepts
properties it does not recognise -- that is what makes custom properties useful
-- so a strict schema would reject valid layouts. What this catches instead is
the narrower and more useful case: a property or value that *is* part of the
format but belongs to a different control type, plus the few things TouchOSC
genuinely cannot load.

```python
for issue in doc.validate():
    print(issue)
```

Every rule below is corroborated against layouts the TouchOSC editor wrote; see
`tests/test_validate.py`, which requires every editor-written file in the corpus
to validate without errors.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .control import Control
from .defaults import allowed_properties, default_values_for
from .enums import ControlType, PartialType
from .errors import Py2ToscError
from .messages import GamepadMessage, LocalMessage
from .properties import KNOWN_TYPES

if TYPE_CHECKING:  # pragma: no cover
    from .document import Document

__all__ = ["Issue", "ValidationError", "validate"]

#: The only control types the editor nests children inside.
CONTAINERS = frozenset({ControlType.GROUP, ControlType.PAGER, ControlType.GRID})

#: Connection field widths the format has used, by message. Network bindings
#: went from five slots in lexml 3 to ten in 6; gamepads went from five to four,
#: because the field counts controllers rather than connections.
CONNECTION_WIDTHS = frozenset({5, 10})
GAMEPAD_CONNECTION_WIDTHS = frozenset({4, 5})

#: Keys the format stores under more than one type, so a mismatch means nothing.
#: `gridX`/`gridY` are element counts on a GRID and on/off switches on an XY or
#: RADAR, which is why they are absent from `KNOWN_TYPES` reasoning too.
AMBIGUOUS_TYPES = frozenset({"gridX", "gridY"})

ERROR = "error"
WARNING = "warning"


@dataclass(frozen=True)
class Issue:
    """One finding from [`validate`][py2tosc.validate].

    Attributes:
        level: `error` for something TouchOSC cannot load, `warning` for
            something it tolerates but probably did not intend.
        path: Slash-separated control names from the root, for locating it.
        message: What is wrong.
    """

    level: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.path}: {self.message}"


class ValidationError(Py2ToscError):
    """Raised by `save(validate=True)` when a layout has errors.

    Attributes:
        issues: Every finding, not only the errors, so a caller catching this
            can report the warnings too.
    """

    def __init__(self, issues: list[Issue]):
        self.issues = issues
        errors = [i for i in issues if i.level == ERROR]
        super().__init__(
            f"{len(errors)} error(s) in the layout:\n"
            + "\n".join(f"  {i}" for i in errors)
        )


def _path(trail: list[str]) -> str:
    return "/".join(trail) or "<root>"


def _check_destination(
    message: LocalMessage, destination: Control, here: str
) -> Iterator[Issue]:
    """Check that a local message writes something the destination actually has.

    A binding whose `dst_var` names nothing on the destination is delivered and
    then discarded -- the layout loads, round-trips and looks entirely well
    formed while that control never moves. All 358 resolvable local messages in
    the corpus address something real, so this fires on nothing the editor
    wrote.

    A blank `dst_var` is left alone for the same reason a blank `dst_id` is:
    the editor writes half-configured bindings while you are setting one up.
    """
    if not message.dst_var:
        return

    # `color.a` addresses one component of a property, so only the root has to
    # exist. The corpus writes two of those.
    root = message.dst_var.split(".", 1)[0]
    kind = destination.control_type

    if str(message.dst_type) == str(PartialType.VALUE):
        carried = {key for key, _ in default_values_for(kind)}
        if root not in carried:
            yield Issue(
                WARNING,
                here,
                f"LocalMessage writes value {message.dst_var!r} on a "
                f"{kind.value}, which carries {', '.join(sorted(carried))}",
            )
    elif str(message.dst_type) == str(PartialType.PROPERTY) and not destination.has(
        root
    ):
        yield Issue(
            WARNING,
            here,
            f"LocalMessage writes property {message.dst_var!r} on a "
            f"{kind.value} that has no such property",
        )


def _check_triggers(control: Control, message: object, here: str) -> Iterator[Issue]:
    """Check that a binding fires on a value the control it sits on has.

    A trigger names the value that fires a message, so one naming a value the
    control does not carry never fires: the layout loads, round-trips and
    validates as well formed while the binding is inert. `ui.labelled` is the
    common way to arrive there, since it returns the group holding a control
    and its caption rather than the control, and a `GROUP` carries `touch` and
    nothing else.

    This rule is the one thing here settled by experiment rather than by the
    corpus, because the corpus says the opposite of what it appears to. The
    editor writes 152 bindings that fire on a value their control does not
    have -- 104 on labels, 48 on grids -- which by the usual standard would
    retire the rule. A layout built to ask TouchOSC directly settles it: two
    labels differing only in their trigger, both written to by the same
    button, and only the one firing on `text` sends anything. The other 152
    are dead in TouchOSC's own examples, and `tests/test_validate.py` names
    the files rather than tolerating them.
    """
    carried = _carried(control)
    for trigger in getattr(message, "triggers", None) or []:
        if trigger.var and trigger.var not in carried:
            yield Issue(
                WARNING,
                here,
                f"{type(message).__name__} fires on value {trigger.var!r} on a "
                f"{control.control_type.value}, which carries "
                f"{', '.join(sorted(carried))}",
            )


def _carried(control: Control) -> set[str]:
    """The values a control has, as far as the document says.

    A file may omit `<values>` altogether, and decoding deliberately does not
    fill in a type's defaults, so an empty list means unstated rather than
    none -- 11 faders in the corpus are written that way.
    """
    return {value.key for value in control.values} or {
        key for key, _ in default_values_for(control.control_type)
    }


def _check_source(
    message: LocalMessage, control: Control, here: str
) -> Iterator[Issue]:
    """Check that a local message sends a value the control it sits on has.

    The mirror of `_check_destination`, and the same failure: a binding that
    reads nothing sends nothing, while the layout stays well formed. All 361
    local bindings in the corpus that send a value send one their control
    carries.

    A local message sends a constant or a property just as readily, and those
    say nothing about the control's values, so only a `VALUE` source is
    checked.
    """
    if str(message.type) != str(PartialType.VALUE) or not message.value:
        return

    carried = _carried(control)
    if message.value.split(".", 1)[0] not in carried:
        yield Issue(
            WARNING,
            here,
            f"LocalMessage sends value {message.value!r} from a "
            f"{control.control_type.value}, which carries "
            f"{', '.join(sorted(carried))}",
        )


def _check_reads(control: Control, message: object, here: str) -> Iterator[Issue]:
    """Check that what a binding sends is read from a value the control has.

    The other half of the trigger rule, and the worse half. A trigger that
    names a value the control does not carry fires nothing; an argument that
    reads one is sent anyway, as `0`. So a binding that looks dead is not
    silent -- it transmits a plausible number to whatever is listening, which
    a synth on the other end has no way to tell from an instruction.

    Both were watched going out of TouchOSC from the same layout: two labels
    differing only in their trigger, and the one that fired sent `FLOAT(0)`
    for the `x` a label does not have.

    An OSC address, a MIDI slot and an OSC argument all read the same way, so
    all three are checked. A constant, a property or an index says nothing
    about the control's values and is left alone.
    """
    carried = _carried(control)
    read = (
        list(getattr(message, "path", None) or [])
        + list(getattr(message, "arguments", None) or [])
        + list(getattr(message, "values", None) or [])
    )

    for partial in read:
        if str(partial.type) != str(PartialType.VALUE):
            continue
        # A `Partial` holds the key it reads in `value`; a `MidiValue` in `key`.
        key = getattr(partial, "value", None) or getattr(partial, "key", None)
        if not key or key.split(".", 1)[0] in carried:
            continue
        yield Issue(
            WARNING,
            here,
            f"{type(message).__name__} reads value {key!r} on a "
            f"{control.control_type.value}, which carries "
            f"{', '.join(sorted(carried))}",
        )


def _check_control(
    control: Control, trail: list[str], known: dict[str, Control]
) -> Iterator[Issue]:
    here = _path(trail)
    kind = control.control_type
    allowed = allowed_properties(kind)

    for key, prop in sorted(control.properties.items()):
        declared = None if key in AMBIGUOUS_TYPES else KNOWN_TYPES.get(key)
        if declared is not None and prop.type is not declared:
            yield Issue(
                ERROR,
                here,
                f"property {key!r} is stored as type {prop.type.value!r}, "
                f"but the format defines it as {declared.value!r}",
            )
        # A key the format defines, on a control type that has no use for it.
        # Unknown keys are left alone: custom properties are a feature.
        elif key in KNOWN_TYPES and key not in allowed:
            yield Issue(
                WARNING,
                here,
                f"property {key!r} belongs to the format but not to {kind.value} controls",
            )
        # A custom property named after one of the control's own values, which
        # is what `label.text = "hi"` produces: a label says what its `text`
        # *value* holds, so the property is written, ignored, and draws as
        # nothing. Custom properties are a feature, so nothing else reports it
        # -- but a key that collides with a value the control already has is
        # the one custom property that is never deliberate. No control in the
        # corpus has one.
        elif key not in KNOWN_TYPES and any(v.key == key for v in control.values):
            yield Issue(
                WARNING,
                here,
                f"custom property {key!r} has the same name as this control's "
                f"{key!r} value; TouchOSC reads the value, so setting the "
                f"property has no effect",
            )

    expected_values = {key for key, _ in default_values_for(kind)}
    for value in control.values:
        if value.key not in expected_values:
            yield Issue(
                WARNING,
                here,
                f"value {value.key!r} is not one a {kind.value} carries "
                f"({', '.join(sorted(expected_values))})",
            )

    for message in control.messages:
        connections = getattr(message, "connections", None)
        widths = (
            GAMEPAD_CONNECTION_WIDTHS
            if isinstance(message, GamepadMessage)
            else CONNECTION_WIDTHS
        )
        if connections is not None and len(connections) not in widths:
            yield Issue(
                WARNING,
                here,
                f"{type(message).__name__} connections is {len(connections)} "
                f"characters; the format uses {' or '.join(map(str, sorted(widths)))}",
            )
        # No rule about empty triggers: the editor writes send-enabled OSC
        # bindings with none, 40 times across the corpus, so whatever that
        # means it is not a mistake.
        yield from _check_triggers(control, message, here)
        yield from _check_reads(control, message, here)
        if isinstance(message, GamepadMessage) and not message.target_var:
            yield Issue(WARNING, here, "GamepadMessage has no target_var to write to")
        # A LocalMessage addresses its destination by node id, and a stale one
        # still looks valid: the message is simply never delivered. Reminting
        # ids without re-pointing the bindings is the usual way to get here.
        #
        # An empty dst_id is left alone. That is a binding the user added and
        # has not filled in yet, and the editor writes them -- five times
        # across the corpus -- so it is a normal intermediate state rather than
        # a mistake. Only a destination that names something is checked.
        if isinstance(message, LocalMessage):
            yield from _check_source(message, control, here)
        if isinstance(message, LocalMessage) and message.dst_id:
            destination = known.get(message.dst_id)
            if destination is None:
                yield Issue(
                    WARNING,
                    here,
                    f"LocalMessage is addressed to node id {message.dst_id!r}, "
                    f"which no control in this layout has",
                )
            else:
                yield from _check_destination(message, destination, here)

    # Reported because the tree in hand is unplaced, not because the file would
    # be: `save` places what nobody resolved. But an unset frame reads back as
    # (0, 0, 0, 0) rather than raising, so anything reading frames before then
    # -- this checker included -- is looking at coordinates that mean nothing.
    spec = getattr(control, "_layout", None)
    if spec is not None and not spec.resolved:
        yield Issue(
            WARNING,
            here,
            f"{spec.kind} layout was never resolved, so its "
            f"{len(control.children)} children still read as (0, 0, 0, 0); "
            f"saving places them, or call Document.resolve() to do it now",
        )

    # A GRID is never empty in TouchOSC: creating one populates it, and its
    # `gridX`/`gridY` say how many cells it holds rather than describing
    # something to be filled in later. All 37 in the corpus hold exactly
    # `gridX * gridY` children, and none holds none.
    if kind is ControlType.GRID:
        cells = int(control.get("gridX") or 0) * int(control.get("gridY") or 0)
        if len(control.children) != cells:
            yield Issue(
                WARNING,
                here,
                f"GRID is {control.get('gridX')}x{control.get('gridY')}, so it "
                f"should hold {cells} controls, but it holds "
                f"{len(control.children)}",
            )

    if control.children and kind not in CONTAINERS:
        yield Issue(
            ERROR,
            here,
            f"{kind.value} controls cannot hold children; this one has "
            f"{len(control.children)}",
        )

    if kind is ControlType.PAGER:
        for child in control.children:
            if child.control_type is not ControlType.GROUP:
                yield Issue(
                    WARNING,
                    here,
                    f"PAGER pages should be GROUP controls, found {child.control_type.value}",
                )

    for child in control.children:
        yield from _check_control(
            child,
            [*trail, child.get("name") or f"<{child.control_type.value}>"],
            known,
        )


def validate(target: Control | Document) -> list[Issue]:
    """Check a control tree for things TouchOSC will reject or ignore.

    Args:
        target: A [`Document`][py2tosc.Document] or any
            [`Control`][py2tosc.Control]; a control is checked along with
            everything beneath it.

    Local message destinations are resolved against `target` and nothing above
    it, so validating a subtree that is wired to a control outside itself
    reports a destination it cannot see. Validate the whole
    [`Document`][py2tosc.Document] to avoid that.

    Returns:
        Every finding, errors first, then in tree order. An empty list means
        nothing was found -- it is not a guarantee the layout opens.
    """
    root = target if isinstance(target, Control) else target.root
    name = str(root.get("name") or "<root>")

    known = {control.id: control for control in root.walk()}
    issues = list(_check_control(root, [name], known))

    # The root node is the canvas, and TouchOSC gives it none of the behaviour
    # its type would otherwise have: a PAGER there draws its tab bar but never
    # pages, stacking every child instead. All 35 layouts in the corpus root at
    # a GROUP, and no PAGER appears above depth 1. Only checked for a document,
    # since validating a subtree says nothing about what sits at the top of it.
    if not isinstance(target, Control) and root.control_type is not ControlType.GROUP:
        issues.append(
            Issue(
                WARNING,
                name,
                f"the root is a {root.control_type.value}; TouchOSC treats the "
                f"root as a plain container, so put it inside a GROUP instead",
            )
        )

    # Node ids must be unique across the whole layout, so this cannot be done
    # per control.
    counts = Counter(control.id for control in root.walk())
    for node_id, count in sorted(counts.items()):
        if count > 1:
            issues.append(
                Issue(ERROR, name, f"node id {node_id} is used by {count} controls")
            )

    issues.sort(key=lambda i: i.level != ERROR)
    return issues
