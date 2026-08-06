# Changelog

Notable changes to py2tosc. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [semantic versioning](https://semver.org/spec/v2.0.0.html) -- while the version is below 1.0, a minor bump may break the API.

## [Unreleased]

### Added

- `py2tosc.ui`, message combinators that build the existing dataclasses from a shorter description. `osc("/synth/{parent.name}/{name}")` expands an f-string-like address into partials, `midi_cc` and `midi_note` cover the two common MIDI bindings, and `connect` replaces the seven keyword arguments a `LocalMessage` needs with a source and a target described by the same `value`, `const`, `prop` and `index` constructors used for OSC arguments. Nothing it builds can reach a file that a hand-written message could not. The module is unstable while the version is below 1.0; see the [API reference](https://shakfu.github.io/py2tosc/api/ui/).

- `midi_cc` and `midi_note` take a partial as well as a number for the note, the controller and the channel, so `midi_note(prop("name"))` gives a keyboard whose buttons name their own notes instead of being numbered one at a time. `const` and `prop` gained a `scale` to match, since a MIDI slot draws its fixed byte from the range rather than from the key.

- `ALL_CONNECTIONS` and `ALL_GAMEPADS` are exported, having previously been reachable only by importing `py2tosc.messages` directly.

- Layout combinators in `py2tosc.ui`: `row`, `column`, `grid` and `stack` describe an arrangement without sizing anything, and `resolve` assigns frames once the frame at the top is known. Each returns the group it built rather than the children, so layouts nest by ordinary composition -- `row(column(a, b), c)` -- a row can hold a fader and a label rather than one control type, and `stack` expresses the button-with-a-label idiom the eager functions cannot. `gap` and `pad` are supported throughout, with exact arithmetic: each slot ends exactly `gap` before the next begins and the last reaches the content edge. `Document.resolve()` runs the pass against the root. `py2tosc.layout` is unchanged.

- `validate` warns when a control carries a layout that was never resolved. An unset frame reads back as `(0, 0, 0, 0)` rather than raising, so the mistake would otherwise reach the file as a group of zero-sized controls. Saving deliberately does not resolve on its own: writing a file must not change the tree.

- `validate` warns when a `LocalMessage` is addressed to a node id no control in the layout has. A stale destination is otherwise invisible: nothing about the message is malformed, so the binding simply never fires. A destination that is still blank is left alone, since the editor writes those while a binding is part way through being set up.

### Fixed

- `Control.copy(new_ids=True)` left local messages pointing at the originals. Duplicating a wired subtree -- the obvious use of `copy`, and how a second numpad gets built -- produced a clone whose controls drove the subtree it was copied from, silently, because the id it held still resolved. Destinations inside the copied subtree now follow the copy; destinations outside it are left alone, since those are deliberate references to controls the copy does not own.

- The messages guide taught `dst_type="FLOAT"` on a `LocalMessage`, which is a `Conversion` value in a field that takes a `PartialType`. `dst_type` says what kind of thing is written on the destination, so it takes `VALUE` or `PROPERTY`; nothing catches the mistake, since the field is annotated as a bare `str` and `validate` has no rule for it.

## [0.1.0]

First release: py2tosc is a rewrite of [tosclib](https://github.com/AlbertoV5/tosclib) 0.3.5 by Alberto Valdez; the entries below describe what changed relative to it. Scripts written against tosclib will not run against py2tosc, and there are no compatibility shims. See [Coming from tosclib](https://shakfu.github.io/py2tosc/migrating/) for a name by name mapping.

### Addeds

- `Document`, with `load`, `loads`, `save` and `dumps` named after the `json` module's. `load` accepts a `.tosc` or an `.xml` without being told which, and `save` picks the format from the file extension.

- `Control` as the node model. Traversal returns controls, not `ET.Element`, so children no longer have to be re-wrapped by hand.

- `find`, `find_all` and `walk`, searching by name, by control type or both.

- `Control.copy`, duplicating a subtree with fresh node ids.

- `save(validate=True)` and `dumps(validate=True)`, which refuse to write a layout that has errors and raise `ValidationError` instead. Off by default.

- `validate`, an opt-in check for things TouchOSC rejects or ignores -- children on a control that cannot hold them, duplicate node ids, a property stored under the wrong type, or a format property on a control type that has no use for it. Advisory and never raises; custom properties are left alone. Every rule is corroborated against layouts the editor wrote.

- `GamepadMessage`. tosclib 0.3.x had a `ControlElements.GAMEPAD` enum member with no implementation behind it, so a layout containing a gamepad binding could not be read at all.

- `Frame` and `Color` named tuples. Colours accept normalised floats, 0-255 integers or hex strings.

- `__version__`, and an `__all__` that governs the public namespace.

- Support for reading and writing lexml version 6, the format TouchOSC 1.5 writes: the `<includes>` element and the `<noDuplicates>` message flag. Both are omitted from documents that declare an older version.

- Frames keep sub-pixel positions. TouchOSC stores frames like `x=417.439`, which earlier releases -- and the first draft of this one -- rounded to integers, moving the control.

- A test corpus of 42 layout files, including the twenty examples bundled with TouchOSC 1.5.2, spanning both format versions, and demo scripts that the test suite executes -- including a numpad built from nested layouts, a Lua script and LOCAL message wiring.

### Changed

- **The API is `snake_case`.** `setColor` is `control.color = ...`, `findChildByName` is `find`. Property keys stay camelCase in the file, because that is what the format stores; `control.corner_radius` addresses the `cornerRadius` key.

- **Property and value data are native Python types**, not strings. `Value.locked` is a `bool`; `Property("textSize", 14).value` is `14`.

- **Reading no longer mutates the tree.** tosclib inserted empty `<messages>` and `<children>` elements into any control it wrapped.

- **Missing properties raise `AttributeError`** rather than returning `None`. Use `control.get(key)` where absence is expected.

- **Layouts are functions, not decorators.** `layout.row`, `layout.column` and `layout.grid` take the parent as an argument and return the controls they made, so nesting is ordinary function composition.

- Serialization is written directly rather than through `ElementTree`, so CDATA sections, element order and the XML declaration are preserved. Loading a layout and saving it reproduces the TouchOSC editor's own bytes exactly, in both the compressed and exported forms.

- Documentation moved from Sphinx to MkDocs.

- Packaging moved to `pyproject.toml` with the `uv_build` backend; `setup.py`, `tox.ini` and the three `requirements*.txt` files are gone.

- Releasing and publishing the documentation are driven from the Makefile rather than from CI. `make release-check` gates the declared version, the changelog entry and the state of the working tree; `make dist-check` rebuilds `dist/` from empty and validates it with `twine check --strict`; `make publish` uploads, behind a `CONFIRM=1` guard because a filename PyPI has accepted can never be reused. `make docs-deploy` pushes the documentation to `gh-pages`. Nothing is published automatically.

- CI runs the suite on Ubuntu against Python 3.10 through 3.14, and checks types, lint, a strict documentation build, and the built wheel, on every push and pull request.

### Removed

- **numpy is no longer a dependency.** py2tosc has no runtime dependencies at all. The layout arithmetic is plain Python.

- `ElementTOSC` and the `elements`, `controls` and `tosc` modules.

- `asCtrl`, which was declared, exported, and had `pass` for a body.

### Fixed

- `import tosclib` failed without `pyparsing`, an undeclared dependency reached by a stray `from pyparsing import Optional` that was never used. In a clean environment, `pip install tosclib` produced an unimportable package.

- Building a control with more than one message nested the second message inside the first, because the XML builder rebound its parent element inside a nested loop. An OSC and a MIDI binding on the same control produced a file TouchOSC could not load.

- MIDI bindings were written with a trigger's fields in place of the status bytes, from a leaked loop variable, and their values used a `<midivalue>` tag the format does not define. No MIDI binding tosclib produced was valid.

- `<dstID>` was written without its CDATA wrapper, unlike every other string in the format.

- Generated layouts declared `lexml version=3` and omitted `<includes>`.

- Default `connections` was five slots wide; TouchOSC 1.5 uses ten.

- Element truth-value testing, deprecated since Python 3.12.

- The test suite only passed when run from the repository root.

- CI declared its matrix key as `python-versions` but read `matrix.python-version`, so every leg silently tested the same interpreter, and the matrix targeted Python versions the package rejected.

- `numpy>=2` broke every layout: numpy 2 changed scalar `repr`, and the frames were stringified through it.

- `gridColor` was missing from XY and RADAR defaults, `textClip` and `textWrap` from TEXT, and `lines`/`linesDisplay` from XY.

- `GamepadMessage.connections` defaulted to ten characters. The gamepad field counts controllers, not network connections, and is four wide.

- `MidiType.NOTE_ON` was spelled `NOTEON`; the format uses `NOTE_ON`.

- `PAGER` carried an `x` value instead of `page`, and `ENCODER` was missing its `y`.

## Prior history

py2tosc began as a fork of [tosclib](https://github.com/AlbertoV5/tosclib), which had twelve releases between 2022-05-20 and 2022-06-09, ending at 0.3.5. That history belongs to a different distribution and is not restated here; see [the tosclib releases](https://pypi.org/project/tosclib/#history).

[0.1.0]: https://github.com/shakfu/py2tosc/releases/tag/v0.1.0
