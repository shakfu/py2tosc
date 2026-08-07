"""Building a control surface from a parameter list.

This is the module the `py2tosc build` subcommand and the `control_surface`
demo both call, so its contract is public in a way a demo's was not: the shape
of the JSON, and what happens to a name or a controller number that cannot be
used as given.
"""

import pytest

import py2tosc
from py2tosc import surface


def bindings(doc, kind):
    return [m for c in doc.walk() for m in c.messages if isinstance(m, kind)]


# -- reading the parameter list ----------------------------------------------


def test_a_list_of_names_is_the_short_form():
    assert surface.read(["Threshold", "Ratio"]) == [
        surface.Parameter("Threshold"),
        surface.Parameter("Ratio"),
    ]


def test_an_object_may_name_its_own_controller_and_channel():
    assert surface.read([{"name": "Threshold", "cc": 20, "channel": 1}]) == [
        surface.Parameter("Threshold", cc=20, channel=1)
    ]


def test_a_host_index_is_ignored():
    """An index identifies the parameter to the host and is not a CC.

    A real export runs well past the 127 a controller number allows, so reading
    one as a CC would fail on two thirds of the file.
    """
    parameters = surface.read([{"index": 182, "name": "Delta"}])
    assert parameters == [surface.Parameter("Delta")]

    doc = surface.build(parameters)
    assert bindings(doc, py2tosc.MidiMessage)[0].message.data1 == 0


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"not": "a list"}, "expected a list"),
        ([1, 2], "expected a name"),
        ([{"cc": 3}], "has no name"),
        ([{"name": ""}], "has no name"),
    ],
)
def test_a_malformed_list_says_what_is_wrong(payload, message):
    """A demo can read whatever is in front of it; a public entry point cannot."""
    with pytest.raises((TypeError, ValueError), match=message):
        surface.read(payload)


# -- names on the wire -------------------------------------------------------


def test_a_name_becomes_an_osc_safe_slug():
    assert surface.slug("Side Chain High Frequency") == "sideChainHighFrequency"
    assert surface.slug("pro_c_2_fabfilter") == "proC2Fabfilter"
    assert surface.slug("!!!") == "parameter"


def test_repeated_names_are_numbered():
    """Real lists repeat, and two controls cannot share one address."""
    assert surface.unique(["a", "b", "a", "a"]) == ["a", "b", "a2", "a3"]


def test_a_namespace_may_be_more_than_one_segment():
    assert surface.namespace("Synth/Bank 1") == "synth/bank1"
    assert surface.namespace("/leading/and/trailing/") == "leading/and/trailing"
    assert surface.namespace("  ") == ""


def test_names_reach_the_wire_intact():
    doc = surface.build(surface.read(["Side Chain", "Bypass", "Bypass"]))
    names = [c.name for c in doc.find_all(type="FADER")]
    assert names == ["sideChain", "bypass", "bypass2"]
    assert not [n for n in names if set(n) & set(" #*,?[]{}/")]


# -- what comes out ----------------------------------------------------------


def test_controller_numbers_come_from_position():
    doc = surface.build(surface.read(["a", "b", "c"]))
    assert [m.message.data1 for m in bindings(doc, py2tosc.MidiMessage)] == [0, 1, 2]


def test_a_named_controller_number_wins():
    doc = surface.build(surface.read([{"name": "a", "cc": 64, "channel": 2}]))
    command = bindings(doc, py2tosc.MidiMessage)[0].message
    assert (command.data1, command.channel) == (64, 2)


def test_parameters_past_the_controller_range_still_get_osc():
    """A list can be longer than 128; MIDI runs out and OSC does not."""
    doc = surface.build(surface.read([f"p{n}" for n in range(130)]))
    assert len(doc.find_all(type="FADER")) == 130
    assert len(bindings(doc, py2tosc.MidiMessage)) == surface.CC_LIMIT
    assert len(bindings(doc, py2tosc.OscMessage)) == 130


def test_either_binding_can_be_left_out():
    parameters = surface.read(["a", "b"])
    assert not bindings(surface.build(parameters, midi=False), py2tosc.MidiMessage)
    assert not bindings(surface.build(parameters, osc=False), py2tosc.OscMessage)


def test_a_surface_with_neither_binding_is_refused():
    with pytest.raises(ValueError, match="would do nothing"):
        surface.build(surface.read(["a"]), midi=False, osc=False)


def test_an_empty_list_is_refused():
    with pytest.raises(ValueError, match="at least one parameter"):
        surface.build([])


def test_it_pages_and_validates():
    doc = surface.build(surface.read([f"p{n}" for n in range(30)]), columns=4, rows=3)
    assert len(doc.find(type="PAGER").children) == 3
    assert doc.validate() == []


def test_the_pager_is_not_the_root():
    """TouchOSC gives the root none of its type's behaviour, so a PAGER there
    draws a tab bar and then stacks every page instead of paging."""
    doc = surface.build(surface.read(["a"]))
    assert doc.root.control_type is py2tosc.ControlType.GROUP
    assert doc.find(type="PAGER") in doc.root.children


def test_the_canvas_is_a_shipped_template_size():
    """1024x768 was a guess; the templates TouchOSC ships are small and wide,
    and a surface that fits `automat5_mk2`'s canvas scales up to anything."""
    assert surface.SIZE == (568, 320)
    assert tuple(int(v) for v in surface.build(surface.read(["a"])).root.frame) == (
        0,
        0,
        568,
        320,
    )


def test_the_canvas_can_be_chosen():
    doc = surface.build(surface.read(["a"]), frame=(0, 0, 320, 480))
    assert (int(doc.root.frame.w), int(doc.root.frame.h)) == (320, 480)


@pytest.mark.parametrize("size", [(320, 480), (568, 320), (1024, 768), (1920, 1080)])
def test_caption_text_follows_the_canvas(size):
    """A fixed text size only suits one canvas. At 1024x768 the old fixed 14pt
    sat at 0.28 of its box, half the corpus median."""
    doc = surface.build(surface.read([f"p{n}" for n in range(6)]), frame=(0, 0, *size))
    low, high = surface.TEXT_RANGE
    captions = [c for c in doc.walk() if str(c.get("name", "")).endswith("Caption")]
    assert captions
    for caption in captions:
        size_ = caption.get("textSize")
        assert low <= size_ <= high
        assert abs(size_ / caption.frame.h - surface.TEXT_RATIO) < 0.06


def test_text_is_clamped_rather_than_absurd():
    """A tiny canvas would otherwise ask for 1pt text, a huge one for 90pt."""
    low, high = surface.TEXT_RANGE
    for size in ((120, 80), (4000, 3000)):
        doc = surface.build(surface.read(["a", "b"]), frame=(0, 0, *size))
        for control in doc.walk():
            if str(control.get("name", "")).endswith("Caption"):
                assert low <= control.get("textSize") <= high
