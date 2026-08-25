"""Frame arithmetic, shared by the eager and the deferred layout APIs.

`layout` sizes children the moment it creates them, which needs a parent that
already has a frame. `ui` describes the arrangement and assigns frames later,
which does not. Both divide a length the same way, so the division lives here
rather than in either of them.

Nothing in this module is public. The layout spec it defines is carried on a
control's `_layout` attribute, which the codec cannot reach: `_write_control`
serializes `properties`, `values`, `messages` and `children` and nothing else,
so a deferred layout never becomes part of a `.tosc` file.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field

from .control import Control
from .enums import Orientation
from .properties import Frame

#: The arrangements a `_layout` can describe.
ROW = "row"
COLUMN = "column"
TILES = "tiles"
STACK = "stack"
PAGES = "pages"
CELLS = "cells"

#: The gap a `GRID` control leaves around and between its cells. It has no
#: property for this -- the editor writes the child frames out -- and every
#: grid in the corpus uses three points, whatever its size or shape.
CELL_MARGIN = 3


def _round(value: float) -> int:
    """Round halves upwards, which is what a `GRID` control does.

    Python rounds halves to even, so it turns 404.5 into 404. The editor writes
    405, and an eight-wide grid in the corpus lands on exactly that boundary.
    """
    return math.floor(value + 0.5)


def ratios(sizes: int | Sequence[float]) -> list[float]:
    """Normalise a slot count or a set of weights into fractions summing to 1."""
    wanted = "sizes takes a number of slots or a list of weights"
    # A string is a sequence of characters, so it would otherwise be read as
    # one weight per character and fail a long way from the call.
    countable = isinstance(sizes, int) and not isinstance(sizes, bool)
    listed = isinstance(sizes, Sequence) and not isinstance(sizes, (str, bytes))
    if not countable and not listed:
        raise ValueError(f"{wanted}, not {sizes!r}")
    try:
        # A bool is an `int` to Python and was refused above, so the narrowing
        # here is the same test `countable` made.
        values = [1.0] * sizes if isinstance(sizes, int) else [float(s) for s in sizes]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{wanted}: {exc}") from exc
    if not values:
        raise ValueError("sizes must describe at least one slot")
    total = sum(values)
    if total <= 0:
        raise ValueError("sizes must add up to a positive number")
    return [v / total for v in values]


def spans(length: float, fractions: Iterable[float]) -> list[tuple[int, int]]:
    """Split `length` into offset and size pairs.

    Each slot ends exactly where the next begins, so rounding never opens a gap
    or an overlap, and the last slot always reaches the end of `length`.

    The length may be fractional, since a frame can be, but the slots are whole
    numbers: a layout with crisp edges is worth more than one that inherits a
    parent's sub-pixel offset.
    """
    result = []
    offset = 0.0
    for fraction in fractions:
        start = round(offset)
        offset += length * fraction
        result.append((start, round(offset) - start))
    return result


def slots(
    length: float,
    fractions: Sequence[float],
    start: int,
    end: int,
    gap: int,
    axis: str,
) -> list[tuple[int, int]]:
    """Offsets and sizes along one axis, inset by `start`/`end`, split by `gap`.

    The invariant `spans` holds has to be restated once slots are separated
    rather than touching: slot *i* ends exactly `gap` before slot *i+1* begins,
    the first begins at `start`, and the last ends at `length - end`.

    Which means the content edge is rounded before the division rather than
    after it. Rounding the available length instead lets a fractional frame
    push the last slot a pixel past its parent, since `round` is applied to a
    span that no longer starts at zero.
    """
    count = len(fractions)
    edge = round(length - end)
    usable = edge - start - gap * (count - 1)
    if usable < 0:
        raise ValueError(
            f"a {axis} of {length:g} cannot hold {count} slots with "
            f"{start}/{end} padding and {gap} between them"
        )
    return [
        (start + index * gap + offset, size)
        for index, (offset, size) in enumerate(spans(usable, fractions))
    ]


def to_pad(value: float | Sequence[float]) -> tuple[int, int, int, int]:
    """Normalise padding to whole pixels, as left, top, right and bottom."""
    if isinstance(value, (int, float)):
        return (round(value),) * 4
    parts = tuple(round(v) for v in value)
    if len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    if len(parts) == 4:
        return parts
    raise ValueError(
        "pad takes a number, a (horizontal, vertical) pair, or four numbers"
    )


def to_gap(value: float | Sequence[float]) -> tuple[int, int]:
    """Normalise a gap to whole pixels, as horizontal and vertical.

    A gap sits between slots, so unlike padding it has no four-sided form.
    """
    if isinstance(value, (int, float)):
        return (round(value), round(value))
    parts = tuple(round(v) for v in value)
    if len(parts) == 2:
        return parts
    raise ValueError("gap takes a number or a (horizontal, vertical) pair")


def to_inset(value: float | Sequence[float]) -> tuple[float, float, float, float]:
    """Normalise an inset to fractions, as left, top, right and bottom.

    Padding is in pixels, which a deferred layout cannot use for anything
    proportional: the size to take a fraction of is not known until the frame
    comes down from above. An inset is kept as a fraction and applied then.
    """
    if isinstance(value, (int, float)):
        return (float(value),) * 4
    parts = tuple(float(v) for v in value)
    if len(parts) == 2:
        return (parts[0], parts[1], parts[0], parts[1])
    if len(parts) == 4:
        return parts
    raise ValueError(
        "inset takes a number, a (horizontal, vertical) pair, or four numbers"
    )


def inset_frame(control: Control, frame: Frame) -> Frame:
    """Shrink a frame by the control's own inset, if it carries one.

    Applied to the frame a parent computed rather than to the control's current
    frame, so resolving twice gives the same answer as resolving once.
    """
    amount = getattr(control, "_inset", None)
    if amount is None:
        return frame
    left, top, right, bottom = amount
    x, y, w, h = frame
    dx, dw = round(w * left), round(w * left) + round(w * right)
    dy, dh = round(h * top), round(h * top) + round(h * bottom)
    if w - dw < 0 or h - dh < 0:
        raise ValueError(f"an inset of {amount} does not fit in {frame}")
    return Frame(x + dx, y + dy, w - dw, h - dh)


@dataclass
class Layout:
    """How a group arranges its children, recorded until frames can be assigned.

    Attributes:
        kind: `row`, `column`, `tiles`, `stack`, `pages` or `cells`. The last
            two are the arrangements a `PAGER` and a `GRID` impose on their own
            children rather than ones a caller picks.
        sizes: Relative weights matching the children, or `None` for equal
            shares. Used only by `row` and `column`.
        columns: How many across, for `tiles` and `cells`.
        rows: How many down, or `None` to take just enough for the children.
        gap: Space between slots, horizontal and vertical.
        pad: Inset before the first slot and after the last, on all four sides.
        resolved: Whether frames have been assigned yet. `validate` reports a
            layout that was never resolved, since its children would otherwise
            be written with whatever frames they happened to be built with.
    """

    kind: str
    sizes: int | Sequence[float] | None = None
    columns: int = 4
    rows: int | None = None
    gap: tuple[int, int] = (0, 0)
    pad: tuple[int, int, int, int] = field(default=(0, 0, 0, 0))
    resolved: bool = False


#: Which edge a pager's tab bar occupies, by its `orientation`, as multipliers
#: for left, top, right and bottom. Read as a clockwise order from the top,
#: which is also the order `pad` and `inset` take their four numbers in.
#:
#: All four are attested. The bundled examples cover three -- `NORTH` on 123
#: pagers, `WEST` on two and `SOUTH` on one -- and never use `EAST`, which was
#: inferred as the only edge left over until `tests/data/pagers.tosc` settled
#: it: one pager per orientation, drawn in the editor, each page frame showing
#: which edge lost its pixels.
#: Keyed by `int` rather than by `Orientation` on purpose: the lookup below
#: takes whatever number the file holds and falls back to the top edge, so a
#: layout carrying an orientation this enum does not name still loads.
_TAB_EDGES: dict[int, tuple[int, int, int, int]] = {
    Orientation.NORTH: (0, 1, 0, 0),  # top
    Orientation.EAST: (0, 0, 1, 0),  # right
    Orientation.SOUTH: (0, 0, 0, 1),  # bottom
    Orientation.WEST: (1, 0, 0, 0),  # left
}


def tab_bar(control: Control, kind: str) -> tuple[int, int, int, int]:
    """How much of a pager each edge loses to its tab bar.

    Zero on every edge unless the control is a pager showing one, which is the
    common case in the corpus: 906 of 1005 pages have the bar switched off and
    fill their pager exactly.
    """
    if kind != PAGES or not control.get("tabbar"):
        return (0, 0, 0, 0)
    bar = round(float(control.get("tabbarSize") or 0))
    edges = _TAB_EDGES.get(int(control.get("orientation") or 0), _TAB_EDGES[0])
    return (edges[0] * bar, edges[1] * bar, edges[2] * bar, edges[3] * bar)


def child_frames(spec: Layout, control: Control, count: int) -> list[Frame]:
    """The frames `spec` gives to `count` children of `control`.

    Frames are relative to the parent, which is what the format stores.

    The control is passed rather than only its frame because a pager has to read
    its own tab bar to know how much room is actually left for a page.
    """
    frame = control.frame
    _, _, width, height = frame
    left, top, right, bottom = spec.pad
    across, down = spec.gap

    if spec.kind in (STACK, PAGES):
        # A pager gives its pages whatever the tab bar leaves, so a page sized
        # to the whole frame would sit underneath it.
        bar_left, bar_top, bar_right, bar_bottom = tab_bar(control, spec.kind)
        filled = Frame(
            left + bar_left,
            top + bar_top,
            width - left - right - bar_left - bar_right,
            height - top - bottom - bar_top - bar_bottom,
        )
        if filled.w < 0 or filled.h < 0:
            raise ValueError(f"padding of {spec.pad} does not fit in {frame}")
        return [filled] * count

    if spec.kind == CELLS:
        # A GRID control tiles its cells itself, and does not divide its frame
        # the way a layout does: every cell is the same size, with a margin all
        # round and between, and whatever will not divide evenly is left over
        # at the far edge rather than shared out.
        columns = spec.columns
        rows = spec.rows if spec.rows is not None else 1
        margin = CELL_MARGIN
        pitch_x = (width - margin) / columns
        pitch_y = (height - margin) / rows
        cell_w, cell_h = _round(pitch_x - margin), _round(pitch_y - margin)
        if cell_w < 0 or cell_h < 0:
            raise ValueError(f"a {columns}x{rows} grid does not fit in {frame}")
        return [
            Frame(
                _round(margin + col * pitch_x),
                _round(margin + row * pitch_y),
                cell_w,
                cell_h,
            )
            for row in range(rows)
            for col in range(columns)
        ]

    if spec.kind == TILES:
        columns = spec.columns
        rows = spec.rows if spec.rows is not None else -(-count // columns)
        across_slots = slots(width, ratios(columns), left, right, across, "width")
        down_slots = slots(height, ratios(rows), top, bottom, down, "height")
        return [Frame(x, y, w, h) for y, h in down_slots for x, w in across_slots]

    fractions = ratios(count if spec.sizes is None else spec.sizes)
    if len(fractions) != count:
        raise ValueError(
            f"{spec.kind} was given {len(fractions)} sizes for {count} children"
        )

    if spec.kind == ROW:
        tall = height - top - bottom
        if tall < 0:
            raise ValueError(f"padding of {spec.pad} does not fit in {frame}")
        return [
            Frame(x, top, w, tall)
            for x, w in slots(width, fractions, left, right, across, "width")
        ]

    wide = width - left - right
    if wide < 0:
        raise ValueError(f"padding of {spec.pad} does not fit in {frame}")
    return [
        Frame(left, y, wide, h)
        for y, h in slots(height, fractions, top, bottom, down, "height")
    ]


def _named(control: Control) -> str:
    """What to call one control in a message, matching `validate`'s paths."""
    return control.get("name") or f"<{control.control_type.value}>"


@contextmanager
def _under(control: Control) -> Iterator[None]:
    """Name this branch on anything that will not divide below it.

    A layout is a tree and its arithmetic is not local -- a row fails because
    of the frame its grandparent handed down -- so the message has to say
    which one, and the path accumulates as the error unwinds.
    """
    try:
        yield
    except ValueError as exc:
        raise ValueError(f"{_named(control)}/{exc}") from exc


def resolve(control: Control, frame: Sequence[float] | None = None) -> Control:
    """Assign frames to everything a layout combinator described.

    Walks the whole tree rather than stopping at controls without a layout, so
    a combinator-built group nested inside a hand-placed one still resolves.

    Args:
        control: The control to place, along with everything beneath it.
        frame: The frame to give `control`. Omitted, it keeps the one it has.

    Returns:
        `control`, placed.

    Raises:
        ValueError: If a layout cannot fit its children into the space it has.
    """
    if frame is not None:
        # `Control.frame` has no setter -- assignment works only because
        # `__setattr__` routes it into `set`, which is the declared path.
        control.set("frame", frame)

    spec = getattr(control, "_layout", None)
    if spec is None:
        for child in control.children:
            with _under(control):
                resolve(child)
        return control

    spec.resolved = True
    if control.children:
        try:
            frames = child_frames(spec, control, len(control.children))
        except ValueError as exc:
            raise ValueError(f"{_named(control)}: {exc}") from exc
        for child, child_frame in zip(control.children, frames):
            with _under(control):
                resolve(child, inset_frame(child, child_frame))
    return control


def resolve_pending(control: Control) -> bool:
    """Place anything still waiting to be placed, and leave the rest alone.

    Saving calls this so that a layout nobody resolved is not written out with
    every child stacked at the origin -- a file that is structurally valid,
    round-trips exactly, and is visibly wrong in TouchOSC.

    Descends until it meets a layout that was never resolved, places that whole
    subtree, and stops. Going no further is the point: re-running a layout that
    was already resolved would discard a frame placed by hand inside it, which
    an explicit `resolve` is still free to do.

    Args:
        control: The control to walk.

    Returns:
        Whether anything was placed.

    Raises:
        ValueError: If a layout cannot fit its children into the space it has.
    """
    spec = getattr(control, "_layout", None)
    if spec is not None and not spec.resolved:
        resolve(control)
        return True
    # Every child is walked: `any` over a generator would stop at the first
    # subtree that needed placing and leave its siblings unplaced.
    placed = False
    for child in control.children:
        placed = resolve_pending(child) or placed
    return placed
