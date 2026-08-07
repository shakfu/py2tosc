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


class ValidationError(Exception):
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
