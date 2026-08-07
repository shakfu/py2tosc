"""Arrange children inside a parent control.

Each function creates controls, sizes them to fill the parent's frame, tints
them along a gradient, appends them to the parent and returns them. The frames
are computed in plain arithmetic -- no numpy.

```python
panel = py2tosc.group(frame=(0, 0, 800, 600))
faders = py2tosc.layout.row(panel, "FADER", sizes=8, colors=("#264653", "#e76f51"))
```
"""

from __future__ import annotations

from collections.abc import Sequence

from ._geometry import ratios as _ratios
from ._geometry import spans as _spans
from .control import Control
from .enums import ControlType
from .properties import Color, to_color

__all__ = ["column", "gradient", "matrix", "row"]

_DEFAULT_COLORS = ((0.25, 0.25, 0.25, 1.0), (0.25, 0.25, 0.25, 1.0))


def gradient(start: object, end: object, count: int) -> list[Color]:
    """Interpolate `count` colours between two endpoints.

    Args:
        start: The first colour, in any notation [`to_color`][py2tosc.to_color]
            accepts.
        end: The last colour.
        count: How many colours to produce. Must be at least 1.

    Returns:
        The interpolated colours, `start` first and `end` last.

    Raises:
        ValueError: If `count` is less than 1.
    """
    if count < 1:
        raise ValueError(f"a gradient needs at least 1 colour, asked for {count}")
    first, last = to_color(start), to_color(end)
    if count == 1:
        return [first]
    step = 1 / (count - 1)
    return [
        Color(*(a + (b - a) * (i * step) for a, b in zip(first, last)))
        for i in range(count)
    ]


def _build(
    parent: Control,
    control_type: ControlType | str,
    frames: Sequence[tuple[float, float, float, float]],
    colors: tuple[object, object] | None,
) -> list[Control]:
    palette = gradient(*(colors or _DEFAULT_COLORS), len(frames))
    children = [
        Control(control_type, frame=frame, color=color)
        for frame, color in zip(frames, palette)
    ]
    parent.add(*children)
    return children


def column(
    parent: Control,
    control_type: ControlType | str = ControlType.GROUP,
    *,
    sizes: int | Sequence[float] = 3,
    colors: tuple[object, object] | None = None,
) -> list[Control]:
    """Stack controls vertically, filling the parent's frame.

    Args:
        parent: The control to fill. Its frame sets the available space.
        control_type: The type of control to create.
        sizes: How many slots, or their relative heights. `(1, 2, 1)` makes
            three rows where the middle one is twice as tall.
        colors: Two endpoints for a top-to-bottom gradient.

    Returns:
        The created controls, top to bottom, already added to `parent`.
    """
    _, _, w, h = parent.frame
    frames = [(0, y, w, height) for y, height in _spans(h, _ratios(sizes))]
    return _build(parent, control_type, frames, colors)


def row(
    parent: Control,
    control_type: ControlType | str = ControlType.GROUP,
    *,
    sizes: int | Sequence[float] = 3,
    colors: tuple[object, object] | None = None,
) -> list[Control]:
    """Lay controls out horizontally, filling the parent's frame.

    Args:
        parent: The control to fill. Its frame sets the available space.
        control_type: The type of control to create.
        sizes: How many slots, or their relative widths.
        colors: Two endpoints for a left-to-right gradient.

    Returns:
        The created controls, left to right, already added to `parent`.
    """
    _, _, w, h = parent.frame
    frames = [(x, 0, width, h) for x, width in _spans(w, _ratios(sizes))]
    return _build(parent, control_type, frames, colors)


def matrix(
    parent: Control,
    control_type: ControlType | str = ControlType.GROUP,
    *,
    columns: int = 4,
    rows: int = 4,
    colors: tuple[object, object] | None = None,
    direction: str = "horizontal",
) -> list[Control]:
    """Tile controls in a grid, filling the parent's frame.

    Args:
        parent: The control to fill. Its frame sets the available space.
        control_type: The type of control to create.
        columns: How many columns.
        rows: How many rows.
        colors: Two endpoints for the gradient.
        direction: How the gradient runs across the grid -- `horizontal`,
            `vertical` or `sequential`, the last running cell by cell in
            row-major order.

    Returns:
        The created controls in row-major order, already added to `parent`.

    Raises:
        ValueError: If `direction` is not one of the three accepted values.
    """
    if direction not in ("horizontal", "vertical", "sequential"):
        raise ValueError(f"{direction!r} is not a valid gradient direction")

    _, _, w, h = parent.frame
    x_spans = _spans(w, _ratios(columns))
    y_spans = _spans(h, _ratios(rows))

    frames = [(x, y, width, height) for y, height in y_spans for x, width in x_spans]

    start, end = colors or _DEFAULT_COLORS
    match direction:
        case "horizontal":
            palette = gradient(start, end, columns) * rows
        case "vertical":
            palette = [c for c in gradient(start, end, rows) for _ in range(columns)]
        case _:
            palette = gradient(start, end, columns * rows)

    children = [
        Control(control_type, frame=frame, color=color)
        for frame, color in zip(frames, palette)
    ]
    parent.add(*children)
    return children
