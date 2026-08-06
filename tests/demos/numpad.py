"""An integer numpad, built entirely from Python.

A reconstruction of the numpad module by Felix
(<https://github.com/F-l-i-x/TouchOSC/tree/main/modules/numpad>), and the demo
that most exercises the library: nested layouts, per-cell controls, a Lua script
carried as a property, and LOCAL messages wiring every key to one readout.

Each key is a BUTTON with a LABEL on top. Pressing a key sends its `name` to the
readout's `text` value over a LOCAL message; the readout's script appends the
digit and clamps the total.

    python tests/demos/numpad.py out.tosc
"""

import sys

import py2tosc
from py2tosc import Control, LocalMessage, Value, layout, ui

GRADIENT = ("#404040", "#804040")
KEYS = ("7", "4", "1", "8", "5", "2", "9", "6", "3")

READOUT_SCRIPT = """
self.sum = "0"
self.values.text = self.sum

function onValueChanged(key, value)
    self.sum = self.sum..self.values.text
    if tonumber(self.sum) >= tonumber(self.max) then
        self.sum = self.max
    end
    if tonumber(self.sum) == 0 then
        self.values.text = "0"
    end
    self.values.text = self.sum
end
"""


def key(cell: Control, caption: str, *, inset: float = 0.0) -> Control:
    """Fill a cell with a button and a label, and return the button.

    The label sits on top and is not interactive, so the button beneath it
    receives the touch. Both are sized to the cell, since a child's frame is
    relative to its parent.

    Args:
        cell: The group to fill.
        caption: The text the label shows, which is also the button's name --
            that name is what a LOCAL message sends.
        inset: Fraction of the cell to inset the label by, for padding.

    Returns:
        The button, so a message can be attached to it.
    """
    _, _, w, h = cell.frame
    pad = (int(w * inset), int(h * inset), int(w * (1 - 2 * inset)), int(h * (1 - 2 * inset)))

    button = py2tosc.button(name=caption, frame=(0, 0, w, h), color=cell.color, outline=False)
    label = py2tosc.label(
        name=caption,
        frame=pad,
        color=cell.color,
        background=False,
        interactive=False,
        text_size=48,
        values=[Value("text", default=caption), Value("touch", default=False)],
    )
    cell.add(button, label)
    return button


def sends_name_to(readout: Control) -> LocalMessage:
    """A binding that sends the pressing control's name to the readout's text."""
    return ui.connect(readout, source=ui.prop("name"), to="text", on="RISE")


def build() -> py2tosc.Document:
    """Assemble the numpad."""
    doc = py2tosc.Document.new(frame=(0, 0, 500, 800), name="Numpad")

    top, middle, bottom = layout.column(doc.root, sizes=(1, 3, 1), colors=GRADIENT)
    top.name, middle.name, bottom.name = "values", "numbers", "clear"

    # -- readout and send, across the top
    value_cell, send_cell = layout.row(top, sizes=2, colors=GRADIENT)
    value_cell.name, send_cell.name = "value", "send"

    _, _, w, h = value_cell.frame
    readout = py2tosc.label(
        name="valueLabel",
        frame=(0, 0, w, h),
        color=value_cell.color,
        background=False,
        text_size=60,
        values=[Value("text", default="0"), Value("touch", default=False)],
    )
    readout.set("sum", "")
    readout.set("max", "127")
    readout.script = READOUT_SCRIPT

    value_cell.add(py2tosc.button(name="valueButton", frame=(0, 0, w, h), color=value_cell.color))
    value_cell.add(readout)
    key(send_cell, "SEND")

    # -- the digits, in a 3x3 grid
    for cell, caption in zip(layout.grid(middle, columns=3, rows=3, colors=GRADIENT, direction="sequential"), KEYS):
        cell.name = f"key{caption}"
        key(cell, caption, inset=0.1).messages.append(sends_name_to(readout))

    # -- clear, zero and delete along the bottom
    clear_cell, zero_cell, del_cell = layout.row(bottom, sizes=3, colors=GRADIENT)
    clear_cell.name, zero_cell.name, del_cell.name = "clear", "zero", "del"

    key(zero_cell, "0").messages.append(sends_name_to(readout))

    # CLR resets the running total and blanks the readout.
    key(clear_cell, "CLR").messages += [
        ui.connect(readout, source=ui.const("0"), to=ui.prop("sum"), on="RISE"),
        ui.connect(readout, source=ui.const(""), to="text", on="FALL"),
    ]

    key(del_cell, "DEL").messages.append(
        ui.connect(readout, source=ui.const(""), to="text", on="FALL")
    )

    return doc


def main(output_path: str) -> None:
    doc = build()

    for issue in doc.validate():
        print(f"  {issue}")

    doc.save(output_path)
    print(f"{len(doc.find_all())} controls -> {output_path}")


if __name__ == "__main__":
    main(*sys.argv[1:2])
