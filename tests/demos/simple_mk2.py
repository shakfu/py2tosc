"""Rebuild a layout TouchOSC ships, from scratch.

`tests/examples/simple_mk2.tosc` is one of the templates that comes with
TouchOSC 1.5: four pages behind a pager, 140 controls, and every binding type
the format has. This builds the same interface with the combinators in
`py2tosc.ui`, which is the widest thing in the repository that the library
authors rather than edits.

    python tests/demos/simple_mk2.py

It comes out with the same control types and names, the same tab labels, and
the same bindings to the message: 105 MIDI, 105 OSC, 30 local. Of the 134
controls that can be compared by position, 77 land on exactly the original
coordinates and 111 within a point. Every property that decides what a control
*does* matches exactly.

That last part was the hard one. A first pass got the layout and the wiring
right and produced something in which nothing moved, because the readouts were
left interactive and so took every touch meant for the control underneath. Three
more followed the same shape: a fader is vertical whatever its frame looks like
unless `orientation` says otherwise; a button is momentary until `button_type`
says it latches; and a caption with no text reads as a missing control rather
than an empty one. None of it is visible to `validate`, to a round trip, or to
comparing positions -- only to opening the file.

Two things differ on purpose.

The tree carries more groups -- 39 against 5 -- because the arrangement is
described rather than hand-placed. A fader and its readout are a `stack`, a row
of four is a `row`, and each of those is a group the original does not have. The
controls still land in the same places.

The readouts fill the control they caption instead of being small boxes placed
by eye, which is the whole of the remaining 23 position differences. A label
with no background draws its text in the middle of whatever frame it is given,
so it reads the same; matching exactly would mean going back to coordinates,
which is the thing this is demonstrating you no longer need.
"""

import argparse
from pathlib import Path

import py2tosc
from py2tosc import Control, Value, ui

SIZE = (0, 0, 320, 480)

#: Every page ends with the same four toggles, and the columns on the fader
#: page line up with them: four slots inset 17 from the left, 16 from the
#: right, 9 apart. Taken from the original rather than invented, so the
#: rebuild lands on the same coordinates.
COLUMNS = {"pad": (17, 0, 16, 0), "gap": 9}

#: The full-width controls -- the XY face and the matrix -- sit two points
#: further out than the columns do. Another number taken from the original.
WIDE = (15, 0, 15, 0)

#: The template's two colours.
YELLOW = (1.0, 0.93, 0.0, 1.0)
TEAL = (0.0, 0.77, 0.66, 1.0)

#: Rounded corners on everything, which is the one styling choice worth
#: carrying because it is uniform across all 140 controls.
TRIM = {"corner_radius": 1}


def readout(
    name: str, text: str = "", *, visible: bool = True, size: int = 14
) -> Control:
    """A label a control writes its value into.

    `interactive=False` is the load-bearing property. These sit on top of the
    control they caption, and a label that stays interactive takes the touch
    instead of letting it through -- which leaves the fader underneath looking
    broken while nothing at all is wrong with its bindings.

    It is a `LABEL` default now, having cost a round of debugging here first,
    so passing it is documentation rather than necessity.

    Args:
        name: The label's name.
        text: What it says before anything writes to it. A caption that never
            changes says it here and nothing writes to it at all -- leave it
            empty and the control it labels reads as missing rather than blank.
        visible: Whether it shows before anything touches it. A fader's readout
            starts hidden and is shown by the touch binding; a caption is
            always there.
        size: Text size.
    """
    return py2tosc.label(
        name=name,
        color=YELLOW,
        interactive=False,
        visible=visible,
        background=False,
        outline=False,
        text_size=size,
        text_clip=False,
        values=[Value("text", default=text), Value("touch", default=False)],
        **TRIM,
    )


def channel(number: int, cc: int, caption: str) -> Control:
    """A fader with a readout laid over it, wired to show its own value.

    The two local bindings are the idiom this template is built on: the fader
    writes its value into the label as text, and shows the label only while it
    is being touched.
    """
    label = readout(caption, "0", visible=False)
    fader = py2tosc.fader(
        name=f"fader{number}",
        color=YELLOW,
        response=1,
        cursor=False,
        centered=False,
        pointer_priority=1,
        **TRIM,
        messages=[
            ui.midi_cc(cc),
            ui.osc("/{parent.name}/{name}"),
            ui.connect(label, source=ui.value("x"), to="text"),
            ui.connect(
                label, source=ui.value("touch"), to=ui.prop("visible"), var="touch"
            ),
        ],
    )
    # A control may address itself: the fader outlines while it is held.
    fader.messages.append(
        ui.connect(
            fader, source=ui.value("touch"), to=ui.prop("outlineStyle"), var="touch"
        )
    )
    return ui.stack(fader, label, name=f"channel{number}")


def wide_channel() -> Control:
    """The fader across the top, which lies on its side.

    A FADER is vertical unless its `orientation` says otherwise, so a wide
    frame alone gives a tall fader squashed into a letterbox.
    """
    cell = channel(5, 4, "label5")
    cell[0].set("orientation", 1)
    return cell


def toggles(first_cc: int) -> Control:
    """The row of four toggles every page carries along its bottom."""
    return ui.row(
        *(
            py2tosc.button(
                name=f"toggle{n + 1}",
                color=TEAL,
                button_type=1,
                **TRIM,
                messages=[ui.midi_cc(first_cc + n), ui.osc("/{parent.name}/{name}")],
            )
            for n in range(4)
        ),
        name="toggles",
        **COLUMNS,
    )


def faders_page() -> Control:
    """A wide fader, four channels, and the toggles."""
    return ui.column(
        ui.row(wide_channel(), name="wide", **COLUMNS),
        ui.row(*(channel(n, n - 1, f"label{n}") for n in range(1, 5)), **COLUMNS),
        toggles(first_cc=5),
        sizes=(65, 255, 65),
        pad=(0, 21, 0, 16),
        gap=9,
        name="1",
        tab_label="FADERS",
    )


def pads_page() -> Control:
    """Sixteen note pads, numbered from the bottom left as the original is."""
    order = [n for row in range(3, -1, -1) for n in range(row * 4 + 1, row * 4 + 5)]
    pads = [
        ui.stack(
            py2tosc.button(
                name=f"push{n}",
                color=YELLOW,
                background=False,
                outline_style=0,
                grab_focus=False,
                **TRIM,
                messages=[
                    ui.midi_note(23 + n),
                    ui.osc("/{parent.name}/{name}"),
                ],
            ),
            readout(f"label{n}", str(n)),
            name=f"pad{n}",
        )
        for n in order
    ]
    return ui.column(
        ui.tiles(*pads, columns=4, rows=4, gap=5, pad=(17, 0, 16, 0)),
        toggles(first_cc=15),
        sizes=(287, 65),
        pad=(0, 36, 0, 16),
        gap=36,
        name="2",
        tab_label="PADS",
    )


def xy_page() -> Control:
    """An XY pad, its two readouts, and the buttons that lock and reset it."""
    # Named label12 and label13, but readouts rather than captions -- the PADS
    # page has labels of the same names that really are captions.
    across = readout("label12", "0", visible=False)
    down = readout("label13", "0", visible=False)
    pad = py2tosc.xy(
        name="xy",
        color=YELLOW,
        response=1,
        **TRIM,
        messages=[
            ui.midi_cc(13),
            ui.midi_cc(14, source="y", var="y"),
            ui.osc("/{parent.name}/{name}/x"),
            ui.osc("/{parent.name}/{name}/y", args=[ui.value("y")], var="y"),
            ui.connect(across, source=ui.value("x"), to="text"),
            ui.connect(down, source=ui.value("y"), to="text", var="y"),
            ui.connect(
                across, source=ui.value("touch"), to=ui.prop("visible"), var="touch"
            ),
            ui.connect(
                down, source=ui.value("touch"), to=ui.prop("visible"), var="touch"
            ),
        ],
    )
    pad.messages.append(
        ui.connect(
            pad, source=ui.value("touch"), to=ui.prop("outlineStyle"), var="touch"
        )
    )

    def command(
        group: str,
        name: str,
        caption: str,
        wording: str,
        wiring: list,
        *,
        latching: bool = True,
    ) -> Control:
        """A button whose caption is the only part you can see.

        The two locks latch, so they show which axis is held; reset springs
        back, because a reset that stayed down would only fire once.
        """
        label = readout(caption, wording, size=12)
        button = py2tosc.button(
            name=name,
            button_type=2 if latching else 0,
            background=False,
            outline=False,
            outline_style=0,
            **TRIM,
            messages=wiring,
        )
        # Every command lights its own caption while it is held.
        button.messages.append(
            ui.connect(label, source=ui.value("x"), to=ui.prop("background"))
        )
        # The group takes a name of its own: sharing the button's would mean
        # `find("buttonLockX")` returned the wrapper rather than the button.
        return ui.stack(button, label, name=group)

    lock_y = command(
        "lockY",
        "buttonLockY",
        "labelLockY",
        "Lock Y",
        [ui.connect(pad, source=ui.value("x"), to=ui.prop("lockY"))],
    )
    lock_x = command(
        "lockX",
        "buttonLockX",
        "labelLockX",
        "Lock X",
        [ui.connect(pad, source=ui.value("x"), to=ui.prop("lockX"))],
    )
    # Locking one axis releases the other. The two bindings point at each
    # other, which is why both buttons are built before either is wired.
    lock_x[0].messages.append(
        ui.connect(lock_y[0], source=ui.value("x"), to="x", on="RISE")
    )
    lock_y[0].messages.append(
        ui.connect(lock_x[0], source=ui.value("x"), to="x", on="RISE")
    )
    reset = command(
        "reset",
        "buttonReset",
        "labelReset",
        "RESET",
        [
            ui.connect(pad, source=ui.const("0"), to="x", on="FALL"),
            ui.connect(pad, source=ui.const("0"), to="y", on="FALL"),
        ],
        latching=False,
    )

    return ui.column(
        ui.row(ui.stack(pad, across, down, name="pad"), pad=WIDE, name="face"),
        ui.row(lock_x, reset, lock_y, pad=WIDE, gap=10, name="commands"),
        toggles(first_cc=15),
        sizes=(290, 30, 65),
        pad=(0, 20, 0, 16),
        gap=9,
        name="3",
        tab_label="XY",
    )


def matrix_page() -> Control:
    """An eight by eight matrix of toggles, on its own MIDI channel."""

    def bindings() -> list:
        return [
            ui.midi_cc(0, channel=1),
            ui.osc("/{parent.parent.name}/{parent.name}/{name}"),
        ]

    matrix = ui.grid("BUTTON", columns=8, rows=8, name="multitoggle")
    for cell in matrix:
        # shape 2 is the round button; button type 2 latches rather than
        # springing back, which is what makes it a matrix rather than a pad.
        cell.set("shape", 2)
        cell.set("buttonType", 2)
        cell.set("outline", False)
        cell.set("grabFocus", False)
        cell.set("color", YELLOW)
        cell.set("cornerRadius", 1)
    matrix.messages.extend(bindings())
    # The editor gives every cell a copy of the grid's own bindings, so each
    # one addresses itself by name and reports its index over MIDI.
    for cell in matrix:
        cell.messages.extend(bindings())

    caption = readout("labelReset", "RESET", size=12)
    button = py2tosc.button(
        name="buttonReset",
        button_type=0,
        background=False,
        outline=False,
        outline_style=0,
        **TRIM,
        messages=[ui.connect(caption, source=ui.value("x"), to=ui.prop("background"))],
    )
    reset = ui.stack(button, caption, name="reset")
    return ui.column(
        ui.row(matrix, pad=WIDE, name="face"),
        ui.row(reset, pad=(115, 0, 115, 0), name="commands"),
        toggles(first_cc=19),
        sizes=(290, 30, 65),
        pad=(0, 20, 0, 16),
        gap=9,
        name="4",
        tab_label="MATRIX",
    )


def build() -> py2tosc.Document:
    """Assemble the four pages behind a pager, inside a group."""
    pager = ui.pager(
        faders_page(), pads_page(), xy_page(), matrix_page(), name="pager1"
    )
    # The pager reports which page it switched to.
    pager.messages += [
        py2tosc.MidiMessage(
            triggers=[py2tosc.Trigger("page", "ANY")],
            message=py2tosc.MidiCommand("PROGRAMCHANGE"),
        ),
        ui.osc("/page", args=[ui.value("page")], var="page"),
    ]
    # The pager cannot be the root: TouchOSC treats the root as the canvas and
    # gives it none of its type's behaviour. The original is built the same way.
    return py2tosc.Document(root=ui.stack(pager, name="group", frame=SIZE)).resolve()


def main(output_path: Path) -> None:
    doc = build()

    for issue in doc.validate():
        print(f"  {issue}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    pages = len(doc.find(type="PAGER").children)
    print(f"{pages} pages, {len(doc.find_all())} controls -> {output_path}")


def parse_args() -> argparse.Namespace:
    """Read the command line, so a missing path is a message and not a crash."""
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
    args = parse_args()
    main(args.output)
