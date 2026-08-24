# Describing a layout in JSON

There are two JSON dialects here, and they are opposites. [The .json format](json.md) is the node tree exactly as the file holds it, frames and all, and it round-trips byte for byte. This one describes a layout that does not exist yet -- what nests in what, and how the space gets divided -- and hands it to [`py2tosc.ui`](layouts.md) to build and size.

## The same layout twice

A mixer: eight faders bound to both MIDI and OSC, a row of mute buttons under them, in a canvas divided three to one.

```json
--8<-- "tests/data/mixer.ui.json"
```

<!-- checked: the same layout in Python -->

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

doc = py2tosc.Document(
    root=ui.column(
        ui.row(*faders, gap=4),
        ui.grid("BUTTON", columns=8, rows=2, name="mutes"),
        sizes=(3, 1),
        gap=8,
        pad=8,
        name="mixer",
        frame=(0, 0, 1024, 768),
    )
).resolve()
```

Both produce the same 27 controls, with the same names, the same frames and the same bindings. `tests/test_ui_json.py` builds each of them and compares, so the two halves of this page cannot drift apart.

Line for line the mapping is mechanical:

| JSON | Python |
|------|--------|
| `{"column": [...], "sizes": [3, 1]}` | `ui.column(*children, sizes=(3, 1))` |
| `{"row": [...], "gap": 4}` | `ui.row(*children, gap=4)` |
| `{"repeat": 8, "of": {...}}` | the list comprehension |
| `{"fader": "ch$i"}` | `py2tosc.fader(name=f"ch{n}")` |
| `{"osc": "/mixer/{name}"}` | `ui.osc("/mixer/{name}")` |
| `{"midi_cc": "$i0"}` | `ui.midi_cc(n - 1)` |
| `{"grid": "BUTTON", "columns": 8, "rows": 2}` | `ui.grid("BUTTON", columns=8, rows=2)` |
| the envelope, and `load` | `Document(root=...).resolve()` |

**The Python is shorter, and if you are writing Python, write Python.** This dialect is for when the layout is decided by something that is not code: a config file that people who do not write Python have to review, a web tool emitting layouts, another program generating them. What it saves those callers is not typing -- it is having to get CDATA sections, sorted property order and the geometry right in a language that has no py2tosc.

## Reading one

```python
import py2tosc

doc = py2tosc.load("mixer.ui.json")   # built and resolved, ready to save
doc.save("mixer.tosc")
```

`py2tosc.ui_json.from_json(text)` is the same without a file. From the command line every subcommand takes one, because what a file holds rather than what it is called decides how it is read:

```console
$ py2tosc show mixer.ui.json
$ py2tosc validate mixer.ui.json
$ py2tosc convert mixer.ui.json -o mixer.tosc
```

Which of the two JSON dialects a file is written in is decided by its `format`, which is why this one is required where the faithful encoding's is optional.

**It is read and never written.** A resolved layout has frames and no memory of the `row` that placed them, so there is no way back: `save` writes the faithful encoding whatever the document was built from. This is the only asymmetry in the library, and it is a property of the problem rather than an omission.

## Four rules

**One key names the thing.** Every node carries exactly one key from the tag table, and everything else is an argument to it. `{"row": [...], "gap": 4}` is `ui.row(*children, gap=4)`, mechanically. Where a key could be either a tag or a property -- `grid` is a control *and* the switch that draws grid lines on a fader -- the tag loses if something else in the object is already one, so `{"fader": "ch1", "grid": false}` is a fader with its grid lines off.

**The value is the tag's one positional argument.** Children for the combinators that arrange them, the control type for `grid`, the control being wrapped for `labelled` and `inset`, and the *name* for a plain control, since a name is what a control almost always has. `{"fader": "ch1"}` is `fader(name="ch1")`.

**`repeat` expands in place.** It is a child rather than a setting on its parent, so it works anywhere children are accepted, and a list can mix repeated and hand-written children freely.

**A sibling key that is not an argument is a property.** Checked against what the type accepts, in either `snake_case` or camelCase, so a mistyped `gpa` is a message rather than a custom property nobody asked for. Genuinely custom keys go under `props`.

## The tags

| Tag | Value | Arguments | Builds |
|-----|-------|-----------|--------|
| `row`, `column` | children | `sizes`, `gap`, `pad` | a `GROUP`, divided along one axis |
| `tiles` | children | `columns`, `rows`, `gap`, `pad` | a `GROUP`, filled row by row |
| `stack` | children | `pad` | a `GROUP`, children overlaid |
| `pager` | pages | `pad` | a `PAGER` |
| `grid` | control type | `columns`, `rows` | a `GRID`, filled with its own cells |
| `group` | children | -- | a `GROUP` that arranges nothing |
| `labelled` | one node | `caption`, `size`, `inset` | the control with a label under it |
| `inset` | one node | `by` | the control, shrunk within its frame |
| `box`, `button`, `encoder`, `fader`, `label`, `radar`, `radial`, `radio`, `text`, `xy` | the name | -- | that control |

Each is the [`ui`](../api/ui.md) function of the same name, so what a tag does and what its arguments mean is documented once, there, rather than twice. Two names differ deliberately. `labelled` calls its text `caption`, because `text` is the name of a control and a key that could be either would make the tag ambiguous for nothing. `inset` takes its amount as `by`, and that amount is a fraction of the frame rather than a number of points, exactly as `ui.inset` does.

Any node may also carry:

| Key | |
|-----|--|
| `id` | Pin a node id rather than have one minted. Needed only when something outside the file refers to it. |
| `values` | Replace the control's live state, as `[{"key": "x", "default": 0.5}]`. |
| `messages` | The control's bindings. |
| `props` | Properties the type does not declare -- the [custom properties](custom-properties.md) escape hatch, and the only place an unrecognised key is allowed. |

## Repeating

```json
{"row": [
  {"fader": "master"},
  {"repeat": 8, "of": {"fader": "ch$i", "messages": [{"midi_cc": "$i0"}]}}
], "gap": 4}
```

builds nine faders: `master`, then `ch1` through `ch8` on controllers 0 to 7.

| Key | |
|-----|--|
| `repeat` | How many. Required, and at least one. |
| `of` | The node to repeat. Required. |
| `from` | Where the counter starts. Defaults to 1. |
| `as` | What to call the counter. Defaults to `i`. |

A repeat binds two counters: `$i` counting from `from`, and `$i0` counting from zero whatever `from` says. `$name` and `${name}` are both accepted, and the braces are how a counter is written with a digit after it -- `${i}0` gives `10`, `20`, where `$i0` is the zero-based counter itself.

**A lone counter keeps its type.** `"$i0"` becomes the number `0`, which is what a controller number wants, while `"ch$i"` becomes the string `"ch1"`. This is the only reason a controller number can be repeated at all.

**A `$` is only special inside a repeat.** Everywhere else it is an ordinary character, so a Lua script full of them needs no thought. Inside one, write `$$` for a literal dollar sign; a counter nobody bound is an error rather than a name with a `$` left in it.

**Repeats nest, and each names its own counter.** The outer pass leaves the inner pass's counters alone, so both are readable in the innermost node:

```json
{"repeat": 2, "as": "bank", "of": {
  "row": [{"repeat": 3, "of": {"button": "b$bank-$i"}}]
}}
```

builds `b1-1`, `b1-2`, `b1-3`, `b2-1`, `b2-2`, `b2-3`.

What a repeat cannot do is arithmetic. There is no `$i * 2`, and adding one would mean an expression language inside a JSON string, which is a bigger thing than this format is. Two ways round it: `from` moves where a counter starts, and a layout driven by data rather than by counting -- a name and a controller number per parameter -- is what [`py2tosc build`](../cli.md#build) takes a parameter list for.

## Bindings

```json
"messages": [
  {"osc": "/mixer/{name}", "on": "RISE"},
  {"midi_cc": 7, "channel": 2},
  {"midi_note": 60},
  {"connect": "readout", "source": "x", "to": "text"}
]
```

Each binding is tagged with the [combinator](../api/ui.md) that builds it -- `osc`, `midi_cc`, `midi_note` or `connect` -- whose one positional argument is the value and whose keyword arguments are the other keys.

`{name}` in an OSC address is TouchOSC's own templating, resolved on the device when the message is sent, and it is a different thing from `$i`, which is resolved here while the file is being read. The two use different syntax precisely so that neither can consume the other.

`connect` names the control it writes to, rather than carrying a node id nothing in a hand-written file could know. Names are looked up once the whole tree exists, so a binding can point forwards, backwards or out of its own branch. A name matching no control, or more than one, is an error saying which.

What is not expressible: the arguments that take [partials](messages.md) -- `args` on an OSC binding, and `triggers` on any of them. Those describe a value being assembled piece by piece, which is a small language of its own, and a layout needing one is a layout to build in Python. Saying so is the format's job: `args` is refused with that explanation rather than ignored.

## Sizes and the canvas

Nothing here has coordinates. The combinators record an arrangement, and `resolve` divides the root's frame among everything below it -- which is why `frame` on the root is the one measurement most descriptions state, and why a control inside a `row` states none. A root with no frame of its own gets `1024x768`, matching `Document.new`.

A `frame` on a control that a layout is placing is overwritten by that layout, exactly as it is in Python. Inside a `group`, which arranges nothing, it is kept -- which is what `group` is for.

See [Layout sizes](sizes.md) for what a canvas is and how to choose one, and [Layouts](layouts.md) for what each combinator does with the space it is given.

## Shapes worth copying

A pager, one page per section:

```json
{"pager": [
  {"tiles": [{"repeat": 16, "of": {"button": "pad$i"}}], "columns": 4, "name": "pads"},
  {"row": [{"repeat": 8, "of": {"fader": "ch$i"}}], "gap": 6, "name": "faders"}
], "name": "pages", "frame": [0, 0, 568, 320]}
```

A button with a caption over it, which is what `labelled` and `stack` are for:

```json
{"labelled": {"button": "play"}, "caption": "Play", "size": 40}
```

A bank of encoders, each on its own controller, numbered from 20:

```json
{"tiles": [
  {"repeat": 12, "from": 20, "of": {
    "encoder": "enc$i", "messages": [{"midi_cc": "$i"}]
  }}
], "columns": 4, "gap": 6, "pad": 6}
```

A button that writes into a readout elsewhere in the layout:

```json
{"column": [
  {"button": "go", "messages": [{"connect": "readout", "source": "x", "to": "text"}]},
  {"label": "readout"}
]}
```

## When it will not build

Every message names the node it gave up on, by the path from the root:

```text
root.column[0]: unknown key 'gpa'; did you mean 'pad' or 'gap'?
root.row[0]#1: unknown key 'colour'; did you mean 'color'?
root.messages[0]: no control is named 'readout'
root: nothing here names a control or a layout; expected one of box, button, ...
```

The `#1` is which pass of a `repeat` failed. Every copy is built from one template, so ordinarily they all fail together -- but a counter that lands somewhere only some values are legal will not, and the pass number is what says which.

A description that builds but cannot be divided says that too -- a row whose gaps are wider than its frame, a `tiles` with no columns -- rather than failing later with something out of the geometry.

Reading a file only says it could be built. Whether TouchOSC will accept the result is a separate question, and the answer is [validation](validation.md):

```console
$ py2tosc validate mixer.ui.json
mixer.ui.json: clean
```

## Stability

This dialect is a description of what `py2tosc.ui` does, so it inherits `ui`'s carve-out from the [stability policy](../stability.md): it may change in a minor release, where the faithful encoding may not. It carries a `schema` number for the case where a change would stop an already written description from building.

Nothing it produces is unusual. What comes out is an ordinary `Control` tree, indistinguishable from one built in Python, so if the dialect ever becomes inconvenient the layouts it built remain valid.
