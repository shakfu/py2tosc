"""The layout description that `py2tosc.ui` builds from.

This dialect has no round trip to check it against -- it is read and never
written -- so the bar here is different from the one `test_json_codec.py`
holds. What is asserted instead is that a description builds the layout the
equivalent Python builds, that everything it produces is a document
`validate` passes, and that a file which will not build says why and where.
"""

import json
import re

import pytest

import py2tosc
from _corpus import DATA, PROJECT_ROOT
from py2tosc import ui, ui_json
from py2tosc.errors import FormatError

#: The worked example, which is also what the guide embeds. Keeping the one
#: copy in `tests/data` means the page and the test cannot describe different
#: layouts.
DESCRIPTION = DATA / "mixer.ui.json"

MIXER = json.loads(DESCRIPTION.read_text())

GUIDE = PROJECT_ROOT / "docs" / "guide" / "ui-json.md"

#: The marker the guide puts above the Python half of the comparison.
CHECKED = "<!-- checked: the same layout in Python -->"


def built(root, **envelope):
    """Build one root node, with the envelope filled in around it."""
    return ui_json.build({"format": ui_json.DIALECT, "root": root, **envelope})


# -- what it builds ----------------------------------------------------------


def test_the_worked_example_builds_what_the_python_builds():
    """The description, against the code the guide says it stands for.

    The Python is read out of the page rather than written here twice. A guide
    that claims two things are equivalent should be checked on it, and this is
    the check: if either half is edited without the other, this fails.
    """
    expected = _run_the_python_from(GUIDE)
    produced = ui_json.build(MIXER)

    # Ids are minted per control and cannot match, so compare everything else.
    assert _shape(produced) == _shape(expected)


def _run_the_python_from(page):
    """The fenced Python block the page marks as the equivalent, executed."""
    text = page.read_text()
    assert CHECKED in text, f"{page.name} no longer marks its Python block"

    block = re.search(r"```python\n(.*?)```", text[text.index(CHECKED) :], re.S)
    assert block, f"{page.name} marks a Python block that is not there"

    namespace: dict = {}
    exec(compile(block.group(1), str(page), "exec"), namespace)
    return namespace["doc"]


def _shape(doc):
    """A document as everything about it except the ids, which cannot match.

    Bindings are compared by what they carry rather than by their type: two
    layouts that both hang a MIDI message on every fader are not the same
    layout if one of them numbered the controllers differently.
    """
    return [
        (
            control.control_type.value,
            sorted((key, prop.value) for key, prop in control.properties.items()),
            [(v.key, v.default) for v in control.values],
            [_binding(message) for message in control.messages],
        )
        for control in doc.walk()
    ]


def _binding(message):
    """One message as the things a reader would notice were wrong."""
    if isinstance(message, py2tosc.MidiMessage):
        command = message.message
        return ("midi", str(command.type), command.channel, command.data1)
    if isinstance(message, py2tosc.OscMessage):
        return ("osc", [(str(p.type), p.value) for p in message.path])
    if isinstance(message, py2tosc.LocalMessage):
        return ("local", message.value, message.dst_var)
    return ("gamepad", str(message.type))


def test_what_it_builds_is_a_layout_touchosc_will_accept():
    assert ui_json.build(MIXER).validate() == []


def test_what_it_builds_saves_and_reloads_like_any_other_layout(tmp_path):
    doc = ui_json.build(MIXER)
    doc.save(tmp_path / "mixer.tosc")

    assert py2tosc.load(tmp_path / "mixer.tosc").dumps() == doc.dumps()


def test_every_tag_builds_the_control_it_names():
    for tag, kind in (
        ("box", "BOX"),
        ("button", "BUTTON"),
        ("encoder", "ENCODER"),
        ("fader", "FADER"),
        ("label", "LABEL"),
        ("radar", "RADAR"),
        ("radial", "RADIAL"),
        ("radio", "RADIO"),
        ("text", "TEXT"),
        ("xy", "XY"),
    ):
        doc = built({"row": [{tag: "one"}], "frame": [0, 0, 10, 10]})
        assert doc.find("one").control_type.value == kind


def test_a_leaf_takes_its_name_by_position():
    doc = built({"fader": "cutoff", "color": "#ff0000", "frame": [0, 0, 10, 10]})
    assert doc.root.name == "cutoff"
    assert doc.root.color == (1.0, 0.0, 0.0, 1.0)


def test_a_leaf_may_have_no_name_at_all():
    assert built({"fader": None, "frame": [0, 0, 10, 10]}).root.has("name") is False


def test_a_group_holds_children_without_arranging_them():
    doc = built(
        {
            "group": [{"fader": "a", "frame": [0, 0, 5, 5]}],
            "name": "plain",
            "frame": [0, 0, 10, 10],
        }
    )
    assert doc.root.control_type is py2tosc.ControlType.GROUP
    assert doc.find("a").frame == (0, 0, 5, 5)


def test_a_pager_pages_and_a_grid_fills_itself():
    doc = built(
        {
            "pager": [
                {"row": [{"fader": "a"}], "name": "one"},
                {"grid": "BUTTON", "columns": 2, "rows": 2, "name": "two"},
            ],
            "frame": [0, 0, 200, 200],
        }
    )
    assert doc.root.control_type is py2tosc.ControlType.PAGER
    assert len(doc.find("two").children) == 4


def test_labelled_and_inset_wrap_what_they_are_given():
    doc = built(
        {
            "row": [
                {"labelled": {"button": "play"}, "caption": "Play"},
                {"inset": {"button": "stop"}, "by": 0.1},
            ],
            "frame": [0, 0, 200, 100],
        }
    )
    caption = doc.find("Play")
    assert caption.control_type is py2tosc.ControlType.LABEL
    assert caption.value("text").default == "Play"
    assert doc.find("stop").frame == (110, 10, 80, 80)


def test_a_root_with_no_frame_gets_the_default_canvas():
    assert built({"group": []}).root.frame == py2tosc.Frame(0, 0, 1024, 768)


# -- repeat ------------------------------------------------------------------


def test_repeat_expands_where_it_stands():
    doc = built(
        {
            "row": [
                {"fader": "first"},
                {"repeat": 3, "of": {"fader": "ch$i"}},
                {"fader": "last"},
            ],
            "frame": [0, 0, 100, 10],
        }
    )
    assert [c.get("name") for c in doc.root.children] == [
        "first",
        "ch1",
        "ch2",
        "ch3",
        "last",
    ]


def test_a_counter_on_its_own_keeps_its_type():
    """`"$i0"` is the number a controller number wants, `"ch$i"` is a name."""
    doc = built(
        {
            "row": [
                {"repeat": 2, "of": {"fader": "ch$i", "messages": [{"midi_cc": "$i0"}]}}
            ],
            "frame": [0, 0, 100, 10],
        }
    )
    assert [m.message.data1 for c in doc.root.children for m in c.messages] == [0, 1]


def test_from_moves_where_the_counter_starts():
    doc = built(
        {"row": [{"repeat": 3, "from": 20, "of": {"fader": "ch$i"}}], "frame": [0, 0, 30, 10]}
    )
    assert [c.get("name") for c in doc.root.children] == ["ch20", "ch21", "ch22"]


def test_nested_repeats_each_name_their_own_counter():
    doc = built(
        {
            "column": [
                {
                    "repeat": 2,
                    "as": "bank",
                    "of": {
                        "row": [{"repeat": 3, "of": {"button": "b$bank-$i"}}],
                    },
                }
            ],
            "frame": [0, 0, 100, 100],
        }
    )
    names = [c.get("name") for c in doc.walk() if c.control_type.value == "BUTTON"]
    assert names == ["b1-1", "b1-2", "b1-3", "b2-1", "b2-2", "b2-3"]


def test_braces_delimit_a_counter_from_what_follows_it():
    doc = built(
        {"row": [{"repeat": 2, "of": {"fader": "${i}0"}}], "frame": [0, 0, 20, 10]}
    )
    assert [c.get("name") for c in doc.root.children] == ["10", "20"]


def test_a_doubled_dollar_is_a_literal_one():
    doc = built(
        {"row": [{"repeat": 1, "of": {"fader": "cost$$$i"}}], "frame": [0, 0, 10, 10]}
    )
    assert doc.root.children[0].get("name") == "cost$1"


def test_a_dollar_outside_a_repeat_is_just_a_dollar():
    """Substitution belongs to `repeat`, so a script full of them is safe."""
    doc = built({"fader": "$i and $anything", "frame": [0, 0, 10, 10]})
    assert doc.root.name == "$i and $anything"


# -- properties and bindings -------------------------------------------------


def test_a_property_may_be_written_either_way():
    doc = built({"fader": "a", "corner_radius": 2.0, "gridSteps": 5, "frame": [0, 0, 9, 9]})
    assert doc.root.corner_radius == 2.0
    assert doc.root.grid_steps == 5


def test_a_custom_property_goes_under_props():
    doc = built({"fader": "a", "props": {"myThing": 3}, "frame": [0, 0, 9, 9]})
    assert doc.root.get("myThing") == 3


def test_values_replace_the_type_defaults():
    doc = built(
        {"fader": "a", "values": [{"key": "x", "default": 0.5}], "frame": [0, 0, 9, 9]}
    )
    assert [(v.key, v.default) for v in doc.root.values] == [("x", 0.5)]


def test_an_id_can_be_given_rather_than_minted():
    doc = built({"fader": "a", "id": "fixed-id", "frame": [0, 0, 9, 9]})
    assert doc.root.id == "fixed-id"


def test_each_binding_kind_builds():
    doc = built(
        {
            "row": [
                {"fader": "src", "messages": [
                    {"osc": "/a/{name}", "on": "RISE"},
                    {"midi_cc": 7, "channel": 2},
                    {"midi_note": 60},
                    {"connect": "dst", "source": "x", "to": "x"},
                ]},
                {"label": "dst"},
            ],
            "frame": [0, 0, 100, 20],
        }
    )
    kinds = [type(m).__name__ for m in doc.find("src").messages]
    assert kinds == ["OscMessage", "MidiMessage", "MidiMessage", "LocalMessage"]
    assert doc.find("src").messages[1].message.channel == 2


def test_connect_finds_its_destination_wherever_it_sits():
    """The one thing here that cannot be resolved as the tree is read."""
    doc = built(
        {
            "column": [
                {"row": [{"button": "go", "messages": [{"connect": "readout"}]}]},
                {"row": [{"label": "readout"}]},
            ],
            "frame": [0, 0, 100, 100],
        }
    )
    assert doc.find("go").messages[0].dst_id == doc.find("readout").id


# -- what it refuses ---------------------------------------------------------


@pytest.mark.parametrize(
    "root, message",
    [
        ({}, "nothing here names a control or a layout"),
        ({"fader": "a", "row": []}, "both name something"),
        ({"faderr": "a"}, "nothing here names"),
        ({"row": {}}, "root.row should be a list"),
        ({"row": [], "gpa": 4}, "unknown key 'gpa'"),
        ({"fader": "a", "colour": "#fff"}, "did you mean 'color'?"),
        ({"fader": []}, "fader takes its name, found a list"),
        ({"grid": "SLIDER"}, "not a control type"),
        ({"grid": 4}, "grid takes the control type"),
        ({"labelled": {"button": "b"}}, "labelled needs a caption"),
        ({"inset": {"button": "b"}}, "inset needs a `by`"),
        ({"fader": "a", "id": 7}, "id should be a string"),
        ({"fader": "a", "values": [{"keys": "x"}]}, "did you mean 'key'?"),
        ({"fader": "a", "messages": [{}]}, "a binding is one of"),
        ({"fader": "a", "messages": [{"osc": "/a", "midi_cc": 1}]}, "found 'osc' and"),
        ({"fader": "a", "messages": [{"osc": "/a", "args": []}]}, "takes partials"),
        ({"fader": "a", "messages": [{"osc": "/a", "onn": "RISE"}]}, "did you mean 'on'?"),
        ({"fader": "a", "messages": [{"connect": 7}]}, "connect takes the name"),
        ({"fader": "a", "messages": [{"connect": "nobody"}]}, "no control is named"),
        (
            {"row": [{"fader": "same"}, {"fader": "same"},
                     {"button": "b", "messages": [{"connect": "same"}]}]},
            "2 controls are named",
        ),
        ({"row": [{"repeat": 2}]}, "a repeat needs an `of`"),
        ({"row": [{"repeat": 0, "of": {"fader": "a"}}]}, "less than 1"),
        ({"row": [{"repeat": "two", "of": {"fader": "a"}}]}, "repeat should be a number"),
        ({"row": [{"repeat": 1, "of": {"fader": "$j"}}]}, "$j is not one of this repeat"),
        ({"row": [{"repeat": 1, "as": 7, "of": {"fader": "a"}}]}, "as should name a counter"),
        ({"row": [{"repeat": 1, "off": {"fader": "a"}}]}, "did you mean 'of'?"),
        # what a combinator itself refuses, reported where it was asked for
        ({"fader": "a", "color": "not a colour"}, "root: 'not a colour' is not"),
        ({"fader": "a", "messages": [{"midi_cc": 999}]}, "root.messages[0]: "),
        ({"fader": "a", "messages": [{"osc": 7}]}, "root.messages[0]: "),
        # a layout that resolves to nothing anyone can draw
        ({"tiles": [{"fader": "a"}], "columns": 0}, "root: tiles needs at least one"),
    ],
)
def test_a_layout_that_will_not_build_says_why(root, message):
    with pytest.raises(FormatError) as caught:
        built(root)
    assert message in str(caught.value)


@pytest.mark.parametrize(
    "layout, message",
    [
        ({"root": {"group": []}}, "is not a py2tosc.ui layout"),
        ({"format": "py2tosc.layout", "root": {}}, "is not a py2tosc.ui layout"),
        ({"format": "py2tosc.ui", "schema": 99, "root": {}}, "newer than this release"),
        ({"format": "py2tosc.ui"}, "no root node"),
        ({"format": "py2tosc.ui", "lexml": 6, "root": {"group": []}}, "lexml should be"),
        ({"format": "py2tosc.ui", "rooot": {}}, "did you mean 'root'?"),
    ],
)
def test_an_envelope_that_is_not_this_dialect_is_refused(layout, message):
    with pytest.raises(FormatError) as caught:
        ui_json.build(layout)
    assert message in str(caught.value)


def test_a_layout_that_cannot_fit_says_so_rather_than_raising_a_value_error():
    with pytest.raises(FormatError, match="will not resolve"):
        built({"row": [{"fader": "a"}, {"fader": "b"}], "gap": 50, "frame": [0, 0, 10, 10]})


def test_a_message_names_the_node_it_gave_up_on():
    with pytest.raises(FormatError) as caught:
        built(
            {
                "column": [
                    {"row": [{"fader": "a"}]},
                    {"row": [{"fader": "b"}, {"fader": "c", "gpa": 1}]},
                ]
            }
        )
    assert str(caught.value).startswith("root.column[1].row[1]:")


def test_a_repeated_node_names_which_pass_failed():
    with pytest.raises(FormatError) as caught:
        built({"row": [{"repeat": 3, "of": {"fader": "a", "gpa": 1}}]})
    assert "root.row[0]#1" in str(caught.value)


def test_bad_json_is_a_format_error():
    with pytest.raises(FormatError, match="not valid JSON"):
        ui_json.from_json("{")


# -- through load ------------------------------------------------------------


def test_load_tells_the_two_dialects_apart(tmp_path):
    description = tmp_path / "described.json"
    description.write_text(json.dumps(MIXER))

    doc = py2tosc.load(description)
    assert len(list(doc.walk())) == 27

    faithful = tmp_path / "faithful.json"
    doc.save(faithful)
    assert json.loads(faithful.read_text())["format"] == "py2tosc.layout"
    assert py2tosc.load(faithful).dumps() == doc.dumps()


def test_a_description_is_read_and_never_written(tmp_path):
    """`save` has one JSON encoding to write, and this is not it."""
    doc = ui_json.build(MIXER)
    doc.save(tmp_path / "out.json")

    written = json.loads((tmp_path / "out.json").read_text())
    assert written["format"] == "py2tosc.layout"
    assert not hasattr(ui_json, "to_json")


def test_from_json_takes_text_and_bytes():
    text = json.dumps(MIXER)
    assert len(list(ui_json.from_json(text).walk())) == 27
    assert len(list(ui_json.from_json(text.encode()).walk())) == 27


def test_the_guide_embeds_the_description_it_is_checked_against():
    """The JSON half of the comparison, by inclusion rather than by copy."""
    assert f'--8<-- "tests/data/{DESCRIPTION.name}"' in GUIDE.read_text()


def test_the_description_on_disk_loads_like_any_other_layout():
    doc = py2tosc.load(DESCRIPTION)
    assert len(list(doc.walk())) == 27
    assert doc.validate() == []
