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

```python
import py2tosc
from py2tosc import layout

doc = py2tosc.Document.new(frame=(0, 0, 1024, 768))

strip = py2tosc.group(name="strip", frame=(0, 0, 1024, 768))
doc.add(strip)

for index, fader in enumerate(layout.row(strip, "FADER", sizes=8)):
    fader.name = f"ch{index + 1}"
    fader.messages.append(py2tosc.OscMessage())

doc.save("mixer.tosc")
```

## Where to go next

- [Getting started](getting-started.md) walks through loading, editing and saving a layout.

- [Controls and properties](guide/controls.md) covers the property model and the `snake_case` naming.

- [The .tosc format](guide/format.md) documents the file format itself, which is useful whether or not you use this library.

- [Validation](guide/validation.md) checks a layout for what TouchOSC will reject.

- [Coming from tosclib](migrating.md) maps the tosclib API onto this one.

For TouchOSC itself, see Hexler's [control reference](https://hexler.net/touchosc/manual/controls) and [scripting reference](https://hexler.net/touchosc/manual/script).
