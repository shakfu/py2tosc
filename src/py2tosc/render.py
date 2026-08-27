"""A layout drawn as SVG, for looking at rather than for loading.

Every other emitter here produces something TouchOSC can open. This one
produces a picture, and it exists because layout defects are visual and
nothing in the test suite can see them: a `sizes` that divides wrongly, a
`gap` that eats a row and a `labelled` that mis-splits are all assertable
today only as coordinates, one frame at a time.

```python
doc = py2tosc.load("mixer.tosc")
Path("mixer.svg").write_text(py2tosc.to_svg(doc))
```

It is one way, always. A picture has no `id`, no bindings and no script, so
nothing here reads SVG back, and this is not a `convert` target -- `convert`
means the same layout in another encoding, and implies the reverse works.

**The bar is stated rather than measured.** TouchOSC is the only thing that
knows what a layout really looks like and it cannot be scripted, so what this
promises is that a reader can see where every control is, how big it is and
what kind it is. Not that it matches a screenshot. Anyone who wants the second
thing is starting a different project.

Two consequences of that worth knowing. A control's Lua script can set any
property at runtime, so what is drawn is the document -- the state before
anything ran. And the type-specific marks are chosen to be recognisable rather
than faithful: a fader's bar is where the fader's value is, not where TouchOSC
would paint it to the pixel.

The geometry is free. Frames in this format are relative to the parent, so the
control tree maps onto nested `<g transform="translate(x, y)">` one node for
one node, and nothing here does coordinate arithmetic: `ui.resolve` has already
done the part that is hard.

Being a picture of what `py2tosc.ui` and the controls describe rather than a
part of the format, this module is provisional under the
[stability policy](https://shakfu.github.io/py2tosc/stability/). What it draws
will want changing once anyone looks at real output.
"""

from __future__ import annotations

import math
from typing import Any
from xml.sax.saxutils import escape, quoteattr

from .control import Control
from .document import Document
from .enums import ControlType, Shape
from .properties import Color, Frame

__all__ = ["PAGE_STYLE", "STYLESHEET", "to_html", "to_svg"]

#: What separates one page of a pager from the next when they are laid out
#: side by side. A page nobody can see is a page nobody reviews, which is why
#: they fan out here rather than stacking the way they do on a tablet.
PAGE_GAP = 12

#: What every class this emits begins with. An SVG used inline in a page shares
#: that page's cascade, so a bare `.bar` would reach into someone else's markup.
PREFIX = "p2t"

#: The rules, embedded rather than linked so the file still travels alone and
#: still draws through an `<img src>`. Per-control data arrives as custom
#: properties on the element, which is what keeps a value addressable rather
#: than resolved away into coordinates -- see `--v` on a fader.
#:
#: A shape's fill is deliberately not opaque, and this is the one place
#: legibility is chosen over fidelity on purpose. Every control the layout
#: combinators build carries the same default colour with `background` and
#: `outline` both on, so painting them faithfully composites twenty-seven
#: controls into one flat rectangle -- which fails the only thing this
#: promises, that a reader can see where each control is. At partial fill the
#: stroke reads against it and nesting shows as density.
STYLESHEET = f"""
.{PREFIX}-shape {{
    fill: var(--fill, none);
    fill-opacity: 0.45;
    stroke: var(--line, none);
}}
.{PREFIX}-shape.{PREFIX}-outlined {{ stroke-width: 2; }}
.{PREFIX}-shape.{PREFIX}-track {{ fill-opacity: 0.15; }}
.{PREFIX}-mark {{ stroke: var(--line, #888); stroke-width: 1; fill: none; }}
.{PREFIX}-bar {{
    fill: var(--line, #888);
    fill-opacity: 0.55;
    transform-box: fill-box;
    transform-origin: bottom;
    transform: scaleY(var(--v, 0));
}}
.{PREFIX}-bar.{PREFIX}-across {{
    transform-origin: left;
    transform: scaleX(var(--v, 0));
}}
/* The handle, and the reason a fader at zero is still legible: it has real
   thickness and rides `--v` up the track, where a bar scaled to nothing
   leaves an empty box. `--span` is the travel, which is static. */
.{PREFIX}-cursor {{
    fill: var(--line, #888);
    transform: translateY(calc((1 - var(--v, 0)) * var(--span, 0px)));
}}
.{PREFIX}-cursor.{PREFIX}-across {{
    transform: translateX(calc(var(--v, 0) * var(--span, 0px)));
}}
.{PREFIX}-rule {{ stroke: var(--line, #888); stroke-width: 1; opacity: 0.35; }}
.{PREFIX}-step {{ fill: var(--line, #888); fill-opacity: 0.55; }}
.{PREFIX}-page-name {{ fill: #888; }}
.{PREFIX}-cap {{ fill: none; stroke: var(--line, #888); stroke-width: 1.5; }}
.{PREFIX}-dial {{ fill: none; stroke: var(--line, #888); stroke-width: 2; }}
.{PREFIX}-cross {{ stroke: var(--line, #888); stroke-width: 1; opacity: 0.8; }}
.{PREFIX}-text {{
    fill: var(--ink, #111);
    font-family: var(--face, system-ui, sans-serif);
    dominant-baseline: middle;
}}
.{PREFIX}-hidden {{ opacity: 0.25; }}
.{PREFIX}-hidden .{PREFIX}-shape {{ stroke-dasharray: 4 3; }}
"""


def _n(value: float) -> str:
    """One number, without the trailing zero that makes a diff unreadable."""
    rounded = round(float(value), 3)
    whole = int(rounded)
    return str(whole) if rounded == whole else str(rounded)


def _channel(component: float) -> int:
    """One colour component as CSS wants it, with what a file may hold clamped.

    `o_custom.xml` in the corpus carries ninety `inf` components, written by
    some TouchOSC build and carried faithfully by every codec here since. A
    codec has to reproduce that; a picture has to draw something, so this
    clamps rather than refusing, and a NaN reads as nothing rather than as a
    crash halfway through a layout.
    """
    if math.isnan(component):
        return 0
    if math.isinf(component):
        return 255 if component > 0 else 0
    return max(0, min(255, round(component * 255)))


def _color(value: Any, fallback: str = "none") -> str:
    """One colour as CSS. Alpha is carried, since a layout uses it."""
    if not isinstance(value, Color):
        return fallback
    channels = ", ".join(str(_channel(component)) for component in value[:3])
    alpha = 0.0 if math.isnan(value.a) else max(0.0, min(1.0, value.a))
    return f"rgba({channels}, {_n(alpha)})"


def _frame(control: Control) -> Frame:
    found = control.get("frame")
    return found if isinstance(found, Frame) else Frame(0.0, 0.0, 0.0, 0.0)


def _value(control: Control, key: str, fallback: float = 0.0) -> float:
    """What one of a control's values starts at, for the bits that show it."""
    for held in control.values:
        if held.key == key and isinstance(held.default, (int, float)):
            return float(held.default)
    return fallback


def _text(control: Control) -> str:
    for held in control.values:
        if held.key == "text" and isinstance(held.default, str):
            return held.default
    return ""


def _polygon(sides: int, w: float, h: float) -> str:
    """A regular polygon inscribed in the frame, point upwards.

    Approximate on purpose. TouchOSC's exact vertex placement is not published
    and this is a picture, so a pentagon that reads as a pentagon is the whole
    requirement.
    """
    step = 2 * math.pi / sides
    points = []
    for index in range(sides):
        angle = -math.pi / 2 + index * step
        points.append(
            f"{_n(w / 2 + math.cos(angle) * w / 2)},"
            f"{_n(h / 2 + math.sin(angle) * h / 2)}"
        )
    return " ".join(points)


def _shape(control: Control, frame: Frame, classes: str) -> str:
    """The outline a control is drawn as, from its `shape` property."""
    w, h = frame.w, frame.h
    kind = control.get("shape")
    radius = control.get("cornerRadius")
    rounded = (
        f' rx="{_n(radius)}"' if isinstance(radius, (int, float)) and radius else ""
    )

    if kind == Shape.CIRCLE.value:
        return (
            f'<ellipse class={quoteattr(classes)} cx="{_n(w / 2)}" '
            f'cy="{_n(h / 2)}" rx="{_n(w / 2)}" ry="{_n(h / 2)}"/>'
        )
    for shape, sides in (
        (Shape.TRIANGLE, 3),
        (Shape.DIAMOND, 4),
        (Shape.PENTAGON, 5),
        (Shape.HEXAGON, 6),
    ):
        if kind == shape.value:
            points = _polygon(sides, w, h)
            return f'<polygon class={quoteattr(classes)} points="{points}"/>'
    return (
        f'<rect class={quoteattr(classes)} x="0" y="0" '
        f'width="{_n(w)}" height="{_n(h)}"{rounded}/>'
    )


def _el(tag: str, klass: str, **attrs: Any) -> str:
    """One SVG element, written so a mark reads as the shape it draws."""
    written = " ".join(
        f'{key.replace("_", "-")}="{value}"' for key, value in attrs.items()
    )
    return f'<{tag} class="{klass}" {written}/>'


def _rules(control: Control, w: float, h: float, across: bool | None) -> list[str]:
    """The division lines a control draws across itself.

    A fader's `grid` with its `gridSteps`, and an XY's `gridX`/`gridY`. Faint,
    because they are the thing a control is measured against rather than the
    thing it says.
    """
    drawn = []
    both = across is None
    steps = control.get("gridSteps") if not both else None
    count = steps if isinstance(steps, int) and steps > 1 else 8

    if both or not across:
        for index in range(1, count):
            at = _n(h * index / count)
            drawn.append(_el("line", f"{PREFIX}-rule", x1=0, y1=at, x2=_n(w), y2=at))
    if both or across:
        for index in range(1, count):
            at = _n(w * index / count)
            drawn.append(_el("line", f"{PREFIX}-rule", x1=at, y1=0, x2=at, y2=_n(h)))
    return drawn


def _marks(control: Control, frame: Frame) -> list[str]:
    """What makes a control recognisable as its kind rather than a rectangle.

    The half of this module's promise that costs something. Where a control is
    and how big it is falls out of the frames; *what it is* has to be drawn,
    and a layout whose controls all carry the same default colour -- which is
    every layout the combinators build -- has nothing else to say it.

    These are recognisable rather than faithful. A dial here is an open ring
    with a tick, because that reads as a dial; it is not where TouchOSC would
    put the pixels.
    """
    kind = control.control_type
    w, h = frame.w, frame.h
    mid_x, mid_y = _n(w / 2), _n(h / 2)
    across = control.get("orientation") in (1, 3)

    if kind is ControlType.FADER:
        # The value rides a custom property rather than the geometry, so the
        # bar and the handle can be driven later without the rule for where
        # they go existing twice, once here and once in whatever drives them.
        drawn = []
        if control.get("grid") is True:
            drawn += _rules(control, w, h, across)
        if control.get("bar") is not False:
            klass = f"{PREFIX}-bar {PREFIX}-across" if across else f"{PREFIX}-bar"
            drawn.append(_el("rect", klass, x=0, y=0, width=_n(w), height=_n(h)))
        if control.get("cursor") is not False:
            klass = f"{PREFIX}-cursor {PREFIX}-across" if across else f"{PREFIX}-cursor"
            thick = max(min(w, h) * 0.09, 3)
            drawn.append(
                _el("rect", klass, x=0, y=_n(h - thick), width=_n(w), height=_n(thick))
                if not across
                else _el("rect", klass, x=0, y=0, width=_n(thick), height=_n(h))
            )
        return drawn

    if kind is ControlType.BUTTON:
        # An inset cap, so a button is not the same drawing as a box.
        inset = min(w, h) * 0.18
        return [
            _el(
                "rect",
                f"{PREFIX}-cap",
                x=_n(inset),
                y=_n(inset),
                width=_n(max(w - inset * 2, 0)),
                height=_n(max(h - inset * 2, 0)),
                rx=_n(inset),
            )
        ]

    if kind is ControlType.RADIO:
        steps = control.get("steps")
        count = steps if isinstance(steps, int) and steps > 1 else 2
        span = w if across else h
        # Which step it is on, filled. Without it a radio at the first step and
        # one at the last are the same drawing, which is the defect the fader
        # had at zero.
        chosen = min(int(_value(control, "x") * count), count - 1)
        at = _n(span * chosen / count)
        drawn = [
            _el(
                "rect",
                f"{PREFIX}-step",
                x=at,
                y=0,
                width=_n(span / count),
                height=_n(h),
            )
            if across
            else _el(
                "rect",
                f"{PREFIX}-step",
                x=0,
                y=at,
                width=_n(w),
                height=_n(span / count),
            )
        ]
        for index in range(1, count):
            edge = _n(span * index / count)
            drawn.append(
                _el("line", f"{PREFIX}-mark", x1=edge, y1=0, x2=edge, y2=_n(h))
                if across
                else _el("line", f"{PREFIX}-mark", x1=0, y1=edge, x2=_n(w), y2=edge)
            )
        return drawn

    if kind is ControlType.XY:
        lines = []
        if control.get("gridX") is True or control.get("gridY") is True:
            lines = _rules(control, w, h, across=None)
        return lines + [
            _el("line", f"{PREFIX}-cross", x1=0, y1=mid_y, x2=_n(w), y2=mid_y),
            _el("line", f"{PREFIX}-cross", x1=mid_x, y1=0, x2=mid_x, y2=_n(h)),
            _el(
                "circle",
                f"{PREFIX}-dial",
                cx=mid_x,
                cy=mid_y,
                r=_n(min(w, h) * 0.12),
            ),
        ]

    if kind is ControlType.RADAR:
        rings = [
            _el("circle", f"{PREFIX}-dial", cx=mid_x, cy=mid_y, r=_n(min(w, h) * r / 2))
            for r in (0.35, 0.7, 0.95)
        ]
        return rings + [
            _el("line", f"{PREFIX}-cross", x1=mid_x, y1=mid_y, x2=_n(w), y2=mid_y)
        ]

    if kind in (ControlType.ENCODER, ControlType.RADIAL):
        # An open ring with a tick at the top reads as a dial, and reads as a
        # different thing from a radar, which is the whole job.
        radius = min(w, h) * 0.36
        sweep = (
            f"M {_n(w / 2 - radius * 0.7)} {_n(h / 2 + radius * 0.7)} "
            f"A {_n(radius)} {_n(radius)} 0 1 1 "
            f"{_n(w / 2 + radius * 0.7)} {_n(h / 2 + radius * 0.7)}"
        )
        return [
            _el("path", f"{PREFIX}-dial", d=sweep),
            _el(
                "line",
                f"{PREFIX}-dial",
                x1=mid_x,
                y1=_n(h / 2 - radius),
                x2=mid_x,
                y2=mid_y,
            ),
        ]

    if kind in (ControlType.LABEL, ControlType.TEXT):
        shown = _text(control)
        if not shown:
            return []
        size = control.get("textSize")
        height = size if isinstance(size, (int, float)) and size else 14
        # One line, clipped. TEXT wraps in TouchOSC and SVG has no wrapping;
        # a box with its first line in it still says where the control is.
        first = shown.splitlines()[0]
        return [
            (
                f'<text class="{PREFIX}-text" x="{mid_x}" y="{mid_y}" '
                f'text-anchor="middle" font-size="{_n(height)}">'
                f"{escape(first)}</text>"
            )
        ]

    return []


def _style(control: Control) -> str:
    """The per-control data the stylesheet's rules read."""
    parts = []
    if control.get("background") is not False:
        parts.append(
            f"--fill: {_color(control.get('color'), 'rgba(128,128,128,0.35)')}"
        )
    if control.get("outline") is not False:
        parts.append(f"--line: {_color(control.get('color'), 'rgba(96,96,96,1)')}")
    if control.control_type in (ControlType.FADER, ControlType.RADIO):
        parts.append(f"--v: {_n(_value(control, 'x'))}")
    if control.control_type is ControlType.FADER:
        frame = _frame(control)
        thick = max(min(frame.w, frame.h) * 0.09, 3)
        across = control.get("orientation") in (1, 3)
        travel = (frame.w if across else frame.h) - thick
        parts.append(f"--span: {_n(max(travel, 0))}px")
    if control.control_type in (ControlType.LABEL, ControlType.TEXT):
        parts.append(f"--ink: {_color(control.get('textColor'), 'rgba(20,20,20,1)')}")
    return "; ".join(parts)


def _extent(control: Control, ox: float, oy: float) -> tuple[float, float]:
    """How far right and down the picture actually reaches.

    Everywhere but a pager this is just the frames, and the answer is the root
    -- but a pager's pages are laid out side by side rather than stacked, so
    the drawing is wider than the canvas the layout declares. That fan-out is
    the one place this module does coordinate arithmetic, and it is the price
    of being able to see a page that is not the first.
    """
    frame = _frame(control)
    x, y = ox + frame.x, oy + frame.y
    right, bottom = x + frame.w, y + frame.h

    pages = control.control_type is ControlType.PAGER
    for index, child in enumerate(control.children):
        across = x + index * (frame.w + PAGE_GAP) if pages else x
        far, low = _extent(child, across, y)
        right, bottom = max(right, far), max(bottom, low)
    return right, bottom


def _clip_id(counter: list[int]) -> str:
    """A name for one clip, counted rather than taken from the control's id.

    A control's id is minted fresh on every build, so using it would make two
    renders of one layout differ in their text and nothing could be held to a
    golden file.
    """
    counter[0] += 1
    return f"{PREFIX}-clip-{counter[0]}"


def _node(control: Control, depth: int, clip: bool, counter: list[int]) -> list[str]:
    """One control and everything under it, as its own group."""
    frame = _frame(control)
    pad = "  " * (depth + 1)
    name = control.get("name")

    classes = [f"{PREFIX}-control", f"{PREFIX}-{control.control_type.value.lower()}"]
    if control.get("visible") is False:
        classes.append(f"{PREFIX}-hidden")
    if control.get("script"):
        # A script can set any property at runtime, so what is drawn is the
        # state before it ran. The class says so without drawing anything.
        classes.append(f"{PREFIX}-scripted")

    style = _style(control)
    opened = (
        f"{pad}<g class={quoteattr(' '.join(classes))} "
        f'transform="translate({_n(frame.x)}, {_n(frame.y)})"'
        + (f" data-name={quoteattr(str(name))}" if name else "")
        + (f" style={quoteattr(style)}" if style else "")
        + ">"
    )

    shape_classes = f"{PREFIX}-shape"
    if control.get("outline") is not False:
        shape_classes += f" {PREFIX}-outlined"
    if control.control_type is ControlType.FADER:
        # Otherwise the bar and the shape are the same rectangle in the same
        # colour, and a fader at 0 draws exactly like one at 1.
        shape_classes += f" {PREFIX}-track"

    pages = control.control_type is ControlType.PAGER
    backdrop = f"{pad}  {_shape(control, frame, shape_classes)}"
    # A pager paints its backdrop once per column rather than once, so a page
    # laid out beyond the canvas has the same ground under it as the first.
    out = [opened] if pages else [opened, backdrop]
    out += [f"{pad}  {mark}" for mark in _marks(control, frame)]

    # A pager is never clipped even when clipping is on: its pages are laid
    # out past its own frame on purpose, and clipping to that frame would hide
    # every page but the first. The pages themselves are groups, and are
    # clipped like any other container.
    clipping = clip and bool(control.children) and not pages
    if clipping:
        name = _clip_id(counter)
        out.append(f'{pad}  <clipPath id="{name}">')
        out.append(f"{pad}    {_shape(control, frame, f'{PREFIX}-clip')}")
        out.append(f"{pad}  </clipPath>")
        out.append(f'{pad}  <g clip-path="url(#{name})">')

    if pages:
        # Stacked, every page but the front one is invisible and the layout
        # reads as whichever page happens to be last. Side by side, all of
        # them are reviewable, which is what this is for.
        for index, child in enumerate(control.children):
            across = index * (frame.w + PAGE_GAP)
            label = child.get("name") or f"page {index + 1}"
            out.append(f'{pad}  <g transform="translate({_n(across)}, 0)">')
            out.append(f"  {backdrop}")
            out.append(
                f'{pad}    <text class="{PREFIX}-text {PREFIX}-page-name" '
                f'x="6" y="14" font-size="11">{escape(str(label))}</text>'
            )
            out += _node(child, depth + 2, clip, counter)
            out.append(f"{pad}  </g>")
    else:
        for child in control.children:
            out += _node(child, depth + 1, clip, counter)

    if clipping:
        out.append(f"{pad}  </g>")
    out.append(f"{pad}</g>")
    return out


def to_svg(doc: Document, *, clip: bool = False) -> str:
    """Draw one layout as SVG.

    Args:
        doc: The layout. Resolve it first if it was built by `py2tosc.ui`;
            what is drawn is whatever frames the controls carry.
        clip: Whether a control is cut off at the edge of the one holding it,
            the way TouchOSC draws it. Off by default, and the default is the
            decision: a control that overflows its parent is exactly the kind
            of defect a picture is being drawn to find, and clipping hides it
            behind a layout that looks correct. Turn it on to see what the
            device will actually show. A pager is never clipped either way,
            since its pages are laid out past its own frame on purpose.

    Returns:
        The SVG, as text.
    """
    width, height = _extent(doc.root, 0.0, 0.0)
    out = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {_n(width)} {_n(height)}" '
            f'width="{_n(width)}" height="{_n(height)}">'
        ),
        f"  <style>{STYLESHEET}  </style>",
    ]
    out += _node(doc.root, 0, clip, [0])
    out.append("</svg>")
    return "\n".join(out) + "\n"


#: The page's own rules, which style what is around the picture rather than the
#: picture. Kept apart from `STYLESHEET` for that reason: one travels inside the
#: SVG wherever it goes, and this one only applies when there is a page.
PAGE_STYLE = """
:root { color-scheme: light dark; }
body {
    margin: 0;
    padding: 1.5rem;
    font: 14px/1.5 system-ui, sans-serif;
    background: Canvas;
    color: CanvasText;
}
header { margin: 0 0 1rem; }
h1 { font-size: 1.1rem; margin: 0 0 .25rem; }
.meta { opacity: 0.7; }
.issues { margin: .75rem 0 0; padding-left: 1.1rem; }
.issues li { opacity: 0.85; }
figure { margin: 0; overflow-x: auto; }
svg { max-width: 100%; height: auto; display: block; }
"""


def to_html(doc: Document, *, clip: bool = False) -> str:
    """Draw one layout as a page with the picture in it.

    The same SVG `to_svg` produces, with a page around it -- not a second
    renderer. That is what keeps anything added later, a runtime included,
    additive rather than a second code path to keep in step.

    What the page adds is the context a bare picture has nowhere to put: what
    the layout is called, how many controls it holds, and what `validate` says
    about it. A layout with a control the editor will refuse is worth knowing
    about while looking at the picture rather than afterwards.

    Args:
        doc: The layout, resolved.
        clip: As `to_svg`.

    Returns:
        A complete HTML document, as text.
    """
    name = doc.root.get("name") or "layout"
    controls = len(list(doc.walk()))
    issues = doc.validate()

    reported = ""
    if issues:
        listed = "".join(f"<li>{escape(str(issue))}</li>" for issue in issues)
        reported = f'<ul class="issues">{listed}</ul>'

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(str(name))}</title>\n"
        f"<style>{PAGE_STYLE}</style>\n</head>\n<body>\n"
        f"<header>\n<h1>{escape(str(name))}</h1>\n"
        f'<div class="meta">{controls} controls'
        f"{f', {len(issues)} issue(s)' if issues else ''}</div>\n"
        f"{reported}\n</header>\n"
        f"<figure>\n{to_svg(doc, clip=clip)}</figure>\n"
        "</body>\n</html>\n"
    )
