# The .json format

A `.tosc` is a zlib-compressed XML tree, and that tree is what TouchOSC defines. py2tosc can also read and write the same tree as JSON, which is a second encoding of one model rather than a second model: a layout can go out to JSON and come back byte for byte the file it started as.

This exists for the two jobs the XML does badly.

- **Emitting a layout from something that is not Python.** The XML has rules that are easy to get subtly wrong -- keys and string values in `CDATA`, properties written in sorted order, elements omitted rather than written empty. A JSON emitter has none of that to get right.
- **Reading a diff.** A layout under version control is a file people have to review. The one-fader layout below is 72 lines of JSON against 254 lines of the XML export, with one line per property rather than five.

It is not a different way to *design* a layout. Every key is the file's own, and nothing here is shorter to hand-write than the Python in [Layouts](layouts.md).

## Reading and writing one

The extension chooses on the way out, and the content decides on the way in:

```python
import py2tosc

doc = py2tosc.load("mixer.tosc")
doc.save("mixer.json")          # the JSON encoding
doc = py2tosc.load("mixer.json")  # read back, and identical
doc.save("mixer.tosc")
```

`py2tosc.to_json(doc)` and `py2tosc.from_json(text)` are the same thing without a file in the middle. From the command line, `convert` follows the output's extension and every other subcommand accepts a `.json` where it accepts a `.tosc`:

```console
$ py2tosc convert mixer.tosc -o mixer.json
$ py2tosc show mixer.json
$ py2tosc validate mixer.json
```

## What a layout looks like

```json
{
  "format": "py2tosc.layout",
  "schema": 1,
  "lexml": "6",
  "root": {
    "type": "GROUP",
    "id": "8043bc39-62c1-4d6e-9174-3b181505525c",
    "properties": {
      "frame": ["r", [0.0, 0.0, 100.0, 240.0]],
      "name": ["s", "mixer"],
      "visible": ["b", true]
    },
    "values": [
      {"key": "touch"}
    ],
    "children": [
      {
        "type": "FADER",
        "id": "a5a8f581-7a32-43a9-b67d-75467efda2c1",
        "properties": {
          "color": ["c", [0.25, 0.25, 0.25, 1.0]],
          "frame": ["r", [20.0, 20.0, 60.0, 200.0]],
          "gridSteps": ["i", 13],
          "name": ["s", "ch1"]
        },
        "values": [
          {"key": "x", "default": 0.0},
          {"key": "touch"}
        ],
        "messages": [
          {
            "kind": "osc",
            "path": [
              {"value": "/mixer/"},
              {"type": "PROPERTY", "value": "name"}
            ]
          }
        ]
      }
    ]
  }
}
```

Properties are trimmed here for length; a real fader carries twenty-three of them.

## The envelope

| Key | |
|-----|--|
| `format` | Always `py2tosc.layout`. Identifies the file as this and not some other JSON. |
| `schema` | The envelope version, currently `1`. A reader refuses a file that declares a higher one rather than guessing at it. |
| `lexml` | The format version written into the `.tosc`. TouchOSC 1.5 uses `"6"`; older releases wrote `"3"`. A string, as it is in the XML. |
| `root` | The one node every other node lives inside, always a `GROUP`. |

`format` and `schema` are optional on the way in, so a file written by hand or by another tool is readable without ceremony. A `format` that says something else is refused rather than assumed.

## A node

| Key | |
|-----|--|
| `type` | The control type: `GROUP`, `FADER`, `BUTTON` and the ten others. Required. |
| `id` | The node's unique id. Generated if absent, which is fine for a layout being written from scratch and not for one being edited -- see below. |
| `properties` | Every property, keyed by the camelCase key the file stores it under. |
| `values` | The control's live state. Omitted when there is none. |
| `messages` | The OSC, MIDI, local and gamepad bindings. Omitted when there are none. |
| `children` | Nested controls. Omitted when there are none. |
| `includes` | `true` on a node that carries the format's empty `<includes/>` element. Written where the file had one and left out everywhere else. |

Nothing is filled in from the control's type. A node with no `properties` decodes to a control with none, exactly as reading the XML does, so a layout says what it means rather than what it inherits.

**Ids matter more than they look.** A local binding addresses its destination by node id, so an id that changes silently repoints a binding. Editing an existing layout means keeping the ids that came with it. Writing a fresh one means leaving them out and letting py2tosc mint them.

## Properties

A property is a `[type, value]` pair, where the type is the one-letter tag the format itself uses:

| Tag | | Written as |
|-----|--|------------|
| `s` | string | `["s", "ch1"]` |
| `b` | boolean | `["b", true]` |
| `i` | integer | `["i", 13]` |
| `f` | float | `["f", 0.5]` |
| `r` | frame | `["r", [20.0, 20.0, 60.0, 200.0]]`, as `x, y, w, h` |
| `c` | colour | `["c", [0.25, 0.25, 0.25, 1.0]]`, as `r, g, b, a` from 0 to 1 |

The tag is carried rather than worked out from the value, and that is the decision the whole format rests on. Four numbers are a frame or a colour and only the tag says which; `gridX` is an element count on a `GRID` and a switch on an `XY`; a custom property has no table to consult at all. A format that left the tags out would quietly rewrite the ones it guessed wrong.

Keys are the file's own camelCase. A `snake_case` key is accepted on the way in and written back out as camelCase, the same translation `control.corner_radius` makes.

## Values

A control's live state, one entry per key it holds:

```json
"values": [
  {"key": "x", "default": 0.0},
  {"key": "touch"}
]
```

`key` is always written. `locked`, `locked_default_current`, `default` and `default_pull` appear only when they are not at their defaults, which is why the `touch` entry above is a single key.

This is the one place the JSON carries more than the XML. In the file every default is text, and the reader has to work out from the key whether `0` is a number and `false` is a boolean -- which is also why a label whose text is the word `true` needs a special case. Here the types are the JSON types.

## Bindings

Each binding says what kind it is and then only what was configured:

```json
"messages": [
  {"kind": "osc", "path": [{"value": "/mixer/"}, {"type": "PROPERTY", "value": "name"}]},
  {"kind": "midi", "message": {"data1": 7}, "values": [
    {"type": "CONSTANT"},
    {"type": "INDEX", "scale_min": 7, "scale_max": 8},
    {"type": "VALUE", "key": "x", "scale_max": 127.0}
  ]},
  {"kind": "local", "dst_type": "VALUE", "dst_var": "x", "dst_id": "e0537d9e-..."},
  {"kind": "gamepad", "type": "BUTTON_X"}
]
```

`kind` is one of `osc`, `midi`, `local` or `gamepad`. Everything else is the `snake_case` name of a field on the corresponding class -- [`OscMessage`][py2tosc.OscMessage], [`MidiMessage`][py2tosc.MidiMessage], [`LocalMessage`][py2tosc.LocalMessage], [`GamepadMessage`][py2tosc.GamepadMessage] -- and any field left out takes that class's default. The first binding above is a complete OSC message: enabled, sending and receiving on all ten connections, triggered by `x`, with the control's `x` value as its argument. All of that is default, so none of it is written.

The two conventions meeting inside one node is deliberate. Property keys are camelCase because they are the format's vocabulary; binding fields are `snake_case` because they are this library's, and nothing in the file is spelled that way.

## What survives, and what is not recorded

A layout written to JSON and read back produces the same `.tosc` bytes it started as. Everything the format holds is carried: all thirteen control types, custom properties, Lua scripts, every binding type, and the per-node `includes` element.

Three things are deliberately not recorded, because none of them can reach the file:

- **Property order.** The XML writer sorts properties by key, so the order in a file is not information.
- **Integer against float.** `15` and `15.0` are both written `15`.
- **Anything a default stands in for.** A binding field, a value field or an empty container that is absent is reconstructed from the class it belongs to, which is where the file's own defaults come from too.

One thing is recorded that JSON has no notation for. A non-finite number -- `o_custom.xml` in the test corpus holds ninety `inf` colour components, written by some TouchOSC build and carried faithfully ever since -- is written as an object:

```json
"color": ["c", [{"$float": "inf"}, 0.0, 0.0, 1.0]]
```

An object never appears where a number belongs otherwise, so the escape is unambiguous, and the output stays strictly valid JSON rather than emitting the `Infinity` that most parsers outside Python reject.

## When it will not read

A key nothing reads is refused rather than ignored:

```console
$ py2tosc show mixer.json
mixer.json: not a readable layout (root.children[1]: unknown key 'childs'; did you mean 'children'?)
```

This is the failure mode a format like this has to close. A `childs` that is quietly skipped drops an entire subtree, and the layout that comes back looks exactly like one that read correctly. If a key is genuinely new, that is what `schema` is for.

Every message names the node it gave up on, by the path from the root:

```text
root.children[0].properties.frame: a frame needs 4 values (x, y, w, h), got 2
root.messages[0].path[0]: unknown key 'values'; did you mean 'value'?
root.children[0]: id should be a string, found a number
```

A file that reads is not necessarily a layout that works, and the two checks are separate. The codec answers "can this be read", while [validation](validation.md) answers "will TouchOSC accept it" -- a binding pointing at a control that no longer exists, a pager with no pages, a name that an OSC address cannot carry:

```console
$ py2tosc validate mixer.json
mixer.json: clean
```

## Stability

The JSON encoding is covered by the same guarantee as the rest of the format work: a layout that round-trips today round-trips in every later release with the same `schema`. Anything that would break a file already written gets a new `schema` number, and files declaring an older one keep reading.
