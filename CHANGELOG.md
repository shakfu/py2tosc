# Changelog

Notable changes to py2tosc. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [semantic versioning](https://semver.org/spec/v2.0.0.html) -- while the version is below 1.0, a minor bump may break the API.

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
