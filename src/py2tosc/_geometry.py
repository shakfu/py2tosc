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

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from .control import Control
from .properties import Frame

#: The arrangements a `_layout` can describe.
ROW = "row"
COLUMN = "column"
GRID = "grid"
STACK = "stack"
PAGES = "pages"


def ratios(sizes: int | Sequence[float]) -> list[float]:
    """Normalise a slot count or a set of weights into fractions summing to 1."""
    values = [1.0] * sizes if isinstance(sizes, int) else [float(s) for s in sizes]
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
        kind: `row`, `column`, `grid` or `stack`.
        sizes: Relative weights matching the children, or `None` for equal
            shares. Unused by `grid` and `stack`.
        columns: Grid width.
        rows: Grid height, or `None` to derive it from the child count.
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
        # A pager draws its tab bar across the top and gives its pages what is
        # left, so a page sized to the whole frame would sit underneath it.
        bar = 0
        if spec.kind == PAGES and control.get("tabbar"):
            bar = round(float(control.get("tabbarSize") or 0))
        filled = Frame(
            left, top + bar, width - left - right, height - top - bottom - bar
        )
        if filled.w < 0 or filled.h < 0:
            raise ValueError(f"padding of {spec.pad} does not fit in {frame}")
        return [filled] * count

    if spec.kind == GRID:
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
            resolve(child)
        return control

    spec.resolved = True
    if control.children:
        frames = child_frames(spec, control, len(control.children))
        for child, child_frame in zip(control.children, frames):
            resolve(child, inset_frame(child, child_frame))
    return control
