# py2tosc

Generate and edit TouchOSC layouts from Python.

![Tests](https://github.com/shakfu/py2tosc/actions/workflows/tests.yaml/badge.svg) ![PyPI](https://img.shields.io/pypi/v/py2tosc) ![License](https://img.shields.io/github/license/shakfu/py2tosc)

py2tosc is a rewrite of [tosclib](https://github.com/AlbertoV5/tosclib) by [Alberto Valdez](https://github.com/AlbertoV5), whose work established the original mapping between the `.tosc` format and Python that this library is built on. The API is new and incompatible, but the knowledge of the format -- the control types, the property tables, the message layouts, and some of the tests and examples -- came from there, and is carried over with thanks. Original copyright is retained in [LICENSE](LICENSE).


**Disclaimer**: This project has no relation to Hexler, the developer of TouchOSC. Back up your layouts before editing them with third party tools.

## [Documentation](https://shakfu.github.io/py2tosc)

```console
$ pip install py2tosc
```

No dependencies. Python 3.10 or newer.

## What it does

A `.tosc` file is a zlib-compressed XML tree. py2tosc reads that tree into plain Python objects, lets you edit them, and writes it back out -- accurately enough that loading a layout and saving it again reproduces the editor's own bytes exactly, in both the compressed and exported forms.

```python
import py2tosc

doc = py2tosc.load("mixer.tosc")

for fader in doc.find_all(type="FADER"):
    fader.color = "#e76f51"
    fader.corner_radius = 2.0

doc.save("mixer-restyled.tosc")
```

Building one from scratch:

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

## Design

| Module | Holds |
|--------|-------|
| `enums` | TouchOSC's own vocabulary: control types, property types, conversions |
| `properties` | `Property`, `Frame`, `Color`, and the `snake_case` to camelCase mapping |
| `messages` | `Value`, `OscMessage`, `MidiMessage`, `LocalMessage`, `GamepadMessage` and their parts |
| `defaults` | The default property set for each control type |
| `control` | `Control`, the node model, plus a factory per control type |
| `codec` | Reading and writing the `.tosc` XML dialect, CDATA included |
| `document` | `Document`, `load`, `save`, `dumps` |
| `layout` | Row, column and grid arrangement, in plain arithmetic |

Property keys are camelCase in the file because that is what TouchOSC stores. The Python API is `snake_case` and translates at the boundary, so `control.corner_radius` addresses the `cornerRadius` key.

## Contributing

```console
$ make install     # install the package and dev dependencies
$ make test        # run the test suite
$ make docs-serve  # serve the documentation with live reload
```

`make help` lists the rest. The project uses [uv](https://docs.astral.sh/uv/) for environments, building and publishing.

### Releasing

1. Bump `version` in `pyproject.toml` and `__version__` in `src/py2tosc/__init__.py` -- a test fails if they disagree.

2. Date the release's section in `CHANGELOG.md`.

3. `make release-check`, then `make tag` and `git push origin vX.Y.Z`.

4. `make publish-test` to rehearse against TestPyPI, then `make publish CONFIRM=1`.

Publishing is manual and irreversible: a filename PyPI has accepted cannot be reused even after a delete, and no workflow re-checks the tag or the tree first. That makes `make release-check` in step 3 the only gate, so run it on a clean checkout. Both publish targets rebuild `dist/` from scratch and validate it with `twine check --strict` before uploading, and both need credentials in `~/.pypirc` or `TWINE_USERNAME`/`TWINE_PASSWORD`.

Documentation is published the same way, with `make docs-deploy`. Nothing deploys it automatically.

Bug reports and pull requests are welcome, including for the documentation.
