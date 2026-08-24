# Command line

Installing py2tosc puts a `py2tosc` command on your path. Everything it does is
file-shaped, and none of it needs a script written first.

```console
$ py2tosc --help
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | The command did what was asked. |
| `1` | The layout was read and `validate` found an error in it. |
| `2` | The command could not run: a command line that will not parse, or input that cannot be read. |

`1` and `2` are deliberately different. `1` is a result -- the file was read and
judged, and the judgement is that TouchOSC will reject it. `2` means no
judgement happened, because the path was wrong, the bytes were not a layout, or
the flags made no sense. One is a layout to fix and the other is a pipeline to
fix:

```bash
py2tosc validate layout.tosc
case $? in
  0) echo "clean" ;;
  1) echo "layout has errors" ;;
  *) echo "could not check it"; exit 1 ;;
esac
```

This is the same split `grep`, `diff` and `mypy` make, and the numbers are the
ones those tools use. A bad command line and an unreadable file share `2`
because no caller acts on the difference, and because argparse exits `2` for
the first of them whether or not we agree.

Only `validate` returns `1`; every other subcommand returns `0` or fails with
`2`. These codes are covered by the [stability policy](stability.md).

## show

What is in a layout: how many controls of each type, how many bindings, and the
tree.

```console
$ py2tosc show mixer.tosc
mixer.tosc  lexml 6
  3 controls: GROUP 1, FADER 1, LABEL 1
  2 messages: Midi 1, Osc 1

GROUP  (0, 0, 640, 860)  2 children
  FADER   'fader1'  (77, 60, 50, 200)
  LABEL   'label1'  (60, 275, 80, 25)
```

The tree stops at two levels by default. `--depth 0` prints all of it.

## validate

Reports what TouchOSC will reject or quietly ignore, and exits non-zero if any
of it is an error -- so it drops into a pre-commit hook or a build script
without further ceremony.

```console
$ py2tosc validate mixer.tosc
mixer.tosc: clean
```

Warnings alone do not fail. See [Validation](guide/validation.md) for what each
rule means.

## decompile

Writes the layout out as the Python that would build it, to stdout unless you
give it somewhere to go.

```console
$ py2tosc decompile mixer.tosc -o mixer.py
```

Useful when the layout exists and the script does not. See
[Generating Python](api/codegen.md).

## convert

Rewrites a layout in another format, chosen by the output's extension: `.tosc`
for the compressed file TouchOSC opens, `.xml` for the readable export the
editor also writes, `.json` for the [JSON encoding](guide/json.md).

```console
$ py2tosc convert mixer.tosc -o mixer.xml
$ py2tosc convert mixer.tosc -o mixer.json
$ py2tosc convert mixer.json -o mixer.tosc
```

The input is read the same way wherever it comes from, so every subcommand on
this page takes a `.json` layout where it takes a `.tosc`. The format is
decided by what the file holds rather than by its name, which includes telling
the two JSON dialects apart: a file whose envelope says `py2tosc.ui` is a
[layout description](guide/ui-json.md) and is built before it is read.

There is no `-o mixer.ui.json`, and there cannot be. A description says how the
space is divided; a layout that has been resolved has frames instead, and no
memory of the row that placed them.

## build

Generates a control surface from a list of parameters -- a fader each, paged,
bound to MIDI and OSC.

```console
$ py2tosc build parameters.json
54 parameters -> 5 pages, 169 controls -> build/parameters.tosc
```

The input is JSON, in either of two shapes. A list of names is the short form:

```json
["Threshold", "Ratio", "Attack"]
```

A list of objects is the long one, where only `name` is required:

```json
[
  {"name": "Threshold", "cc": 20, "channel": 1},
  {"name": "Ratio"}
]
```

Two things are worth knowing before pointing it at a file a plugin host wrote.

**An `index` is ignored.** Hosts export one next to each name, and it is not a
controller number -- a real export's indices run well past the 127 a CC allows.
Controller numbers come from the parameter's position unless an entry says `cc`.

**Names are made safe.** They are meant for people, so they contain spaces and
repeat, and an OSC address can carry neither. Each control's name is slugged and
numbered if it collides, while the original text stays on the caption.

| Option | |
|--------|--|
| `-o`, `--output` | Where to write it. Defaults to `build/<parameters>.tosc`. |
| `--prefix` | The OSC namespace, which may be more than one segment deep. Defaults to the parameter file's name. |
| `--columns`, `--rows` | The shape of each page, and so how many pages there are. |
| `--size` | The design canvas, as `WIDTHxHEIGHT`. Defaults to `568x320`. |
| `--midi-only`, `--osc-only` | Leave out the other binding. |

### Choosing a size

TouchOSC scales a layout to whatever screen opens it, so the canvas is a
coordinate space and an aspect ratio rather than a pixel count. It still
matters, because font sizes and margins are absolute within it, and because
the aspect ratio is what decides whether the layout has letterboxing on the
device you actually use.

The general-purpose control surfaces TouchOSC ships are all phone-sized:
`simple_mk2`, `mix_2_mk2` and `logictouch` at 320x480, `beatmachine_mk2` at
480x320, `automat5_mk2` at 568x320. The default follows the landscape ones,
because a parameter surface is faders side by side. Match the device instead
when you know it:

```console
$ py2tosc build params.json --size 320x480 --columns 2 --rows 4   # a phone
$ py2tosc build params.json --size 1024x768                       # a tablet
```

Caption text is sized from the box it lands in rather than fixed, at the ratio
the corpus uses, so changing the canvas or the page density does not leave the
text behind.

If the pages come out too dense, prefer `--columns` and `--rows` over a bigger
canvas: `beatmachine_mk2` fits 231 controls on 480x320 by paging, and no
official example exceeds 1024x768.

[Layout sizes](guide/sizes.md) has every size in the corpus and what each suits.

The same thing from Python is [`py2tosc.surface`](api/surface.md), which is
what this subcommand calls.
