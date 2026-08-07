"""Writing a layout back out as the Python that would build it.

The claim is a round trip through source: load a file, generate a script, run
the script, and get the same layout. It is checked against every file in the
corpus rather than a sample, because the interesting cases are the ones nobody
would think to write by hand.
"""

import collections
from dataclasses import fields, is_dataclass

import pytest

import py2tosc
from _corpus import CORPUS, DATA
from py2tosc.defaults import defaults_for


def rebuild(source: str) -> py2tosc.Document:
    """Run generated source and hand back what it built."""
    scope: dict = {}
    exec(compile(source, "<generated>", "exec"), scope)  # noqa: S102
    return scope["doc"]


def plain(value):
    """Enums and their string values are one thing as far as the format goes.

    A loaded message holds plain strings; a freshly built one holds enum
    members. Comparing them raw would report a difference the file cannot
    express.
    """
    if is_dataclass(value):
        return tuple((f.name, plain(getattr(value, f.name))) for f in fields(value))
    if isinstance(value, list):
        return tuple(plain(v) for v in value)
    if hasattr(value, "value") and not isinstance(value, (str, int, float, bool)):
        return str(value)
    return value


def differences(
    before: py2tosc.Document, after: py2tosc.Document
) -> collections.Counter:
    """Everything that changed, by kind, ignoring node ids."""
    found: collections.Counter = collections.Counter()
    ids_before = {c.id: n for n, c in enumerate(before.walk())}
    ids_after = {c.id: n for n, c in enumerate(after.walk())}

    originals, rebuilt = list(before.walk()), list(after.walk())
    if len(originals) != len(rebuilt):
        found["control count"] += 1
        return found

    for a, b in zip(originals, rebuilt):
        if a.control_type != b.control_type:
            found["type"] += 1
        for key in b.properties:
            if not a.has(key):
                found[
                    "default added" if key in defaults_for(a.control_type) else "extra"
                ] += 1
        for key in a.properties:
            if not b.has(key):
                found["lost"] += 1
            elif a.get(key) != b.get(key):
                found["changed"] += 1
        if [plain(v) for v in a.values] != [plain(v) for v in b.values]:
            found["values"] += 1
        if [type(m).__name__ for m in a.messages] != [
            type(m).__name__ for m in b.messages
        ]:
            found["messages"] += 1
            continue
        for m, n in zip(a.messages, b.messages):
            for field in fields(m):
                x, y = getattr(m, field.name), getattr(n, field.name)
                if field.name == "dst_id":
                    if ids_before.get(x, x) != ids_after.get(y, y):
                        found["wiring"] += 1
                elif plain(x) != plain(y):
                    found[f"message.{field.name}"] += 1
    return found


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_every_layout_round_trips_through_generated_source(path):
    """Load, generate, run, compare.

    `default added` is the one tolerated difference and it is named rather
    than ignored: `Control` applies its type's defaults before anything else,
    so a property the file omits comes back. Ten combinations across the
    corpus do this, all of them keys the format gained after the file was
    written.
    """
    original = py2tosc.load(path)
    found = differences(original, rebuild(py2tosc.to_python(original)))
    assert set(found) <= {"default added"}, dict(found)


def test_a_generated_script_names_its_controls():
    """Readable output is the point: variables come from the control's name."""
    source = py2tosc.to_python(py2tosc.load(DATA / "fader_with_label.tosc"))
    assert "fader1 = py2tosc.fader(" in source
    assert "label1 = py2tosc.label(" in source
    assert "group.add(fader1)" in source


def test_local_bindings_are_written_after_the_tree():
    """A binding names its destination, which may be built later."""
    source = py2tosc.to_python(py2tosc.load(DATA / "Numpad_basic.tosc"))
    _, _, after_imports = source.partition(")\n\n\n")
    body, _, wiring = after_imports.partition("# every binding")
    assert "LocalMessage" not in body, "a local binding was written before its target"
    assert ".id)" in wiring


def test_out_of_range_colours_survive():
    """A bare tuple would be read back as 0-255 and silently rescaled.

    `o_custom.tosc` holds colours above 1.0, which the library preserves
    rather than clamps, so the generated source has to preserve them too.
    """
    original = py2tosc.load(DATA / "o_custom.tosc")
    loud = next(c for c in original.walk() if c.color.r > 1)
    again = rebuild(py2tosc.to_python(original))
    assert (
        next(c for c in again.walk() if c.get("name") == loud.get("name")).color
        == loud.color
    )


def test_a_custom_property_keeps_its_exact_key():
    """`CustomProperty` does not survive snake_case and back, so it is `set`."""
    doc = py2tosc.Document(root=py2tosc.group(name="root"))
    doc.root.set("CustomProperty", "Craig")
    source = py2tosc.to_python(doc)
    assert ".set('CustomProperty', 'Craig')" in source
    assert rebuild(source).root.get("CustomProperty") == "Craig"


def test_a_control_can_be_generated_on_its_own():
    """Given a control rather than a document, the script ends with the control."""
    source = py2tosc.to_python(py2tosc.fader(name="solo"))
    assert "py2tosc.Document" not in source
    scope: dict = {}
    exec(compile(source, "<generated>", "exec"), scope)  # noqa: S102
    assert scope["doc"].control_type is py2tosc.ControlType.FADER


def test_generated_source_is_valid_python_for_every_layout():
    """Compiling is cheaper than running and catches a mangled literal."""
    for path in CORPUS:
        compile(py2tosc.to_python(py2tosc.load(path)), str(path), "exec")
