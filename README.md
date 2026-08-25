# py2tosc

Roundtrip generation and editing of TouchOSC layouts (`.tosc`) from Python.

![Tests](https://github.com/shakfu/py2tosc/actions/workflows/tests.yaml/badge.svg) ![PyPI](https://img.shields.io/pypi/v/py2tosc) ![License](https://img.shields.io/github/license/shakfu/py2tosc)

```console
$ pip install py2tosc
```

No dependencies. Python 3.10 or newer. **[Documentation](https://shakfu.github.io/py2tosc)**

## Why

TouchOSC layouts are drawn by hand in a GUI editor, which is the right tool right up until the work is repetitive. Laying out a fader per parameter for a plugin with fifty-four of them, numbering an eight-by-eight pad grid, renaming two hundred controls, restyling everything, or keeping a layout in step with a config file -- all of it is an afternoon of clicking, or a few lines of Python:

```python
import py2tosc
from py2tosc import ui

faders = [py2tosc.fader(name=f"ch{n}", messages=[ui.midi_cc(n - 1)])
          for n in range(1, 9)]

doc = py2tosc.Document(root=ui.row(
    *faders,
    gap=4,
    pad=8,
    frame=(0, 0, 1024, 768),
    name="mixer",
))

# `ui.row` records how the faders should be arranged but cannot size them,
# since it runs before the frame above it exists. `resolve` walks the finished
# tree and divides that frame among them -- nothing has coordinates until it does.
doc.resolve()

doc.save("mixer.tosc")
```

It reads them back too, so a layout someone else drew is as editable as one you generated. Three things make that safe to do to a file you care about:

- **It round-trips exactly.** Loading a file and saving it again reproduces the editor's own bytes, in the compressed `.tosc`, the exported `.xml` and the [JSON encoding](https://shakfu.github.io/py2tosc/guide/json/) py2tosc adds. Everything in the corpus is checked that way on every commit, so an edit changes what you edited and nothing else.

- **It covers the whole format.** All thirteen control types, OSC, MIDI, local and gamepad bindings, Lua scripts, custom properties, and the two container types with rules of their own.

- **It can tell you when a layout is wrong** before TouchOSC does, and refuse to write one that is.

A `.tosc` file is a zlib-compressed XML tree; py2tosc is a careful binding to that tree plus a layer of convenience over it.

## Building a layout

`py2tosc` includes a combinator library, `py2tosc.ui`, built around the combinator pattern —- a style of library design in which components are constructed by combining simpler pieces.

A combinator here is a function that takes controls and returns a control, so its result is valid input to the next one and layouts nest by ordinary function composition -- `row(column(a, b), c)` -- with no special case for the outermost call or the innermost.

`py2tosc.ui` describes an arrangement and sizes it afterwards, so a layout is written from the inside out and nothing needs coordinates:

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

doc.resolve()  # hand the root frame down the tree, sizing everything
doc.save("mixer.tosc")
```

`row`, `column`, `tiles` and `stack` arrange controls inside a group; `pager` and `grid` build the two containers the format names. `resolve` hands the frame at the top down the tree.

```python
pads = [py2tosc.button(name=f"pad{n}") for n in range(1, 17)]
faders = [py2tosc.fader(name=f"ch{n}") for n in range(1, 9)]

doc = py2tosc.Document(root=ui.stack(
    ui.pager(
        ui.tiles(*pads, columns=4, gap=6, pad=6, name="pads"),
        ui.row(*faders, gap=6, pad=6, name="faders"),
        name="pages",
    ),
    frame=(0, 0, 568, 320),
    name="root",
))

doc.resolve()
```

`stack` overlays its children, which is how a caption goes on a button; `ui.labelled` is that plus a non-interactive label, and `ui.inset` shrinks one control within the frame its layout gave it.

The eager `py2tosc.layout` functions are still there and unchanged, for when you would rather place children against a parent you already have.

## Bindings

A control by itself sends nothing. A **binding** is a message attached to a control, which defines what it sends and what triggers it. The first line below creates a fader; the second attaches a binding to it.

```python
fader = py2tosc.fader(name="cutoff")
fader.messages.append(ui.osc("/synth/{parent.name}/{name}"))
```

With that fader inside a group named `comp`, moving it sends `/synth/comp/cutoff 0.62`: the address is resolved on the device when the message is sent, and the argument is the fader's current value. The braces are TouchOSC's templating, not Python's, so renaming the group or the control changes the address the layout sends without editing the binding.

What the file stores for that one line is four partials, a trigger and a pair of send/receive flags. `ui` returns exactly those objects and can reach nothing a hand-built `OscMessage` could not -- it is a shorter way to say the same thing, not a second vocabulary. `ui.midi_cc(74)` binds the same fader to a MIDI controller instead, and `ui.midi_note` does the same for notes.

`connect` wires one control to another in a line rather than seven keyword arguments:

```python
readout = py2tosc.label(name="readout")
key = py2tosc.button(name="C", messages=[
    ui.connect(readout, source=ui.prop("name"), to="text", on="RISE"),
])
```

Pressing the key writes `C` into the readout: the button sends its own `name` property to the label's `text` value, which is the value a label displays. A local binding stays inside the layout and sends nothing over the network, which is how twelve keys can share one readout instead of carrying twelve messages of their own.

**Both ends of a binding are addressed to a value**: the one that fires it, and the one it carries. `ui.osc()` defaults to `x` at both ends, which is right for a fader and wrong for a label -- a label carries `text` and `touch`, so a binding left on `x` never fires, and if anything did fire it would send `0`. Nothing about such a file is malformed, and TouchOSC will not tell you, which is why [validation](#checking-a-layout) reports both halves.

Copying a wired subtree remaps its local bindings, so the copy drives its own controls rather than the originals:

```python
strip = ui.stack(readout, key, name="strip")
second = strip.copy()
```

## Generating from data

The point of scripting a layout is usually that something else already knows what should be on it:

```python
PARAMETERS = ["Threshold", "Ratio", "Attack", "Release", "Knee", "Makeup"]

strips = [
    ui.labelled(
        py2tosc.fader(name=name.lower(), messages=[ui.midi_cc(cc)]),
        name,
    )
    for cc, name in enumerate(PARAMETERS)
]

doc = py2tosc.Document(root=ui.tiles(
    *strips,
    columns=3, gap=8, pad=8,
    frame=(0, 0, 600, 400), name="comp",
))

doc.resolve()
```

When the data is already a JSON file, `py2tosc build` does this without a script at all, and `py2tosc.surface` is the same thing from Python. A [layout description](https://shakfu.github.io/py2tosc/guide/ui-json/) can carry the same rows itself, which is the way to take when the generated part is one section of a larger layout rather than the whole of it.

`tests/demos/` has the longer version, building a paged MIDI and OSC surface from a plugin's exported parameter list, along with a numpad wired entirely with local messages and a rebuild of a layout TouchOSC ships.

## Editing an existing layout

`load` reads a `.tosc` or an exported `.xml` without being told which, and the tree it returns is the same one you would have built:

```python
doc = py2tosc.load("mixer.tosc")

for fader in doc.find_all(type="FADER"):
    fader.color = "#e76f51"
    fader.corner_radius = 2.0

doc.save("mixer-restyled.tosc")
```

### Finding things

```python
print(len(doc.find_all()), "controls")
for control in doc.walk():
    print(f"  {control.control_type.value:6} {control.get('name')}")

doc.find("cutoff")                  # by name
doc.find_all(type="FADER")          # by type
doc.find_all("send", type="BUTTON") # by both
```

Properties are attributes, in `snake_case`, translated to the file's camelCase at the boundary -- `control.corner_radius` addresses the `cornerRadius` key. Anything the format does not define is a custom property and is left alone, which is how TouchOSC scripts store their own state:

```python
readout = py2tosc.label(name="readout")

readout.set("max", "127")           # a key the format does not define, kept as-is
readout.script = """
function onValueChanged(key)
    print(key)
end
"""
```

## Reading a layout back as code

`to_python` writes a layout out as the script that would build it, which is what you want when the layout exists and the source does not:

```python
print(py2tosc.to_python(py2tosc.load("mixer.tosc")))
```

Every layout in the test corpus round-trips through its own generated script.

## Checking a layout

`validate` is advisory and never raises. It catches what TouchOSC will reject or quietly ignore -- children on a control that cannot hold them, a property belonging to a different control type, a binding addressed to a control that is not there -- and every rule is corroborated against layouts the editor itself wrote:

```python
for issue in doc.validate():
    print(issue)
#> error: root/panel/readout: BOX controls cannot hold children; this one has 1
```

`doc.save("out.tosc", validate=True)` writes nothing and raises if there are errors.

## Other formats

`save` picks the format from the extension, so exporting the readable XML the editor also writes is a matter of naming the file:

```python
doc.save("mixer.xml")
```

The XML is the format to reach for when a layout has to be read in a text editor or kept under version control.

A `.json` suffix writes [the JSON encoding](https://shakfu.github.io/py2tosc/guide/json/) instead: the same tree, round-tripping byte for byte like the XML, and easier to read a diff of at one line per property rather than five. `load` reads all three back, deciding from the content rather than the extension.

A second JSON dialect works the other way round. The encoding above records a layout that already exists, frames and all; [a description](https://shakfu.github.io/py2tosc/guide/ui-json/) states what nests in what and leaves the combinators to build it and `resolve` to size it:

```json
{
  "format": "py2tosc.ui",
  "root": {
    "column": [
      {"row": [{"fader": "ch$i", "messages": [{"midi_cc": "$i0"}], "repeat": 8}], "gap": 4},
      {"grid": "BUTTON", "columns": 8, "rows": 2, "name": "mutes"}
    ],
    "sizes": [3, 1], "gap": 8, "pad": 8, "frame": [0, 0, 1024, 768]
  }
}
```

`py2tosc.load` builds and resolves that like any other layout. It exists for when the layout is decided by something that is not code -- a config file people who do not write Python have to review, a web tool, another program -- and it repeats over rows of data as well as over a counter, so a parameter list can drive one part of a layout while the rest is written by hand. It is read and never written: a resolved layout has frames and no memory of the row that placed them, so `save` always writes the faithful encoding.

## From the command line

Installing py2tosc also puts a `py2tosc` command on your path, because most of what is above is file-shaped and should not need a script written first:

```console
$ py2tosc show mixer.tosc
mixer.tosc  lexml 6
  3 controls: GROUP 1, FADER 1, LABEL 1
  2 messages: Midi 1, Osc 1

GROUP  (0, 0, 640, 860)  2 children
  FADER   'fader1'  (77, 60, 50, 200)
  LABEL   'label1'  (60, 275, 80, 25)
```

| | |
|-|-|
| `show` | What is in a layout, and its tree. |
| `validate` | What TouchOSC will reject, exiting non-zero if any of it is an error. |
| `decompile` | The layout written out as the Python that builds it. |
| `convert` | The same layout as `.tosc`, `.xml` or `.json`, chosen by the output's extension. |
| `build` | A control surface generated from a list of parameters. |

`validate` is the one worth automating. It exits `0` on a clean layout, `1` on one with errors and `2` on a bad command line, so it works in a pre-commit hook or a CI job without a wrapper:

```console
$ py2tosc validate mixer.tosc
mixer.tosc: clean
```

`build` takes JSON -- a list of names, or objects where only `name` is required and `cc` and `channel` are optional -- and lays it out across as many pages as it needs, a fader per parameter bound to both MIDI and OSC:

```console
$ py2tosc build params.json -o surface.tosc
4 parameters -> 1 page, 15 controls -> surface.tosc
```

`--midi-only` and `--osc-only` leave out the other binding, `--columns` and `--rows` set the shape of each page, and `--size 320x480` sets the canvas.

## Design

| Module | Holds |
|--------|-------|
| `enums` | TouchOSC's own vocabulary: control types, property types, conversions, and the names behind the numbers a property stores |
| `properties` | `Property`, `Frame`, `Color`, and the `snake_case` to camelCase mapping |
| `messages` | `Value`, `OscMessage`, `MidiMessage`, `LocalMessage`, `GamepadMessage` and their parts |
| `defaults` | The default property set for each control type |
| `control` | `Control`, the node model, plus a factory per control type |
| `codec` | Reading and writing the `.tosc` XML dialect, CDATA included |
| `json_codec` | The same tree as JSON, for emitting a layout from elsewhere or reading a diff of one |
| `ui_json` | A layout *described* in JSON and built by the combinators, for when the layout is decided by a config file rather than by code |
| `document` | `Document`, `load`, `save`, `dumps` |
| `layout` | Eager `row`, `column` and `matrix`: make the children and size them now |
| `ui` | Message and layout combinators, described now and sized by `resolve` |
| `codegen` | `to_python`, a layout written back out as source |
| `validate` | The optional checks, and the `Issue` they report |
| `surface` | A paged control surface built from a list of parameters |
| `cli` | The `py2tosc` command |

`grid` names the `GRID` control everywhere and nothing else: `py2tosc.grid` is the bare control and `ui.grid` builds one with its cells. Arranging controls you already have is `ui.tiles`, and the eager equivalent is `layout.matrix`.

The `ui` module is separate from the core deliberately. `control`, `codec` and `messages` bind to a format someone else defines and age at the speed of TouchOSC; `ui` encodes opinions about how interfaces are composed, and opinions age faster. `ui` is therefore provisional: it may change in a minor release, where the rest of the API may not. See the [stability policy](https://shakfu.github.io/py2tosc/stability/) for what is covered.

## Credits

py2tosc is a rewrite of [tosclib](https://github.com/AlbertoV5/tosclib) by [Alberto Valdez](https://github.com/AlbertoV5), whose work established the original mapping between the `.tosc` format and Python that this library is built on. The API is new and incompatible, but the knowledge of the format -- the control types, the property tables, the message layouts, and some of the tests and examples -- came from there, and is carried over with thanks. Original copyright is retained in [LICENSE](LICENSE).

**Disclaimer**: This project has no relation to Hexler, the developer of TouchOSC. Back up your layouts before editing them with third party tools.
