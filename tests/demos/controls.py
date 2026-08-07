"""Build one of every control type the format has.

Thirteen controls, each captioned and each sending to `/<name>`, on a single
sheet meant to be opened in TouchOSC and looked at.

    python tests/demos/controls.py

That is the point of it. py2tosc can tell you a layout is structurally valid,
and it can prove a file round-trips byte for byte, but neither says whether a
`RADIAL` came out round or a `RADIO` came out sideways. Every defect this
project has found in construction -- a pager page with no tab label, a grid
announcing the wrong cell type, readouts that swallowed their own faders'
touches -- was valid, round-tripped exactly, and visibly wrong the moment
someone opened it. This is the sheet to open.

It is also the answer to a gap: six of the thirteen types (`BOX`, `ENCODER`,
`RADAR`, `RADIAL`, `RADIO`, `TEXT`) were read and round-tripped by the library
but never built by anything in it, so nothing exercised the path where those
defects live.

Compare `tests/data/controls.tosc`, which is the same idea drawn by hand in
the editor and is what the defaults are tested against.
"""

import argparse
from pathlib import Path

import py2tosc
from py2tosc import Control, Value, ui

#: Everything except the containers, which need children to be worth looking at.
SIMPLE = [
    ("BOX", "box"),
    ("BUTTON", "button"),
    ("LABEL", "label"),
    ("TEXT", "text"),
    ("FADER", "fader"),
    ("XY", "xy"),
    ("RADIAL", "radial"),
    ("ENCODER", "encoder"),
    ("RADAR", "radar"),
    ("RADIO", "radio"),
]

TEAL = (0.15, 0.27, 0.32, 1.0)
SAND = (0.90, 0.44, 0.32, 1.0)

#: A sheet is read all at once, so it is not paged -- the same reason `hexkeys`
#: is not. 1024x768 is the largest canvas any layout TouchOSC ships uses, and
#: thirteen captioned controls is what it is for.
FRAME = (0, 0, 1024, 768)


def caption(text: str) -> Control:
    """The name under a control. Never interactive, so the control gets the touch.

    What a label says is a value, so it goes in `values`. Passing `text=` to
    the factory would set a *property* of that name instead -- accepted, since
    the format lets a script invent properties, and drawn as nothing.
    """
    return py2tosc.label(
        name=f"{text}Caption",
        color=SAND,
        background=False,
        outline=False,
        text_size=18,
        values=[Value("text", default=text), Value("touch", default=False)],
    )


def cell(control: Control, name: str) -> Control:
    """One control with its name underneath."""
    return ui.column(control, caption(name), sizes=(5, 1), gap=2, name=f"{name}Cell")


def sample(kind: str, name: str) -> Control:
    """One control of a type, addressed by its own name.

    A `LABEL` and a `TEXT` are given something to say: their text defaults to
    empty, which draws as nothing at all and would leave two blanks on a sheet
    whose whole job is being looked at.

    What they say is a *value*, not a property. `control.text = "..."` would
    create a custom property called `text` that TouchOSC ignores, and nothing
    would report it -- a custom property is exactly what the format lets a
    script invent, so it cannot be told from a typo.
    """
    control = getattr(py2tosc, kind.lower())(name=name, color=TEAL)
    if kind == "LABEL":
        control.value("text").default = "label"
    elif kind == "TEXT":
        control.value("text").default = "A TEXT holds several lines, and wraps."
    control.messages.append(ui.osc("/{name}"))
    return control


def build() -> py2tosc.Document:
    """The whole sheet."""
    cells = [cell(sample(kind, name), name) for kind, name in SIMPLE]

    # The three container types, each holding something, since an empty one
    # shows nothing about how it behaves.
    cells.append(
        cell(
            ui.row(
                py2tosc.button(name="a", color=TEAL),
                py2tosc.button(name="b", color=TEAL),
                gap=4,
                name="group",
            ),
            "group",
        )
    )
    cells.append(
        cell(
            ui.pager(
                *(
                    ui.stack(caption(f"page{n}"), name=f"page{n}")
                    for n in range(1, 4)
                ),
                name="pager",
            ),
            "pager",
        )
    )
    cells.append(cell(ui.grid("FADER", columns=2, rows=2, name="grid"), "grid"))

    return py2tosc.Document(
        root=ui.tiles(*cells, columns=5, gap=10, pad=12, frame=FRAME, name="controls")
    )


def main(output_path: Path) -> None:
    doc = build()
    doc.resolve()

    for issue in doc.validate():
        print(f"  {issue}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    kinds = {c.control_type.value for c in doc.walk()}
    print(f"{len(kinds)} control types, {len(list(doc.walk()))} controls -> {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("build") / f"{Path(__file__).stem}.tosc",
        help="where to write the layout (default: %(default)s)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main(parse_args().output)
