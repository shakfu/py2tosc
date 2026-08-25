# py2tosc

Generate and edit TouchOSC layouts from Python.

A `.tosc` file is a zlib-compressed XML tree. py2tosc reads that tree into plain Python objects, lets you edit them, and writes it back out -- accurately enough that loading a layout and saving it again reproduces the editor's own bytes exactly.

!!! warning "Disclaimer"

    This project has no relation to Hexler, the developer of TouchOSC. Back up
    your layouts before editing them with third party tools.

```console
$ pip install py2tosc
```

No dependencies. Python 3.10 or newer.

## Editing a layout

```python
import py2tosc

doc = py2tosc.load("mixer.tosc")

for fader in doc.find_all(type="FADER"):
    fader.color = "#e76f51"
    fader.corner_radius = 2.0

doc.save("mixer-restyled.tosc")
```

## Building one from scratch

[`py2tosc.ui`](api/ui.md) describes an arrangement and sizes it afterwards, so a
layout is written from the inside out and nothing needs coordinates:

```python
import py2tosc
from py2tosc import ui

faders = [
    py2tosc.fader(
        name=f"ch{n}",
        messages=[ui.osc("/mixer/{name}"), ui.midi_cc(n - 1)],
    )
    for n in range(1, 9)
]

doc = py2tosc.Document(root=ui.column(
    ui.row(*faders, gap=4),
    ui.grid("BUTTON", columns=8, rows=2, name="mutes"),
    sizes=(3, 1),
    pad=8,
    gap=8,
    frame=(0, 0, 1024, 768),
    name="mixer",
))

doc.resolve()   # hand the root frame down the tree, sizing everything
doc.save("mixer.tosc")
```

The eager [`layout`](api/layout.md) functions are still there and unchanged, for
when you would rather place children against a parent you already have.

## Reading one back as code

`to_python` writes a layout out as the script that would build it, which is what
you want when the layout exists and the source does not:

```python
print(py2tosc.to_python(py2tosc.load("mixer.tosc")))
```

## Where to go next

- [Getting started](getting-started.md) walks through loading, editing and saving a layout.

- [Command line](cli.md) does most of the above without a script: inspect, check, convert and decompile a layout, or generate one from a list of parameters.

- [Controls and properties](guide/controls.md) covers the property model and the `snake_case` naming.

- [Layouts](guide/layouts.md) covers both arrangement APIs, and when each is the easier one.

- [Message combinators](api/ui.md) shortens the bindings: an f-string-like OSC address, the two common MIDI ones, and local wiring in a line.

- [The .json format](guide/json.md) is the same tree as JSON, for emitting a layout from something that is not Python, or reading a diff of one.

- [Describing a layout in JSON](guide/ui-json.md) is the other dialect: what nests in what, repeated over counters or rows of data, built by the combinators.

- [The .tosc format](guide/format.md) documents the file format itself, which is useful whether or not you use this library.

- [Validation](guide/validation.md) checks a layout for what TouchOSC will reject.

- [Coming from tosclib](migrating.md) maps the tosclib API onto this one.

For TouchOSC itself, see Hexler's [control reference](https://hexler.net/touchosc/manual/controls) and [scripting reference](https://hexler.net/touchosc/manual/script).
