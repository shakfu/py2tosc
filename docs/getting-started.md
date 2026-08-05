# Getting started

## Install

```console
$ pip install py2tosc
```

py2tosc has no runtime dependencies and needs Python 3.10 or newer.

## Loading a layout

[`load`][py2tosc.load] accepts either format the TouchOSC editor writes: the compressed `.tosc` a layout is saved as, and the `.xml` it exports. You do not have to say which you have.

```python
import py2tosc

doc = py2tosc.load("mixer.tosc")
print(doc)
#> <Document version=6 root=<GROUP, 3 children> (24 controls)>
```

A [`Document`][py2tosc.Document] holds one root control -- always a group -- and the format version. Everything else hangs off the root.

## Finding controls

`find` returns the first match anywhere beneath the root; `find_all` returns every match. Both take a name, a control type, or both.

```python
doc.find("cutoff")                       # by name
doc.find_all(type="FADER")               # by type
doc.find("cutoff", type="FADER")         # both
doc.root.children                        # direct children only
list(doc.walk())                         # every control, depth first
```

## Reading and writing properties

Properties are attributes. Python names are `snake_case`; the camelCase keys the file format uses are handled for you.

```python
fader = doc.find("cutoff")

fader.name             #> 'cutoff'
fader.frame            #> Frame(x=77, y=60, w=50, h=200)
fader.color            #> Color(r=1.0, g=0.0, b=0.0, a=1.0)
fader.corner_radius    #> 1.0        (the file's "cornerRadius")
fader.grid_steps       #> 13         (the file's "gridSteps")

fader.color = "#e76f51"
fader.frame = (10, 20, 50, 200)
fader.visible = False
```

Colours accept floats, 0-255 integers or hex strings, and frames accept any four-item sequence. Both come back as named tuples that still compare as plain tuples:

```python
fader.frame == (10, 20, 50, 200)   #> True
fader.frame.w                      #> 50
```

Reading a property that is not set raises `AttributeError`. Use `get` when absence is expected:

```python
fader.get("script", "")
fader.has("script")
```

## Creating controls

There is a factory function per control type, each applying that type's defaults. Any property can be passed as a keyword argument.

```python
import py2tosc

f = py2tosc.fader(name="cutoff", frame=(0, 0, 50, 200), color="#e76f51")
g = py2tosc.group(name="panel")

g.add(f)
```

Available: `box`, `button`, `label`, `text`, `fader`, `xy`, `radial`, `encoder`, `radar`, `radio`, `group`, `pager`, `grid`.

## Copying

`copy` duplicates a control and everything beneath it, with fresh ids so the result is still a valid layout.

```python
strip = doc.find("channel1")

for channel in range(2, 9):
    doc.add(strip.copy(name=f"channel{channel}"))
```

## Saving

The extension decides the format: `.xml` writes the readable export, anything else writes a compressed `.tosc`.

```python
doc.save("mixer.tosc")     # what TouchOSC opens
doc.save("mixer.xml")      # readable, useful in diffs
text = doc.dumps()         # the XML as a string
```

## A complete example

```python
import py2tosc
from py2tosc import layout

doc = py2tosc.Document.new(frame=(0, 0, 1024, 768))

top, bottom = layout.column(doc.root, sizes=(3, 1), colors=("#264653", "#2a9d8f"))

for index, fader in enumerate(layout.row(top, "FADER", sizes=8)):
    fader.name = f"ch{index + 1}"
    fader.messages.append(py2tosc.OscMessage())

for index, button in enumerate(layout.row(bottom, "BUTTON", sizes=8)):
    button.name = f"mute{index + 1}"

doc.save("mixer.tosc")
```
