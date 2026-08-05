# Layouts

`py2tosc.layout` fills a control's frame with evenly divided children. Each function creates the controls, sizes them, tints them along a gradient, appends them to the parent and returns them.

The arithmetic is plain Python -- py2tosc has no numpy dependency.

## Rows and columns

```python
import py2tosc
from py2tosc import layout

panel = py2tosc.group(frame=(0, 0, 800, 600))
faders = layout.row(panel, "FADER", sizes=8)
```

`sizes` is either a count or a set of ratios. `(1, 2, 1)` makes three slots where the middle one is twice the size of its neighbours:

```python
top, middle, bottom = layout.column(panel, sizes=(1, 2, 1))
```

Slots always add up to the parent's frame exactly; rounding is absorbed as the layout is built, so there are no gaps or overlapping edges.

## Grids

```python
cells = layout.grid(panel, "BUTTON", columns=4, rows=3)
```

Cells come back in row-major order: left to right, then top to bottom.

## Colours

Pass two endpoints and the children are tinted between them:

```python
layout.row(panel, "FADER", sizes=8, colors=("#264653", "#e76f51"))
```

For grids, `direction` chooses how the gradient runs:

```python
layout.grid(panel, columns=4, rows=4, colors=("#264653", "#e76f51"),
            direction="horizontal")   # across each row, repeated per row
            direction="vertical"      # down the rows, constant along each
            direction="sequential"    # cell by cell, row-major
```

[`gradient`][py2tosc.layout.gradient] is available on its own:

```python
for control, color in zip(controls, layout.gradient("#264653", "#e76f51", len(controls))):
    control.color = color
```

## Nesting

Because each function returns the controls it made, layouts compose by passing one of the results back in as the next parent:

```python
doc = py2tosc.Document.new(frame=(0, 0, 1600, 1600))

cells = layout.grid(doc.root, columns=3, rows=3, colors=("#CE6A85", "#5C374C"))
layout.column(cells[4], "BUTTON", sizes=4)
layout.row(cells[6], "FADER", sizes=2)
```

Children are positioned relative to their parent, so a nested layout needs no offset arithmetic.

## Naming what you build

Layout functions do not name the controls they create; that is left to you, because the naming is what makes the layout addressable over OSC:

```python
for index, fader in enumerate(layout.row(panel, "FADER", sizes=8)):
    fader.name = f"ch{index + 1}"
    fader.messages.append(py2tosc.OscMessage())
```
