"""Generate a paged MIDI and OSC control surface from a plugin's parameters.

Given a JSON list of parameters -- the kind a DAW or a plugin host will export
-- this builds a fader per parameter, laid out in pages, with each fader
bound both to an OSC address and to a MIDI CC. Nothing about the layout is
written by hand: the parameter list decides how many pages there are and what
is on them.

    python tests/demos/control_surface.py tests/data/pro_c_2_fabfilter.json out.tosc
    python tests/demos/control_surface.py params.json out.tosc synth/bank1

The optional third argument is the OSC namespace every address hangs off. It
defaults to the file's name, which is convenient and fragile -- renaming the
file silently moves every address -- so anything that has to stay put should
say so rather than rely on the default.

Two things about real parameter data drive most of the code here. Names are
meant for people, so they contain spaces and repeat, while an OSC address can
have neither -- so each control gets a slug for its name and keeps the original
text on its caption. And a plugin's parameter *index* is a host identifier, not
a controller number: this file's runs to 182, well past the 127 a CC allows, so
the CC comes from the parameter's position instead.

Compare `from_json.py`, which is the smallest version of this idea: one row of
faders, OSC only, using the eager `py2tosc.layout` functions.
"""

import json
import re
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path

import py2tosc
from py2tosc import Control, Value, layout, ui

#: A page of parameters. Four across reads well on a tablet.
COLUMNS, ROWS = 4, 3
PER_PAGE = COLUMNS * ROWS

#: MIDI control change numbers run 0-127. A plugin can expose more parameters
#: than that, and the ones past the end simply go out over OSC alone.
CC_LIMIT = 128

GRADIENT = ("#264653", "#e76f51")


def slug(text: str) -> str:
    """An OSC-safe name, since an address cannot contain a space.

    OSC also reserves `#`, `*`, `,`, `?`, `[`, `]`, `{` and `}`, so anything
    that is not alphanumeric is dropped rather than substituted.
    """
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return "parameter"
    return words[0].lower() + "".join(word.capitalize() for word in words[1:])


def namespace(text: str) -> str:
    """An OSC-safe address prefix, which may be more than one segment deep.

    Each segment is slugged on its own, so `Synth/Bank 1` survives as
    `synth/bank1` rather than collapsing into a single name.
    """
    parts = [slug(part) for part in text.split("/") if part.strip()]
    return "/".join(parts)


def unique(names: Sequence[str]) -> list[str]:
    """Number any repeats, so two parameters cannot share one OSC address.

    Real parameter lists repeat: this one has three `Bypass` entries and two
    called `Internal`.
    """
    seen: dict[str, int] = {}
    result = []
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        result.append(name if seen[name] == 1 else f"{name}{seen[name]}")
    return result


def strip(name: str, caption: str, cc: int, color: object, prefix: str) -> Control:
    """One parameter: a fader with its name underneath.

    Args:
        name: The control's name, which is what the OSC address is built from.
        caption: The parameter's own name, shown to the reader.
        cc: The MIDI control change number, or -1 for none.
        color: The fader's colour.
        prefix: The OSC namespace the address hangs off.

    Returns:
        The strip, unsized until the layout is resolved.
    """
    fader = py2tosc.fader(name=name, color=color)
    fader.messages.append(ui.osc(f"/{prefix}/{{name}}"))
    if cc >= 0:
        fader.messages.append(ui.midi_cc(cc))

    label = py2tosc.label(
        name=f"{name}Caption",
        color=color,
        background=False,
        interactive=False,
        text_size=14,
        values=[Value("text", default=caption), Value("touch", default=False)],
    )
    return ui.column(fader, label, sizes=(6, 1), name=name, color=color)


def pages(captions: Sequence[str], prefix: str) -> Iterator[Control]:
    """Chunk the parameters into pages of `PER_PAGE`."""
    names = unique([slug(caption) for caption in captions])
    shades = layout.gradient(*GRADIENT, PER_PAGE)

    for first in range(0, len(captions), PER_PAGE):
        chunk = range(first, min(first + PER_PAGE, len(captions)))
        yield ui.tiles(
            *(
                strip(
                    names[i],
                    captions[i],
                    i if i < CC_LIMIT else -1,
                    shades[i - first],
                    prefix,
                )
                for i in chunk
            ),
            columns=COLUMNS,
            rows=ROWS,
            gap=8,
            pad=8,
            name=f"{first + 1}-{chunk[-1] + 1}",
        )


def build(
    captions: Sequence[str],
    prefix: str,
    frame: tuple[int, int, int, int] = (0, 0, 1024, 768),
) -> py2tosc.Document:
    """Assemble the surface, then hand the root frame down the tree.

    Args:
        captions: One parameter name per fader, in order.
        prefix: The OSC namespace the addresses hang off. Its last segment
            names the layout, since a control's name cannot sensibly hold a
            path.
        frame: The size of the whole surface.

    Returns:
        The document, resolved and ready to save.
    """
    title = prefix.rsplit("/", 1)[-1]
    surface = ui.pager(*pages(captions, prefix), name=title)

    # The pager cannot be the root. TouchOSC treats the root node as the canvas
    # and gives it none of its type's behaviour, so a PAGER there draws its tab
    # bar and then stacks every page instead of paging between them. Every
    # layout in the corpus roots at a GROUP; `validate` reports it if this slips.
    root = ui.stack(surface, name=title, frame=frame)
    return py2tosc.Document(root=root).resolve()


def main(json_path: str, output_path: str, prefix: str = "") -> None:
    with open(json_path) as file:
        parameters = json.load(file)

    # Falling back to the file's name is a convenience, not a contract: it ties
    # every OSC address to something a rename can change out from under it.
    namespace_ = namespace(prefix) or slug(Path(json_path).stem)
    doc = build([p["name"] for p in parameters], namespace_)

    for issue in doc.validate():
        print(f"  {issue}")

    doc.save(output_path)
    print(
        f"{len(parameters)} parameters -> {len(doc.find(type='PAGER').children)} pages, "
        f"{len(doc.find_all())} controls -> {output_path}"
    )


if __name__ == "__main__":
    main(*sys.argv[1:4])
