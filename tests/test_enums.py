"""The integer enumerations, against the files TouchOSC wrote.

The manual names these values in order but gives no numbers, and TouchOSC does
not number them consistently: `shape`, `textAlignH` and `textAlignV` start at 1
while everything else starts at 0. Reading the manual alone and numbering from
zero gets three of the eleven wrong, which is the whole reason the enums exist
-- so the numbering is pinned here against real files rather than trusted.
"""

import collections

import pytest
from _corpus import CORPUS, DATA

import py2tosc
from py2tosc.enums import _IntEnum

#: The property each integer enumeration names, so a corpus sweep can check it.
PROPERTY_ENUMS = {
    "shape": py2tosc.Shape,
    "textAlignH": py2tosc.AlignH,
    "textAlignV": py2tosc.AlignV,
    "orientation": py2tosc.Orientation,
    "buttonType": py2tosc.ButtonType,
    "outlineStyle": py2tosc.OutlineStyle,
    "cursorDisplay": py2tosc.CursorDisplay,
    "font": py2tosc.Font,
    "response": py2tosc.Response,
    "radioType": py2tosc.RadioType,
    "pointerPriority": py2tosc.PointerPriority,
}


def written_values():
    """Every integer the corpus stores for each enumerated property."""
    seen = collections.defaultdict(set)
    for path in CORPUS:
        for control in py2tosc.load(path).walk():
            for key in PROPERTY_ENUMS:
                prop = control.properties.get(key)
                if prop is not None:
                    seen[key].add(prop.value)
    return seen


VALUES = written_values()


@pytest.mark.parametrize("key", sorted(PROPERTY_ENUMS))
def test_every_value_in_the_corpus_is_a_member(key):
    """No file may hold a number the enumeration cannot name."""
    unknown = sorted(v for v in VALUES[key] if v not in set(PROPERTY_ENUMS[key]))
    assert not unknown, f"{key}: {unknown} written by TouchOSC but not in the enum"


@pytest.mark.parametrize("key", sorted(PROPERTY_ENUMS))
def test_the_numbering_base_matches_what_the_files_use(key):
    """The rule that resolved the manual's silence about numbers.

    A property numbered from 0 has to write a 0 somewhere in 45 files, and one
    numbered from 1 never can. That is what distinguishes the two groups, and it
    is the check that would fail first if a member were renumbered by mistake.
    """
    members = sorted(int(m) for m in PROPERTY_ENUMS[key])
    lowest_written = min(VALUES[key])
    assert members[0] == 0 or members[0] == 1
    assert lowest_written >= members[0]
    if lowest_written == 0:
        assert members[0] == 0, f"{key} writes 0 but is numbered from {members[0]}"


def test_the_three_one_based_properties_never_write_zero():
    """Named explicitly, because getting these wrong is the failure mode."""
    for key in ("shape", "textAlignH", "textAlignV"):
        assert 0 not in VALUES[key], f"{key} wrote 0, so it is not numbered from 1"
        assert min(int(m) for m in PROPERTY_ENUMS[key]) == 1


def test_the_editor_drawn_file_pins_the_names_to_the_numbers():
    """`enums.tosc` was drawn to settle the values the bundled examples omit.

    Each control is named after the setting it was given in the editor, so the
    file checks itself: a button called `3-diamond` has to come back `DIAMOND`.
    That is what turns these members from an inference off the manual's ordering
    into a reading of what TouchOSC writes.
    """
    doc = py2tosc.load(DATA / "enums.tosc")
    checked = 0
    for control in doc.walk():
        name = (control.get("name") or "").split("-")[-1].upper()
        if not name:
            continue
        if control.control_type is py2tosc.ControlType.BUTTON:
            assert control.properties["shape"].value == py2tosc.Shape[name], name
            checked += 1
        elif control.control_type is py2tosc.ControlType.LABEL:
            assert control.properties["textAlignV"].value == py2tosc.AlignV[name], name
            checked += 1
        elif control.control_type is py2tosc.ControlType.FADER:
            assert (
                control.properties["barDisplay"].value == py2tosc.CursorDisplay[name]
            ), name
            checked += 1

    # Six shapes, three vertical alignments, one cursor display.
    assert checked == 10


def test_the_two_shapes_no_bundled_example_uses_are_now_covered():
    """`DIAMOND` and `PENTAGON` were the only members resting on inference."""
    shapes = {
        c.properties["shape"].value
        for c in py2tosc.load(DATA / "enums.tosc").walk()
        if "shape" in c.properties
    }
    assert {py2tosc.Shape.DIAMOND, py2tosc.Shape.PENTAGON} <= shapes
    assert shapes >= set(py2tosc.Shape)


def test_hexkeys_settles_the_shape_numbering():
    """119 hexagonal buttons, the sixth name against the sixth number."""
    path = next(p for p in CORPUS if p.name == "hexkeys.tosc")
    shapes = [
        c.properties["shape"].value
        for c in py2tosc.load(path).walk()
        if "shape" in c.properties
    ]
    assert shapes.count(py2tosc.Shape.HEXAGON) == 119


def test_an_int_enum_writes_the_number_not_its_name():
    """On Python 3.10 `str(IntEnum)` is the name, which would corrupt a file."""
    assert str(py2tosc.Shape.CIRCLE) == "2"
    assert f"{py2tosc.AlignH.RIGHT}" == "3"

    fader = py2tosc.fader(name="f")
    fader.shape = py2tosc.Shape.HEXAGON
    assert "<value>6</value>" in py2tosc.Document(root=fader).dumps()


def test_enums_are_interchangeable_with_the_bare_integers():
    """Layouts written before these existed must be unaffected."""
    fader = py2tosc.fader(name="f")
    fader.shape = 2
    assert fader.shape == py2tosc.Shape.CIRCLE

    fader.shape = py2tosc.Shape.CIRCLE
    assert fader.shape == 2


def test_every_int_enum_is_exported_and_named_after_its_property():
    """A member of `_IntEnum` that nothing exports is one nobody can use."""
    exported = {
        getattr(py2tosc, name)
        for name in py2tosc.__all__
        if isinstance(getattr(py2tosc, name), type)
        and issubclass(getattr(py2tosc, name), _IntEnum)
    }
    assert exported == set(PROPERTY_ENUMS.values())


def test_midi_types_are_the_eight_a_binding_can_hold():
    """The editor's Type menu offers exactly these, and stops at SYSTEMEXCLUSIVE.

    The manual's scripting reference lists nine more -- `CLOCK`, `START`,
    `STOP` and the rest of the system messages -- but those are for `sendMIDI`
    inside a script. A message binding cannot hold one, so naming them here
    would advertise a capability the format does not have.
    """
    assert {str(m) for m in py2tosc.MidiType} == {
        "NOTE_OFF",
        "NOTE_ON",
        "POLYPRESSURE",
        "CONTROLCHANGE",
        "PROGRAMCHANGE",
        "CHANNELPRESSURE",
        "PITCHBEND",
        "SYSTEMEXCLUSIVE",
    }
    for absent in ("CLOCK", "START", "STOP", "CONTINUE", "SONGPOSITION"):
        assert absent not in {str(m) for m in py2tosc.MidiType}


def test_gamepad_inputs_all_appear_in_the_example_touchosc_ships():
    """All 21 members are spellings the editor wrote, not ones we invented."""
    path = next(p for p in CORPUS if p.name == "gamepad.tosc")
    used = {
        m.type
        for c in py2tosc.load(path).walk()
        for m in c.messages
        if isinstance(m, py2tosc.GamepadMessage)
    }
    assert used == {str(m) for m in py2tosc.GamepadInput}
