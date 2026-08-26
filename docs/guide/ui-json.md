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
| `"repeat": 8` on the node | the list comprehension |
| `{"fader": "ch$i"}` | `py2tosc.fader(name=f"ch{n}")` |
| `{"osc": "/mixer/{name}"}` | `ui.osc("/mixer/{name}")` |
| `{"midi_cc": "$i0"}` | `ui.midi_cc(n - 1)` |
| `{"grid": "BUTTON", "columns": 8, "rows": 2}` | `ui.grid("BUTTON", columns=8, rows=2)` |
| the envelope, and `load` | `Document(root=...).resolve()` |
| `"//"` | the comment above it |

**The Python is more capable, and if you are writing Python, write Python.** It has names, arithmetic and f-strings, where a description has counters, [rows of data](#repeating-over-data) and no way to add two numbers -- which is the difference that decides between them. Length is not the difference: the JSON above is 17 lines to the Python's 22. This dialect is for when the layout is decided by something that is not code: a config file that people who do not write Python have to review, a web tool emitting layouts, another program generating them. What it saves those callers is not typing -- it is having to get CDATA sections, sorted property order and the geometry right in a language that has no py2tosc.

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

**`repeat` expands in place.** It is a child rather than a setting on its parent, so it works anywhere children are accepted, and a list can mix repeated and hand-written children freely. A node repeats *itself* -- `{"fader": "ch$i", "repeat": 8}` -- or holds the node it repeats under `of`.

**A sibling key that is not an argument is a property.** Checked against what the type accepts, in either `snake_case` or camelCase, so a mistyped `gpa` is a message rather than a custom property nobody asked for. Genuinely custom keys go under `props`.

Which means a node's siblings are two different things wearing the same clothes. In `{"row": [...], "gap": 4, "color": "ff0000ff"}`, `gap` is an argument to `ui.row` and `color` is a TouchOSC property that ends up in the file; nothing marks them apart. That is deliberate. A reader almost never needs to know which is which -- both are "something about this node" -- and a key that is neither gets an error naming the nearest of both sets. Nesting the arguments to separate them (`{"row": {"children": [...], "gap": 4}}`) would cost a level of structure on every node to document a distinction that only the reader of `ui_json.py` has to care about.

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

Each is the [`ui`](../api/ui.md) function of the same name, so what a tag does and what its arguments mean is documented once, there, rather than twice.

Two argument names differ from `ui`'s, and both follow one rule: **an argument is renamed when its natural name is already a tag.** `labelled` calls its text `caption`, because `text` is a control. `inset` takes its amount as `by`, because `inset` is a combinator -- and that amount is a fraction of the frame rather than a number of points, exactly as `ui.inset` is. Nothing else collides, so nothing else is renamed.

A collision can be settled the other way instead, by making the *tag* lose: `{"fader": "ch1", "grid": false}` is a fader with its grid lines off, and `{"label": "readout", "text": "Hello"}` is a label with something to say. Which way a collision goes is fixed and small -- three tags lose, two arguments are renamed -- and a test pins the list, so it cannot grow without someone deciding that it should.

Any node may also carry:

| Key | |
|-----|--|
| `id` | Pin a node id rather than have one minted. Needed only when something outside the file refers to it. |
| `values` | Replace the control's live state, as `[{"key": "x", "default": 0.5}]`. |
| `text` | What a `LABEL` says, which is a *value* rather than a property: `{"label": "readout", "text": "Hello"}`. Only on the types that carry one, and not alongside `values`, which sets the same thing the long way. A `TEXT` control sets its own with `values`, since the tag has taken the key. |
| `messages` | The control's bindings. |
| `props` | Properties the type does not declare -- the [custom properties](custom-properties.md) escape hatch, and the only place an unrecognised key is allowed. |

`messages` on a node lands on whatever that node builds, which for `labelled` is the *group* holding the control and its caption rather than the control. That is worth knowing because a binding left on its default trigger fires on `x`, and a group carries only `touch` -- [validation](validation.md) reports it. Put the binding on the node inside `labelled` unless the group is what you meant.

## Repeating

```json
{"row": [
  {"fader": "master"},
  {"fader": "ch$i", "messages": [{"midi_cc": "$i0"}], "repeat": 8}
], "gap": 4}
```

builds nine faders: `master`, then `ch1` through `ch8` on controllers 0 to 7.

| Key | |
|-----|--|
| `repeat` | How many. Required, and at least one. |
| `of` | The node to repeat. Optional: without it, the node carrying `repeat` is the one repeated. |
| `from` | Where the counter starts. Defaults to 1. |
| `as` | What to call the counter. Defaults to `i`. |

**A repeat is the node it repeats, or holds one under `of`.** These are the same eight faders:

```json
{"fader": "ch$i", "repeat": 8}
```

```json
{"repeat": 8, "of": {"fader": "ch$i"}}
```

The short form puts the thing being built first, which is the same instinct as one key naming the thing, and costs a nesting level less. The long form keeps a large template separate from the count, which reads better once the template is more than a line or two. A node cannot do both -- a `repeat` beside both a tag and an `of` is refused rather than guessed at -- and `repeat` outside a list of children is refused too, since there is nowhere for the copies to go.

A repeat binds two counters: `$i` counting from `from`, and `$i0` counting from zero whatever `from` says. `$name` and `${name}` are both accepted, and the braces are how a counter is written with a digit after it -- `${i}0` gives `10`, `20`, where `$i0` is the zero-based counter itself.

**A lone counter keeps its type.** `"$i0"` becomes the number `0`, which is what a controller number wants, while `"ch$i"` becomes the string `"ch1"`. This is the only reason a controller number can be repeated at all.

**A `$` is only special inside a repeat -- but inside one it is special everywhere.** Outside, it is an ordinary character and nothing looks at it, so a Lua script full of them needs no thought. Inside, *every* string in the repeated node is substituted into, including a `script` and the text of a label, so a `$` that is not a counter has to be written `$$` there and only there. A name nobody bound is an error rather than a `$` left standing, which is what makes the rule safe: a script carried into a repeat cannot silently lose a character.

**Repeats nest, and each names its own counter.** The outer pass leaves the inner pass's counters alone, so both are readable in the innermost node:

```json
{"row": [{"button": "b$bank-$i", "repeat": 3}], "repeat": 2, "as": "bank"}
```

builds `b1-1`, `b1-2`, `b1-3`, `b2-1`, `b2-2`, `b2-3`, and does the same written the long way round:

```json
{"repeat": 2, "as": "bank", "of": {
  "row": [{"repeat": 3, "of": {"button": "b$bank-$i"}}]
}}
```

The forms mix freely, since which one an inner repeat uses is its own business.

### Repeating over data

Counting only reaches layouts that *are* a sequence. A numpad's keys read 7, 4, 1, 8, 5, 2, 9, 6, 3, and a mixer's channels have names rather than numbers. **`each` walks a list of rows instead of counting**, binding every field of the current row the way `repeat` binds its counter:

```json
{"each": [
  {"n": "kick", "cc": 20},
  {"n": "snare", "cc": 24},
  {"n": "hat", "cc": 31}
], "of": {"fader": "$n", "messages": [{"midi_cc": "$cc"}]}}
```

builds three faders named for their drums, each on its own controller. It takes the short form too, which is usually what you want -- the template first, the data under it:

```json
{"fader": "$n", "messages": [{"midi_cc": "$cc"}], "each": [...]}
```

| | |
|-|-|
| `each` | The rows. Required unless `repeat` is, and the two cannot both appear. |
| `of` | The node to build once per row. Optional, exactly as it is for `repeat`. |
| `from`, `as` | As for `repeat`: `$i` and `$i0` are bound alongside the row's fields. |

A field is read as `$name`, so a key that cannot be written that way is refused rather than left unreachable, and a field named after the counter is refused rather than one of them silently winning. A row holds strings, numbers and booleans; a lone `"$cc"` keeps its type exactly as `"$i0"` does, and a boolean written into a longer string comes out as `true` rather than Python's `True`.

**An `each` of nothing builds nothing.** A generator with nothing to emit writes `[]`, which is data running out rather than a mistake -- where `repeat: 0` is refused, because nobody writes one on purpose.

This is also what closes the gap with [`py2tosc build`](../cli.md#build), which takes a list of parameters and lays out a surface from it. A description can now say the same thing, and say the rest of the layout around it.

### Rows that are not all the same kind

One `each` builds one kind of thing, because substitution reaches values and never keys: the tag is written in the template, so a row can change what a control is *called*, *bound to* and *numbered*, but not what it *is*. A table generated from a plugin's parameters is mixed by nature -- a bypass wants a `button`, a waveform selector wants a `radio`, a cutoff wants a `fader`.

**`case` reads a field and `when` holds a complete node per value it can take.** The `of` holds the table instead of a node:

```json
{
  "each": [
    {"kind": "cont", "name": "cutoff", "cc": 74},
    {"kind": "sw",   "name": "bypass", "cc": 75},
    {"kind": "cont", "name": "reso",   "cc": 76}
  ],
  "of": {"case": "$kind", "when": {
    "cont": {"fader":  "$name", "messages": [{"midi_cc": "$cc"}]},
    "sw":   {"button": "$name", "messages": [{"midi_cc": "$cc"}]}
  }}
}
```

which builds a fader, a button and a fader, in that order -- the order the rows are in, which for a generated table is the order the plugin author chose.

| | |
|-|-|
| `case` | The string whose substituted value names the branch. Usually one field, `"$kind"`, but any string that substitutes will do. |
| `when` | The branches, keyed by the value that selects them. Each is a complete node, and at least one is required. |

**Every key is still literal.** No key anywhere is built from a row, so every branch is checked against the tag table before any row is looked at -- a branch naming two tags, or none, is refused whether or not a row happens to reach it. That checkability is the reason keys are not substituted in the first place, and `{"$kind": "$name"}` would also read worse than what it replaced.

**Only the branch a row selects is substituted into**, so a branch reads the fields its own rows carry and no others. A `sw` row needs no `steps` field for a `radio` branch that mentions one.

**A branch nothing selects is not an error.** An `each` of nothing is already the thing a generator with nothing to emit writes, and that leaves every branch unselected -- so a hand-written template carrying a branch for a kind this particular table has no rows of is the same shape, and gets the same answer. A row selecting a branch that was *not* written is an error, and it names the value it read.

The selector is matched as the file spells it: a number reads as `"1"`, a boolean as `"true"`. A counting `repeat` can choose too -- `{"case": "$i", "when": {...}}` -- though a layout that varies by position usually reads better written out.

This is a schema 2 feature. A description using it will not build on a release that reads only schema 1, which is what the number is for.

### Arithmetic, and what to do instead

What a repeat still cannot do is arithmetic. There is no `$i * 2`, and adding one would mean an expression language inside a JSON string, which is a bigger thing than this format is. Two ways round it: `from` moves where a counter starts, and `each` puts the number in the data, where a generator or a person can compute whatever they like before writing the file.

## Comments

JSON has no comment, and a description written to be reviewed needs somewhere to say why a number is what it is. **A key beginning with `//` is ignored**, wherever a key may appear -- the envelope, a node, a binding, a value, and inside `props`:

```json
{
  "//": "front-of-house send, 8 channels to match the desk",
  "column": [
    {"fader": "ch$i", "// cc": "20 up, leaving 0-19 to the transport", "from": 20, "repeat": 8}
  ]
}
```

More than one to an object, since JSON keys have to be unique: `"//"`, `"// why"`, `"//left-at-8"`. A comment is dropped before anything reads the node, so it never reaches the file, is never mistaken for a custom property, and is not substituted into -- a note about a layout can mention `$5` inside a repeat without meaning a counter.

## Bindings

```json
"messages": [
  {"osc": "/mixer/{name}", "on": "RISE"},
  {"midi_cc": 7, "channel": 2},
  {"midi_note": 60},
  {"connect": "readout", "source": "x", "to": "text"}
]
```

**This is the same rule as a node, one level down.** One key names the thing -- `osc`, `midi_cc`, `midi_note` or `connect`, each the [combinator](../api/ui.md) of that name -- its value is that combinator's one positional argument, and the siblings are its keyword arguments. A [partial](#partials) is the same shape again, one level below that. Three levels, one rule: if you can read a node you can read a binding, and there is nothing else to learn.

`{name}` in an OSC address is TouchOSC's own templating, resolved on the device when the message is sent, and it is a different thing from `$i`, which is resolved here while the file is being read. The two use different syntax precisely so that neither can consume the other.

`connect` names the control it writes to, rather than carrying a node id nothing in a hand-written file could know. Names are looked up once the whole tree exists, so a binding can point forwards, backwards or out of its own branch. A name matching no control, or more than one, is an error saying which.

### Partials

What a binding *sends* is assembled from [partials](messages.md), and each one is an object naming what it reads -- one key names the thing, as everywhere else:

| Partial | Reads |
|---------|-------|
| `{"value": "x"}` | one of the control's own values |
| `{"prop": "name"}` | one of its properties; dotted lookups reach upwards, as in `parent.name` |
| `{"const": "#7"}` | the text itself, sent unchanged |
| `{"index": null}` | where the control sits within its parent. It reads nothing else, so its value is `null` |

Each takes `conversion` and `scale` alongside, exactly as [`ui.value`](../api/ui.md) and the other three do. A partial goes wherever `ui` takes one:

```json
"messages": [
  {"osc": "/mix", "args": [{"value": "text", "conversion": "STRING"}, {"index": null}]},
  {"midi_note": {"prop": "name"}, "channel": {"index": null}},
  {"connect": "readout", "source": {"const": "#7"}, "to": "text", "on": "RISE"}
]
```

The second is a keyboard whose buttons name their own notes. The third is a key sending a marked constant into a readout, which is what a numpad does.

**A bare string keeps the meaning `ui` gives it**: in `source` and `to` it names one of the control's *values*, so `"source": "x"` is `{"value": "x"}` written short. That is why a constant has to say so -- `"source": "#7"` is a binding that reads a value called `#7`, which nothing has. In `args`, where the two readings are equally plausible and neither is safe to guess, a bare string is refused and the message names both spellings.

**`triggers` replaces `on` and `var` entirely**, for a binding that watches more than one value -- an XY sending on both axes, which is what all 39 multi-trigger messages in the corpus are:

```json
{"osc": "/pad", "triggers": [{"var": "x"}, {"var": "y"}]}
```

Each is `{"var": ..., "on": ...}`, defaulting to `x` and `ANY`. Nothing in `py2tosc.ui` is now beyond this dialect.

## Sizes and the canvas

Nothing here has coordinates. The combinators record an arrangement, and `resolve` divides the root's frame among everything below it -- which is why `frame` on the root is the one measurement most descriptions state, and why a control inside a `row` states none. A root with no frame of its own gets `1024x768`, matching `Document.new`.

A `frame` on a control that a layout is placing is overwritten by that layout, exactly as it is in Python. Inside a `group`, which arranges nothing, it is kept -- which is what `group` is for.

See [Layout sizes](sizes.md) for what a canvas is and how to choose one, and [Layouts](layouts.md) for what each combinator does with the space it is given.

## Shapes worth copying

A pager, one page per section:

```json
{"pager": [
  {"tiles": [{"button": "pad$i", "repeat": 16}], "columns": 4, "name": "pads"},
  {"row": [{"fader": "ch$i", "repeat": 8}], "gap": 6, "name": "faders"}
], "name": "pages", "frame": [0, 0, 568, 320]}
```

A button with a caption over it, which is what `labelled` and `stack` are for:

```json
{"labelled": {"button": "play"}, "caption": "Play", "size": 40}
```

A bank of encoders, each on its own controller, numbered from 20:

```json
{"tiles": [
  {"encoder": "enc$i", "messages": [{"midi_cc": "$i"}], "repeat": 12, "from": 20}
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
root.column[1]: color: 'nope' is not a 6 or 8 digit hex colour
root.messages[0]: no control is named 'readout'
root: nothing here names a control or a layout; expected one of box, button, ...
```

The `#1` is which pass of a `repeat` failed. Every copy is built from one template, so ordinarily they all fail together -- but a counter that lands somewhere only some values are legal will not, and the pass number is what says which. A value the control cannot take names its key as well as its node, because a node can carry twenty properties and only one of them is wrong.

A description that builds but cannot be divided says that too -- a row whose gaps are wider than its frame, a `tiles` with no columns. Those are reported once the frames are handed down rather than while the file is read, since a layout only fails against a size, so they name the *control* rather than the node in the file:

```text
the layout will not resolve: mixer/faders: a width of 100 cannot hold 2 slots with 50/50 padding and 100 between them
the layout will not resolve: mixer: column was given 1 sizes for 2 children
```

The path is the names on the way down, as [validation](validation.md) reports them, and a control with no name of its own appears as `<GROUP>`.

Reading a file only says it could be built. Whether TouchOSC will accept the result is a separate question, and the answer is [validation](validation.md):

```console
$ py2tosc validate mixer.ui.json
mixer.ui.json: clean
```

## Checking a description without py2tosc

`py2tosc validate` is the check when py2tosc is installed. When it is not -- which is the ordinary case for the program *writing* these files -- `scripts/check_json.py` in this repository is a single file with no imports beyond the standard library, meant to be copied into that program's own tree:

```console
$ python check_json.py synth.ui.json
synth.ui.json: warning: <envelope>: the description declares schema 1 and uses schema 2; a release reading only schema 1 will refuse it with a message about a node
```

```python
from check_json import check

problems = check(json.loads(text))
assert not problems, problems
```

It reads both dialects, telling them apart by `format` exactly as `py2tosc.load` does, and exits `0`, `1` and `2` on the same meanings the [CLI](../cli.md#exit-codes) gives them. This is what makes the schema stamp checkable by the only party that can get it right: a generator can assert in its own test suite that the file it wrote is well formed and stamps what it needs, without putting the compiler in its dependency list.

It is deliberately conservative. Everything it calls an error, py2tosc refuses too, so a false positive would be the failure that matters; the reverse is not promised, because it resolves nothing and so cannot see a layout that will not fit, a `sizes` that does not match its children, or a property value that will not coerce. What it does see is the failure class the dialect exists to close -- a key nothing reads -- plus a `$name` no repeat binds, a binding a control cannot carry, and a schema stamped below what the file uses.

Its tables are generated from py2tosc by `scripts/make_check_json.py` and compared against the live ones by `tests/test_check_json.py`, so a copy that has gone stale is a failing test here rather than a wrong answer somewhere else. A description declaring a schema newer than the tables know says so, and says to regenerate.

## Stability

This dialect is a description of what `py2tosc.ui` does, so it inherits `ui`'s carve-out from the [stability policy](../stability.md): it may change in a minor release, where the faithful encoding may not. It carries a `schema` number of its own for the case where a change would stop an already written description from building, and it is at 2.

**The `schema` key is the producer's to stamp.** This is the one format here written by something other than py2tosc, and a description carrying no `schema` means "whatever the reader is" -- harmless in a file a person wrote and opened once, and the ambiguity a version number exists to remove in one a program emits. `py2tosc.ui_json.required_schema(data)` is the number to stamp -- the lowest schema that builds that description -- so a generator can ask rather than remember. On the reading side, `SCHEMAS` is every schema the installed release builds and `supports(n)` asks about one, so a generator can also check that the release it is running against will read what it is about to write. A schema above the range is a `SchemaError` rather than a bare `FormatError`, because it is the one reading failure whose remedy is not in the file.

Understating the stamp is the mistake nothing catches by building, because the reader that could catch it is by definition new enough to build the file -- it is caught by whoever opens it on an older release, and what they see is a message about a node. So `py2tosc validate` warns on a description that declares less than it uses, or that stamps nothing while using something new:

```console
$ py2tosc validate synth.ui.json
warning: <envelope>: the description declares schema 1 and uses schema 2; a release reading only schema 1 will refuse it with a message about a node
```

One limit is worth knowing. `required_schema` detects spellings, not meanings: a schema that changed what an existing spelling *does* leaves a description textually identical, so it reports the older number and the warning stays quiet. For that class the guard is a file of expected output, not a version number.

Nothing it produces is unusual. What comes out is an ordinary `Control` tree, indistinguishable from one built in Python, so if the dialect ever becomes inconvenient the layouts it built remain valid.
