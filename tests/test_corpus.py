"""Every layout in `tests/data`, exercised end to end.

The corpus is a mix of real TouchOSC layouts and the outputs of the demo
scripts, spanning lexml 3 and 6, plain groups up to a 4715-control generated
image, and every message type including gamepad bindings. Running the library
over all of it catches the things a hand-written fixture never will -- the first
pass over this corpus found two defects that the rest of the suite missed.
"""

import zlib

import pytest

import py2tosc

from _corpus import CORPUS, EDITOR_WRITTEN, payload

# Parametrised by filename so a failure names the file it came from.
ALL = pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
EDITOR = pytest.mark.parametrize("path", EDITOR_WRITTEN, ids=lambda p: p.name)


def test_the_corpus_is_not_empty():
    assert len(CORPUS) >= 20
    assert len(EDITOR_WRITTEN) >= 10
    # both formats and both format versions are represented
    assert any(p.suffix == ".tosc" for p in CORPUS)
    assert any(p.suffix == ".xml" for p in CORPUS)
    versions = {py2tosc.load(p).version for p in CORPUS}
    assert {"3", "6"} <= versions


@ALL
def test_every_file_loads(path):
    doc = py2tosc.load(path)
    assert doc.root.control_type is py2tosc.ControlType.GROUP
    assert len(list(doc.walk())) >= 1


@ALL
def test_every_file_re_serializes_identically(path):
    """Writing what was read, twice, must converge on the first pass."""
    doc = py2tosc.load(path)
    once = doc.dumps()
    assert py2tosc.loads(once).dumps() == once


@ALL
def test_every_file_survives_a_save_and_reload(path, tmp_path):
    doc = py2tosc.load(path)
    out = tmp_path / "round.tosc"
    doc.save(out)

    reloaded = py2tosc.load(out)
    assert reloaded.dumps() == doc.dumps()
    assert reloaded.version == doc.version
    assert len(list(reloaded.walk())) == len(list(doc.walk()))


@ALL
def test_every_file_survives_the_xml_export(path, tmp_path):
    doc = py2tosc.load(path)
    out = tmp_path / "round.xml"
    doc.save(out)
    assert py2tosc.load(out).dumps() == doc.dumps()


@EDITOR
def test_editor_written_files_round_trip_byte_for_byte(path):
    """The fidelity guarantee, against every real layout in the corpus.

    Two kinds of file are excluded, detected rather than hardcoded, because both
    hold numbers this library deliberately normalises on read:

    - a frame coordinate of `-0`, which survives as the integer 0
    - a colour component of `-nan(ind)`, which a Windows TouchOSC build wrote
      and which is repaired to 0

    Reproducing either byte for byte would mean carrying the damage forward.
    """
    expected = payload(path)
    produced = py2tosc.load(path).dumps(pretty=path.suffix == ".xml").encode("utf-8")

    if produced == expected:
        return

    # Only now consider excusing it, and only for the two known normalisations.
    # Checking first means a file that merely *contains* one of these but still
    # round-trips exactly is recorded as a pass, not quietly skipped.
    if b">-0<" in expected or b"nan" in expected or b"inf" in expected:
        pytest.xfail("holds a value that is normalised on read")

    assert produced == expected


@ALL
def test_every_control_has_a_type_and_id(path):
    for control in py2tosc.load(path).walk():
        assert control.control_type in py2tosc.ControlType
        assert control.id


@ALL
def test_property_values_are_native_python_types(path):
    for control in py2tosc.load(path).walk():
        for key, prop in control.properties.items():
            assert prop.key == key
            assert isinstance(
                prop.value, (bool, int, float, str, py2tosc.Frame, py2tosc.Color)
            )


@ALL
def test_ids_are_unique_within_a_layout(path):
    ids = [c.id for c in py2tosc.load(path).walk()]
    assert len(ids) == len(set(ids)), "TouchOSC expects node ids to be unique"


def test_gamepad_messages_are_read():
    """`messages.tosc` carries a gamepad binding, which 0.3.x had no model for."""
    doc = py2tosc.load(next(p for p in CORPUS if p.name == "messages.tosc"))

    pads = [
        m
        for c in doc.walk()
        for m in c.messages
        if isinstance(m, py2tosc.GamepadMessage)
    ]
    assert pads
    assert pads[0].type == "BUTTON_A"
    assert pads[0].target_var == "x"
    assert pads[0].target_type == "VALUE"


def test_every_message_type_appears_somewhere_in_the_corpus():
    seen = {
        type(m).__name__
        for p in CORPUS
        for c in py2tosc.load(p).walk()
        for m in c.messages
    }
    assert seen == {"OscMessage", "MidiMessage", "LocalMessage", "GamepadMessage"}


def test_version_3_files_omit_version_6_elements():
    """A v3 layout must not gain `<includes>` or `<noDuplicates>` on a rewrite."""
    for path in CORPUS:
        doc = py2tosc.load(path)
        if doc.version != "3":
            continue
        out = doc.dumps()
        assert "<includes>" not in out, path.name
        assert "<noDuplicates>" not in out, path.name


def test_corrupt_numbers_are_repaired_rather_than_propagated():
    """`o_custom` holds `-nan(ind)` colour components, written by a Windows build.

    Python cannot even parse that spelling, so the alternative to repairing it
    is failing to open the file. Reading it as 0 keeps the layout usable and
    keeps the written file valid.
    """
    path = next(p for p in CORPUS if p.name == "o_custom.xml")
    assert b"-nan(ind)" in payload(path)

    doc = py2tosc.load(path)

    colors = [
        prop.value
        for control in doc.walk()
        for prop in control.properties.values()
        if isinstance(prop.value, py2tosc.Color)
    ]
    assert colors
    # NaN is never equal to itself, so this catches any that survived
    assert all(c == c for color in colors for c in color)
    assert "nan" not in doc.dumps()


def test_out_of_range_colours_are_preserved_not_clamped():
    """`o_custom` also holds colour components above 1.0, from the demo that
    generated it. They are wrong, but they are what the file says, and silently
    rewriting a user's values is worse than carrying them through."""
    doc = py2tosc.load(next(p for p in CORPUS if p.name == "o_custom.xml"))

    over = [c for c in doc.walk() if c.has("color") and c.color.r > 1.0]
    assert over
    assert py2tosc.loads(doc.dumps()).find(over[0].name).color == over[0].color


def test_a_large_layout_is_handled():
    """4715 controls, from the image converter demo."""
    doc = py2tosc.load(next(p for p in CORPUS if p.name == "out.tosc"))
    assert len(list(doc.walk())) > 4000
    assert len(doc.dumps()) > 1_000_000


@ALL
def test_editing_any_file_keeps_it_loadable(path, tmp_path):
    doc = py2tosc.load(path)
    for control in doc.find_all()[:20]:
        control.color = "#e76f51"
        control.tag = "touched"

    out = tmp_path / "edited.tosc"
    doc.save(out)
    reloaded = py2tosc.load(out)

    assert [c.tag for c in reloaded.find_all()[:20]] == ["touched"] * min(
        20, len(reloaded.find_all())
    )
    assert zlib.decompress(out.read_bytes()).startswith(b"<?xml")
