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
cells = layout.matrix(panel, "BUTTON", columns=4, rows=3)
```

Cells come back in row-major order: left to right, then top to bottom.

## Colours

Pass two endpoints and the children are tinted between them:

```python
layout.row(panel, "FADER", sizes=8, colors=("#264653", "#e76f51"))
```

For grids, `direction` chooses how the gradient runs:

```python
layout.matrix(panel, columns=4, rows=4, colors=("#264653", "#e76f51"),
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

cells = layout.matrix(doc.root, columns=3, rows=3, colors=("#CE6A85", "#5C374C"))
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

## Describing a layout instead of applying one

The functions above size children the moment they create them, which needs a parent that already has a frame. That forces a layout to be built outside in, one control type at a time, and it cannot express a label sitting on a button at all.

[`py2tosc.ui`](../api/ui.md) takes the other approach: the combinators record an arrangement and assign frames later, so a layout can be written from the inside out.

```python
from py2tosc import ui

doc = py2tosc.Document(root=ui.column(
    ui.row(py2tosc.label(name="readout"), py2tosc.button(name="send")),
    ui.tiles(*keys, columns=3, gap=4, pad=8),
    sizes=(1, 3),
    frame=(0, 0, 500, 800),
))
doc.resolve()
```

Each combinator returns the group it made rather than the children, so the result goes wherever a control goes and nesting is ordinary function composition -- `row(column(a, b), c)`. A row can hold a fader and a label, since it takes controls rather than a control type.

`ui.stack` overlays its children, each filling the group. That is the button-with-a-label idiom, and it is the reason the numpad demo needs a helper of its own.

### Resolving

Nothing has a frame until `resolve` runs. It walks the tree from the top, because a layout can only divide a frame it knows, and a parent decides its children's frames outright -- a control inside a layout does not keep a frame it was built with. To place something by hand, leave it out of a layout group.

Saving never resolves on its own: writing a file must not change the tree. A layout that was never resolved is reported by [validation](validation.md), because an unset frame reads back as `(0, 0, 0, 0)` rather than raising, so the mistake is otherwise invisible.

### Gaps and padding

`gap` is the space between slots; `pad` is the inset before the first and after the last. `pad` takes a number, a `(horizontal, vertical)` pair, or `(left, top, right, bottom)`. `gap` takes a number or a pair -- it sits between slots, so it has no four-sided form.

Both are whole pixels, and the arithmetic is exact: each slot ends exactly `gap` before the next begins, and the last reaches the content edge. A layout whose padding and gaps do not fit raises rather than silently producing zero-width controls.

### Captions and insets

A label sitting on a button is the commonest control idiom in TouchOSC, and `ui.labelled` is the whole of it:

```python
key = ui.labelled(py2tosc.button(name="7"), "7", inset=0.1)
```

The caption is not interactive and has no background, so the button beneath receives the touch and shows through. It takes the button's colour, and its name is the caption -- which is what a local message sends when the key is pressed.

`inset` is a fraction rather than a pixel count, because a deferred layout has no pixels to work from: the size to take a fraction of is not known until the frame arrives from above. `ui.inset` applies one to any single control, which is the one thing a group's `pad` cannot say -- `pad` insets every child alike, and a key wants its caption padded but not the button underneath.

```python
ui.stack(button, ui.inset(caption, 0.1))
```

The inset belongs to the control rather than to a wrapper group, so padding a caption costs no extra node.

### Pages

`ui.pager` is `stack` on a `PAGER` rather than a `GROUP`: a pager shows one page at a time and switches between them itself, so every page fills it.

```python
ui.pager(
    ui.tiles(*first_twelve, columns=4, name="1-12"),
    ui.tiles(*next_twelve, columns=4, name="13-24"),
    frame=(0, 0, 1024, 768),
)
```

Pages should be groups, which the other combinators already return, and a page's name is its tab label. A page that is not a group is reported by [validation](validation.md) rather than refused, since TouchOSC tolerates it.

### Grids of one control

`ui.tiles` arranges controls you already have. The format also has a `GRID` *control*, which holds many copies of a single control type and is what a multitoggle or a bank of faders is made from. `ui.grid` builds one:

```python
pads = ui.grid("BUTTON", columns=8, rows=8, name="multitoggle")
for cell in pads:
    cell.messages.append(ui.midi_note(ui.prop("name")))
```

Cells are named `1` upwards and reached through the returned control, so each can carry its own bindings.

A `GRID` tiles rather than divides. Every cell is the same size, with a three-point margin around and between them, and whatever will not divide evenly is left at the far edge instead of being shared out -- which is the opposite of what `ui.tiles` and the eager layout functions do, where the last slot always reaches the edge.
