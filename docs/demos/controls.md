# One of every control

`tests/demos/controls.py` builds a sheet holding one of each of the thirteen
control types the format has, captioned and each sending to `/<name>`.

```console
$ python tests/demos/controls.py
13 control types, 52 controls -> build/controls.tosc
```

## Why it exists

py2tosc can tell you a layout is structurally valid, and it can prove a file
round-trips byte for byte. Neither says whether a `RADIAL` came out round.

Every defect this project has found in *construction* rather than parsing was
valid, round-tripped exactly, and visibly wrong the moment someone opened it in
TouchOSC -- a pager page with no tab label, a grid announcing the wrong cell
type, readouts that swallowed their own faders' touches. This is the sheet to
open when you want to check the library still builds controls that work.

It also closed a real gap. Six of the thirteen types -- `BOX`, `ENCODER`,
`RADAR`, `RADIAL`, `RADIO` and `TEXT` -- were read and round-tripped but never
built by anything in the library, so nothing exercised the path those defects
live on. Building them found four wrong defaults, described in
[Controls and properties](../guide/controls.md).

## What it shows

The three container types hold something, since an empty one demonstrates
nothing: the `GROUP` has two buttons, the `PAGER` has three pages, and the
`GRID` is a two-by-two of faders.

It is not paged, which is deliberate and follows the same reasoning as
`hexkeys` in [Layout sizes](../guide/sizes.md): a sheet is read all at once.

## A trap it walked into

What a `LABEL` says is a **value**, not a property:

```python
control.value("text").default = "label"          # correct
py2tosc.label(name="cap", text="label")          # a custom property, drawn as nothing
```

The second is accepted without complaint, because inventing a property is
exactly what the format lets a script do -- which makes a typo indistinguishable
from a feature. Every caption on this sheet was blank until it was fixed.

[`validate`](../guide/validation.md) now reports it, since a custom property
named after a value the control already has is the one case that is never
deliberate. No control in the corpus has one.
