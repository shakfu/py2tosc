"""Build a control surface from a list of parameters.

Something else usually knows what should be on a layout -- a plugin's exported
parameter list, a MIDI map, a config file. This turns such a list into a paged
surface with a control per parameter, each bound to MIDI, to OSC, or to both.

```python
from py2tosc import surface

doc = surface.build(surface.read([{"name": "Threshold"}, {"name": "Ratio"}]))
```

It lives in the package rather than in a demo because the command line needs
it: `py2tosc build params.json` is this module with a file reader in front.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from . import layout, ui
from .control import Control, fader, label
from .document import Document
from .messages import Value

__all__ = ["Parameter", "build", "namespace", "read", "slug"]

#: A page of parameters. Four across reads well on a tablet.
COLUMNS, ROWS = 4, 3

#: The design canvas. TouchOSC scales a layout to whatever screen opens it, so
#: this is a coordinate space and an aspect ratio rather than a pixel count --
#: but it is not arbitrary, because font sizes and margins are absolute within
#: it. The templates TouchOSC ships are small and wide: 320x480 portrait
#: (`simple_mk2`, `mix_2_mk2`), 480x320 (`beatmachine_mk2`), 568x320
#: (`automat5_mk2`). A parameter surface is faders side by side, so it wants
#: the landscape one. Pass `frame` to `build`, or `--size` on the command
#: line, for a canvas that suits the device you have.
SIZE = (568, 320)

#: Text size as a fraction of the height of the box holding it. The corpus
#: median is 0.54 over 2867 labels; `simple_mk2` uses 14pt in a 25pt box.
#: Captions are sized from their resolved frame rather than fixed, so that
#: changing the canvas or the page density does not leave the text behind.
TEXT_RATIO = 0.55
TEXT_RANGE = (6, 32)

#: MIDI control change numbers run 0-127. A list can be longer than that, and
#: the parameters past the end simply go out over OSC alone.
CC_LIMIT = 128

GRADIENT = ("#264653", "#e76f51")


@dataclass
class Parameter:
    """One thing to put on the surface.

    Attributes:
        name: What it is called. Shown as the caption, and slugged for the
            control's name, which is what the OSC address is built from.
        cc: The MIDI control change number. `None` takes it from the
            parameter's position in the list, which is almost always what you
            want -- see `read`.
        channel: The MIDI channel, 0-15.
    """

    name: str
    cc: int | None = None
    channel: int = 0


def slug(text: str) -> str:
    """An OSC-safe name, since an address cannot contain a space.

    OSC also reserves `#`, `*`, `,`, `?`, `[`, `]`, `{` and `}`, so anything
    that is not alphanumeric is dropped rather than substituted.
    """
    words: list[str] = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return "parameter"
    return words[0].lower() + "".join(word.capitalize() for word in words[1:])


def namespace(text: str) -> str:
    """An OSC-safe address prefix, which may be more than one segment deep.

    Each segment is slugged on its own, so `Synth/Bank 1` survives as
    `synth/bank1` rather than collapsing into a single name.
    """
    return "/".join(slug(part) for part in text.split("/") if part.strip())


def unique(names: Sequence[str]) -> list[str]:
    """Number any repeats, so two parameters cannot share one OSC address.

    Real parameter lists repeat: a compressor's might hold three entries called
    `Bypass`.
    """
    seen: dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name}{seen[name]}")
    return result


def read(payload: Any) -> list[Parameter]:
    """Read a parameter list, in either of the shapes worth accepting.

    A list of names is the short form. A list of objects is the long one, and
    only `name` is required:

        ["Threshold", "Ratio"]
        [{"name": "Threshold", "cc": 20, "channel": 1}, {"name": "Ratio"}]

    A plugin host exports an `index` alongside each name. It is deliberately
    ignored: an index identifies the parameter to the host and is not a
    controller number, and a real one runs well past the 127 a CC allows. Say
    `cc` if you mean a controller number.

    Args:
        payload: The parsed JSON.

    Returns:
        The parameters, in order.

    Raises:
        TypeError: If the payload is not a list, or an entry is neither a
            string nor an object.
        ValueError: If an entry is an object with no name.
    """
    if not isinstance(payload, list):
        raise TypeError(
            f"expected a list of parameters, found {type(payload).__name__}"
        )

    parameters = []
    for position, entry in enumerate(payload):
        if isinstance(entry, str):
            parameters.append(Parameter(entry))
            continue
        if not isinstance(entry, dict):
            raise TypeError(
                f"parameter {position} is a {type(entry).__name__}; "
                f"expected a name or an object with one"
            )
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"parameter {position} has no name")
        parameters.append(
            Parameter(
                name=name,
                cc=entry.get("cc"),
                channel=int(entry.get("channel", 0)),
            )
        )
    return parameters


def _strip(
    name: str,
    parameter: Parameter,
    cc: int | None,
    prefix: str,
    color: object,
) -> Control:
    """One parameter: a fader with its name underneath."""
    control = fader(name=name, color=color)
    if prefix:
        control.messages.append(ui.osc(f"/{prefix}/{{name}}"))
    if cc is not None:
        control.messages.append(ui.midi_cc(cc, channel=parameter.channel))

    caption = label(
        name=f"{name}Caption",
        color=color,
        background=False,
        interactive=False,
        values=[Value("text", default=parameter.name), Value("touch", default=False)],
    )
    return ui.column(control, caption, sizes=(6, 1), name=name, color=color)


def _pages(
    parameters: Sequence[Parameter],
    names: Sequence[str],
    prefix: str,
    midi: bool,
    columns: int,
    rows: int,
) -> Iterator[Control]:
    per_page = columns * rows
    shades = layout.gradient(*GRADIENT, per_page)

    for first in range(0, len(parameters), per_page):
        chunk = range(first, min(first + per_page, len(parameters)))
        yield ui.tiles(
            *(
                _strip(
                    names[i],
                    parameters[i],
                    _controller(parameters[i], i) if midi else None,
                    prefix,
                    shades[i - first],
                )
                for i in chunk
            ),
            columns=columns,
            rows=rows,
            gap=8,
            pad=8,
            name=f"{first + 1}-{chunk[-1] + 1}",
        )


def _fit_text(doc: Document) -> None:
    """Size every caption to the box `resolve` gave it.

    A fixed text size only suits one canvas. The frames are not known until
    the layout resolves, so this runs afterwards and reads them.
    """
    low, high = TEXT_RANGE
    for control in doc.walk():
        if str(control.get("name", "")).endswith("Caption"):
            size = round(control.frame.h * TEXT_RATIO)
            control.text_size = max(low, min(high, size))


def _controller(parameter: Parameter, position: int) -> int | None:
    """The CC number for a parameter, or `None` if it cannot have one."""
    number = parameter.cc if parameter.cc is not None else position
    return number if 0 <= number < CC_LIMIT else None


def build(
    parameters: Sequence[Parameter],
    *,
    prefix: str = "surface",
    midi: bool = True,
    osc: bool = True,
    columns: int = COLUMNS,
    rows: int = ROWS,
    frame: tuple[int, int, int, int] = (0, 0, *SIZE),
) -> Document:
    """Lay parameters out across as many pages as they need.

    Args:
        parameters: What to put on it, in order.
        prefix: The OSC namespace every address hangs off.
        midi: Whether to bind each control to a MIDI CC.
        osc: Whether to give each control an OSC address.
        columns: Controls across each page.
        rows: Controls down each page.
        frame: The design canvas, as `(x, y, width, height)`. Defaults to
            `SIZE`; TouchOSC scales whatever you give it to the screen, so
            what matters is the aspect ratio and the room the controls get.

    Returns:
        The document, resolved and ready to save.

    Raises:
        ValueError: If there are no parameters, or neither binding is wanted.
    """
    if not parameters:
        raise ValueError("a surface needs at least one parameter")
    if not midi and not osc:
        raise ValueError("a surface with neither MIDI nor OSC would do nothing")

    address = namespace(prefix) if osc else ""
    names = unique([slug(p.name) for p in parameters])
    title = address.rsplit("/", 1)[-1] if address else slug(prefix)

    pager = ui.pager(
        *_pages(parameters, names, address, midi, columns, rows), name=title
    )
    # The pager cannot be the root: TouchOSC treats the root node as the canvas
    # and gives it none of its type's behaviour, so a PAGER there would draw a
    # tab bar and then stack every page instead of paging between them.
    doc = Document(root=ui.stack(pager, name=title, frame=frame)).resolve()
    _fit_text(doc)
    return doc
