# Changelog

Notable changes to py2tosc. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [semantic versioning](https://semver.org/spec/v2.0.0.html) -- while the version is below 1.0, a minor bump may break the API. What is covered once 1.0 lands, and what stays provisional after it, is set out in the [stability policy](https://shakfu.github.io/py2tosc/stability/).

## [Unreleased]

## [0.3.3]

### Added

- An exception hierarchy. `Py2toscError` is the base for everything the package raises on its own behalf, and `ValidationError` now inherits from it. Errors caused by passing a bad argument stay on the builtins: a `ValueError` for an unparseable colour already says what it means, and wrapping it would tell the caller nothing.

- `FormatError`, raised when input cannot be read as a layout. Reading could fail in three unrelated ways -- the bytes are not XML, a `.tosc` stream will not decompress, or the XML parses but is not a `lexml` root holding one node -- and each reached the caller as a different type from a different module: `ParseError`, `zlib.error` and `ValueError`. None was a py2tosc type, so no single `except` could say "that file is not a layout", and the robustness tests had to assert `pytest.raises(Exception)` to cover it. They now name the type.

  `FormatError` also inherits `ValueError`, which is what `load` and `loads` have documented themselves as raising since they were written. Both docstrings were wrong: neither `ParseError` nor `zlib.error` is a `ValueError`, so the promise was not kept. Narrowing to a subclass makes the older contract true rather than breaking it, so code that catches `ValueError` is unaffected.

### Changed

- **Breaking, for scripts reading exit codes.** A CLI failure to read the input exits `2` rather than `1`. `1` now means one thing only: the layout was read and `validate` found an error in it. Before this, `py2tosc validate layout.tosc` exited `1` whether the layout was invalid or the path was simply wrong, so a CI step could not tell a layout it should fix from a pipeline it should fix -- the first is a result, the second is the check never having run.

  A bad command line already exited `2`, chosen by argparse, and unreadable input now joins it. They share a number because no caller acts on the difference, and because this is where comparable tools put them: `grep`, `diff` and `mypy` all reserve `1` for "what you asked about is bad" and `2` for "I could not look". An exit code nobody expects is worth no more than no exit code at all.

  A script that only tests for zero is unaffected. One that treats any non-zero as failure is unaffected. One that tests `== 1` to mean "something went wrong" now needs `!= 0`.

  The codes are named in `py2tosc.cli` as `OK`, `INVALID` and `CANNOT_RUN`, and are covered by the stability policy.

### Fixed

- `py2tosc.surface` is now bound by `import py2tosc`. The API reference documents `py2tosc.surface.read` and `py2tosc.cli` describes it as "the same thing from Python", but the package imported only `layout` and `ui` as attributes, so a reader following either page got an `AttributeError`. Nothing in the suite caught it because every caller in the repository reaches it as `from py2tosc import surface`, which has always worked.

- `py2tosc.properties` is exported for the same reason. `to_camel` and `to_snake` are documented, and converting between the file's camelCase property names and Python's snake_case is part of using custom properties, so the module they live in is public whether or not it was declared.

- `Message`, `ALL_CONNECTIONS` and `ALL_GAMEPADS` were exported but appeared nowhere in the API reference. `Message` is the union a caller annotates against, which made its absence the most consequential of the three.

  `tests/test_api.py` now holds the checks that keep these from recurring: everything in `__all__` is documented, everything documented is reachable by attribute access from a bare `import py2tosc`, a submodule named in the reference is exported, and the reference never points at a private module. The second of those is the test the `surface` defect would have failed; the third is what found `properties`.

## [0.3.2]

### Added

- A `controls` demo, building one of every control type on a single sheet, captioned and each addressed by name. It exists to be opened: py2tosc can prove a layout is structurally valid and byte-exact on a round trip, and neither says whether a `RADIAL` came out round. Every construction defect this project has found was valid, round-tripped exactly, and visibly wrong the moment TouchOSC drew it. Confirmed working there.

  It also closes the gap that motivated it -- `BOX`, `ENCODER`, `RADAR`, `RADIAL`, `RADIO` and `TEXT` were read and round-tripped but built by nothing, so nothing exercised the path their defects live on.

- `validate` warns when a control carries a custom property named after one of its own values. `label.text = "hi"` writes a property called `text`, but what a label says is its `text` **value**, so the property is stored, ignored, and drawn as nothing. Nothing else can catch this: inventing a property is exactly what the format lets a script do, which makes a typo indistinguishable from a feature -- except when the name collides with a value the control already has, which is never deliberate. No control in the corpus has one. The `controls` demo walked into it and every caption on the sheet was blank.

### Fixed

- Four wrong control defaults, all of the kind that only matters when you create a control rather than read one. A `RADIAL`, `ENCODER` and `RADAR` are drawn round and default to `shape` 2, where they were built square: all 171 in the corpus are 2, while every rectangular type is 1. A `BOX`, `LABEL`, `TEXT` or `GROUP` defaults to `interactive` off, unanimously across 5134 editor-written instances -- one left interactive swallows the press meant for whatever sits beneath it, which is the defect that made the `simple_mk2` readouts eat their own faders' touches. A `RADIO` defaults to `orientation` 1, since a radio runs horizontally or vertically and no instance in the corpus is 0. And `gridSteps` is per type rather than shared: the editor creates a `FADER` with 13 and a `RADIAL` or `ENCODER` with 20, where one default said 10 for all three.

  These change what a freshly built control looks like, so a script that relied on a `LABEL` being interactive, or on a `RADIAL` being square, will need to say so. Loading and saving is untouched -- a control read from a file keeps what the file said -- and every corpus layout still round-trips byte for byte.

  Found by constructing one of each of the six types nothing in the library had ever authored and diffing them against the editor's own. The corpus frequencies alone would not have settled it, since they cannot tell a wrong default from a popular style; `controls.tosc` did -- one of every control type, made in the editor and left unstyled -- and it is now the reference the defaults are tested against. On that evidence `outline`, `background` and `cornerRadius` were left alone, despite disagreeing with the defaults across most of the corpus: that file has them at the default, so the disagreement is taste.

## [0.3.1]

### Added

- A `py2tosc` command. Everything the library does is file-shaped, and none of it needed a script written first -- least of all `to_python`, where you had to write a script to get a script. Five subcommands: `show` summarises a layout and draws its tree, `validate` reports what TouchOSC will reject and exits non-zero if any of it is an error, `decompile` writes the layout out as Python, `convert` rewrites it as `.tosc` or `.xml`, and `build` generates a control surface from a list of parameters.

- `py2tosc.surface`, which builds a paged surface from a parameter list. The `control_surface` demo did this already, but a demo is not shipped in the wheel and so could not back a subcommand. The demo is now a caller, so the two cannot drift.

  Its input is a public contract rather than whatever happened to be in the test data: a list of names, or a list of objects where only `name` is required and `cc` and `channel` are optional. A host's `index` is ignored on purpose -- it identifies the parameter to the host and is not a controller number, and a real export's run well past the 127 a CC allows -- so controller numbers come from position unless an entry says otherwise. Names are slugged and numbered, since they contain spaces and repeat and an OSC address can carry neither. `--midi-only` and `--osc-only` leave out the other binding.

  The design canvas is `--size WIDTHxHEIGHT`, and `surface.build` takes a `frame`. TouchOSC scales a layout to whatever screen opens it, so the canvas is an aspect ratio and a coordinate space rather than a pixel count -- but font sizes and margins are absolute within it, so it is not free either.

- A guide to choosing a layout size, `docs/guide/sizes.md`, together with reference pages for the command line and `py2tosc.surface`, and a section in the README.

  The size guide is a reading of the twenty layouts in `tests/examples/`, which all ship with TouchOSC under Help > Examples and are therefore the best available evidence about what the format's designers consider normal. Three findings: size follows purpose rather than device, and the examples group by what they are for; nothing official exceeds 1024x768; and the five general-purpose control surfaces are the smallest of the lot and every one of them pages, `beatmachine_mk2` fitting 231 controls onto 480x320. The last is a tendency rather than a rule -- `hexkeys` puts 240 controls on 740x345 unpaged, because a keyboard has to be seen at once.

### Changed

- `surface` now defaults to a 568x320 canvas, matching `automat5_mk2`, rather than the 1024x768 it started with. That number was a guess, and nothing official is laid out on it except a 767-control DAW controller.

- Caption text is sized from the box it lands in, at 0.55 of its height, rather than fixed at 14pt. Across the 2867 labels in the corpus, text sits at a median 0.54 of the height of the box holding it, and 0.52 across the official examples alone; a fixed size only suits one canvas, and on 1024x768 that 14pt sat at 0.28, half what the surrounding label wanted. The error grew with the canvas, so the fixed text and the oversized default were the same mistake seen twice.

- `tests/examples/` now holds only what TouchOSC ships. The two hand-drawn `GRID` references moved to `tests/data/`, alongside the hand-drawn `PAGER` one that was already there.

### Fixed

- Saving a layout the combinators described but nobody resolved wrote every control at the origin, silently. It was structurally valid, round-tripped byte-exactly, and was visibly wrong only once TouchOSC drew it -- and `save(validate=True)` did not stop it, because the unresolved-layout rule is a warning and saving only refuses on errors.

  `save` now places whatever is still unplaced. It will not re-run a layout that was already resolved, so a frame placed by hand inside one survives; an explicit `resolve` still re-runs everything, which is how a tree is laid out again after its root frame changes. Loading a file and saving it back is unaffected -- a loaded control carries no layout -- and that is asserted over every `.tosc` in the corpus rather than argued.

  `dumps` still serializes exactly what is in the tree, on purpose: it is what you read a layout with while debugging one, and an unplaced layout is the state you need to see.

  The unresolved-layout warning stays, and now says what it means. It is not a report about the file, since saving places the layout anyway -- it is a report about the tree in hand, where an unset frame reads back as `(0, 0, 0, 0)` rather than raising, so anything consulting frames before saving is reading coordinates that mean nothing yet.

- `build` and `show` reported different control counts for the same layout, off by one: `find_all` returns descendants while `walk` includes the root. `show` was right.

## [0.3.0]

### Added

- `validate` warns when a local binding writes a value or property the destination does not have -- a `LABEL` told to move its `x`, or a property that was renamed out from under the binding. The message is delivered and then discarded, so the layout loads, round-trips and validates as well formed while the control never moves. All 358 resolvable local bindings in the corpus address something real, so the rule fires on nothing the editor wrote. A blank `dst_var` is left alone, like a blank `dst_id`.

- `to_python`, which writes a layout back out as the Python that would build it. Load a `.tosc` and read it as source, which is what you want when the layout already exists and the script does not. Every one of the 43 files in the corpus round-trips through its own generated script.

  The output is flat -- a variable per control, then the tree, then the bindings -- rather than one nested expression: nesting reads better for five controls and is unusable at a hundred and forty, and a local binding has to be able to name the control it addresses. One difference is documented and asserted rather than hidden: a property the file omits but the control's type defaults will be present in the rebuild, which accounts for ten combinations across the corpus, all keys the format gained after those files were written.

- `validate` warns when a `GRID` holds a different number of controls than its `grid_x` and `grid_y` claim. TouchOSC has no empty grid -- creating one populates it -- and all 37 grids in the corpus hold exactly `grid_x * grid_y` children. A bare `py2tosc.grid()` says 2x2 of faders in its defaults and creates none, which now gets reported rather than passing as clean.

- A `simple_mk2.py` demo, rebuilding one of the layouts TouchOSC ships -- four pages, 140 controls, every binding type the format has -- from nothing. It is the widest thing here that the library authors rather than edits, and the first end-to-end evidence that it can. Same control types, names and tab labels as the original, the same bindings to the message, and of the 134 controls comparable by position, 77 land on exactly the original coordinates and 111 within a point.

- `ui.grid`, which builds a `GRID` control with the cells it must hold. TouchOSC has no empty grid, so this is the complete way to make one: it fills itself with `columns * rows` controls of a single type, which is what a multitoggle or a bank of faders is. Every grid in the corpus holds one type, so the type is what it takes.

  A `GRID` tiles its cells rather than dividing its frame: every cell is the same size, with a three-point margin around and between, and whatever will not divide evenly is left at the far edge. That is reproduced for 36 of the 37 grids in the corpus, and for both hand-made reference grids; the one exception is recorded in the tests. `grid_type` is set from the control type -- the corpus numbers it by the type's position in the format's own order, so a grid of buttons left at the default would have announced itself as a grid of faders.

### Changed

- Every demo takes its arguments through `argparse`, so a missing path is a usage message rather than a `TypeError` traceback, and each answers `--help`. The output is now `-o/--output` and defaults to `build/<demo>.tosc`, named after the script, so a demo can be run with only the inputs it actually needs -- `python tests/demos/numpad.py` with nothing at all. The directory is created if it is missing. Inputs stay positional and in the same order.

- **`grid` now names the `GRID` control everywhere and nothing else.** It previously meant three different things across three modules, which is why it took a round of questions to establish how to build one. Two renames follow:

  - `ui.grid` -- the arrangement that tiles controls you already have into a `GROUP` -- is now `ui.tiles`. It sits alongside `row`, `column` and `stack`, and is the only one of them that took the format's name for a control it does not build.
  - `layout.grid` is now `layout.matrix`. It creates one control type across M by N cells inside a parent, which `matrix` describes and `grid` did not; the eager family now reads `row`, `column`, `matrix`. Behaviour is unchanged.

  So `py2tosc.grid` and `ui.grid` both give a `GRID`, the first bare and the second with its cells, while `ui.tiles` and `layout.matrix` arrange controls in a `GROUP`. `layout.matrix` is the first break in `layout` since 0.1.0; no demo used it, and it is a rename with no behavioural change.

## [0.2.1]

### Fixed

- `ui.pager` reserved the tab bar from the top edge whatever the pager's `orientation`, so a bar mounted on the bottom or the left left its pages both the wrong size and in the wrong place. It was right for 999 of the 1005 pager pages in the corpus and wrong for the other six. All 1005 are now reproduced exactly, which covers the bar being switched off as well -- the common case, where a page fills its pager.

## [0.2.0]

Adds `py2tosc.ui`, a layer of combinators for building messages and layouts, and
fixes a defect that made `Control.copy` silently misdirect a duplicated
subtree's wiring. `py2tosc.layout` and everything else in the core namespace are
unchanged, so existing scripts keep working.

### Added

- `py2tosc.ui`, message combinators that build the existing dataclasses from a shorter description. `osc("/synth/{parent.name}/{name}")` expands an f-string-like address into partials, `midi_cc` and `midi_note` cover the two common MIDI bindings, and `connect` replaces the seven keyword arguments a `LocalMessage` needs with a source and a target described by the same `value`, `const`, `prop` and `index` constructors used for OSC arguments. Nothing it builds can reach a file that a hand-written message could not. The module is unstable while the version is below 1.0; see the [API reference](https://shakfu.github.io/py2tosc/api/ui/).

- `midi_cc` and `midi_note` take a partial as well as a number for the note, the controller and the channel, so `midi_note(prop("name"))` gives a keyboard whose buttons name their own notes instead of being numbered one at a time. `const` and `prop` gained a `scale` to match, since a MIDI slot draws its fixed byte from the range rather than from the key.

- `ALL_CONNECTIONS` and `ALL_GAMEPADS` are exported, having previously been reachable only by importing `py2tosc.messages` directly.

- Layout combinators in `py2tosc.ui`: `row`, `column`, `grid` and `stack` describe an arrangement without sizing anything, and `resolve` assigns frames once the frame at the top is known. Each returns the group it built rather than the children, so layouts nest by ordinary composition -- `row(column(a, b), c)` -- a row can hold a fader and a label rather than one control type, and `stack` expresses the button-with-a-label idiom the eager functions cannot. `gap` and `pad` are supported throughout, with exact arithmetic: each slot ends exactly `gap` before the next begins and the last reaches the content edge. `Document.resolve()` runs the pass against the root. `py2tosc.layout` is unchanged.

- `ui.pager`, which stacks groups as the pages of a `PAGER`. The other combinators all build a `GROUP`, and a `PAGER` carries no layout of its own, so before this a page kept whatever frame it was built with -- a 100x100 default inside an 800x600 pager, which `validate` reported as clean. Pages are placed below the tab bar rather than under it, reading the pager's own `tabbar` and `tabbar_size`. A page is also given the properties that make its tab legible: `tab_label`, which is a separate property from `name`, and the four tab and text colours. None of those belong to a control type's defaults, since a group is only a page when a pager holds it, and a page without them draws its label in no colour at all -- a tab bar with nothing written on it.

- `ui.labelled` and `ui.inset`. `labelled` lays a non-interactive caption over a control, which is the commonest idiom in TouchOSC and the one the eager layout functions cannot express at all. `inset` shrinks a single control within the frame its layout gives it, as a fraction rather than a pixel count, since a deferred layout has no pixels until the frame arrives from above. It is what a group's `pad` cannot say: `pad` insets every child alike, and a key wants its caption padded but not the button beneath. The inset rides on the control rather than on a wrapper group, so it costs no extra node.

- `validate` warns when a control carries a layout that was never resolved. An unset frame reads back as `(0, 0, 0, 0)` rather than raising, so the mistake would otherwise reach the file as a group of zero-sized controls. Saving deliberately does not resolve on its own: writing a file must not change the tree.

- `validate` warns when the root node is not a `GROUP`. TouchOSC treats the root as the canvas and gives it none of the behaviour its type would otherwise have, so a `PAGER` there draws its tab bar and then stacks every page instead of paging between them -- a layout that loads, validates and round-trips while being visibly broken. All 35 layouts in the corpus root at a `GROUP`.

- `validate` warns when a `LocalMessage` is addressed to a node id no control in the layout has. A stale destination is otherwise invisible: nothing about the message is malformed, so the binding simply never fires. A destination that is still blank is left alone, since the editor writes those while a binding is part way through being set up.

- A `control_surface.py` demo, generating a paged MIDI and OSC surface from a plugin's parameter list. It is the second thing built on `py2tosc.ui`, and the one that found the pager gap.

### Changed

- The plugin parameter list in `tests/data/` is now `pro_c_2_fabfilter.json`, pretty-printed. Only the demos and their documented commands refer to it; nothing in the package does.

### Fixed

- `Control.copy(new_ids=True)` left local messages pointing at the originals. Duplicating a wired subtree -- the obvious use of `copy`, and how a second numpad gets built -- produced a clone whose controls drove the subtree it was copied from, silently, because the id it held still resolved. Destinations inside the copied subtree now follow the copy; destinations outside it are left alone, since those are deliberate references to controls the copy does not own.

- Pressing the same numpad key twice in a row did nothing the second time. A key writes its caption into the very value the readout displays, and TouchOSC reports a value only when it changes -- so sending `7` while the readout already showed `7` was not a change, and the script never ran. Keys now send their caption behind a `#`, which a total can never start with, keeping the two disjoint whatever is on screen. `SEND` had the same defect for its own reason, writing `1` to the readout's touch on press and never releasing it; it now mirrors the button so the pulse falls back.

- The numpad demo's `SEND` key, which previously carried no binding at all and did nothing. It now pushes the total to `/numpad/value` over OSC. The binding lives on the readout rather than on `SEND`, because an OSC argument reads the control it sits on and only the readout holds the total; `SEND` touches the readout, and the readout sends on touch.

- The numpad demo's readout script. Every entry carried a leading zero, because the running total started at `"0"` and each keypress was concatenated onto it, so pressing 7 displayed `07`. `DEL` did nothing at all: it blanked the readout's text, which appended an empty string and then redrew the unchanged total. A branch meant to show `0` for an empty total was dead, overwritten by the line after it. The script now tracks the total separately from the display, ignores a leading zero, and gives `DEL` and `CLR` their meaning by name -- so every key sends its own name and is wired identically, rather than `CLR` and `DEL` carrying bespoke messages.

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

[0.3.1]: https://github.com/shakfu/py2tosc/releases/tag/v0.3.1
[0.3.0]: https://github.com/shakfu/py2tosc/releases/tag/v0.3.0
[0.2.1]: https://github.com/shakfu/py2tosc/releases/tag/v0.2.1
[0.2.0]: https://github.com/shakfu/py2tosc/releases/tag/v0.2.0
[0.1.0]: https://github.com/shakfu/py2tosc/releases/tag/v0.1.0
