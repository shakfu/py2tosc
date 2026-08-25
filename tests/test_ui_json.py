"""The layout description that `py2tosc.ui` builds from.

This dialect has no round trip to check it against -- it is read and never
written -- so the bar here is different from the one `test_json_codec.py`
holds. What is asserted instead is that a description builds the layout the
equivalent Python builds, that everything it produces is a document
`validate` passes, and that a file which will not build says why and where.
"""

import importlib.util
import json
import re

import pytest

import py2tosc
from _corpus import DATA, DEMOS, PROJECT_ROOT
from py2tosc import Trigger, ui, ui_json
from py2tosc.errors import FormatError

#: The worked example, which is also what the guide embeds. Keeping the one
#: copy in `tests/data` means the page and the test cannot describe different
#: layouts.
DESCRIPTION = DATA / "mixer.ui.json"

MIXER = json.loads(DESCRIPTION.read_text())

GUIDE = PROJECT_ROOT / "docs" / "guide" / "ui-json.md"

#: The marker the guide puts above the Python half of the comparison.
CHECKED = "<!-- checked: the same layout in Python -->"


def demo(name):
    """One demo module, loaded from `tests/demos`, which is not a package.

    Comparing against the demo itself rather than against a saved copy of what
    it once produced is the whole point: the description and the Python it
    mirrors cannot drift apart if one is built from the other every run.
    """
    spec = importlib.util.spec_from_file_location(name, DEMOS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


NODE_ID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def normalized_ids(text):
    """One layout's XML with its minted node ids replaced by their order.

    Two builds of the same layout differ only in the ids, which are fresh each
    time, so this is what "the same document" means for a comparison that has
    to be exact about everything else.
    """
    seen = {}
    for found in NODE_ID.findall(text):
        seen.setdefault(found, f"node-{len(seen):03d}")
    for old, new in seen.items():
        text = text.replace(old, new)
    return text


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


def test_a_repeat_may_be_the_node_it_repeats():
    """The short form, against the long one it stands for.

    Same layout twice, so the two spellings cannot come apart: whatever `of`
    would have held is what the node carrying `repeat` is.
    """
    short = built({"row": [{"fader": "ch$i", "repeat": 3}], "frame": [0, 0, 90, 10]})
    long = built(
        {"row": [{"repeat": 3, "of": {"fader": "ch$i"}}], "frame": [0, 0, 90, 10]}
    )
    assert [c.get("name") for c in short.root.children] == ["ch1", "ch2", "ch3"]
    assert [c.frame for c in short.root.children] == [c.frame for c in long.root.children]


def test_the_short_form_carries_everything_a_node_carries():
    doc = built(
        {
            "row": [
                {
                    "grid": "BUTTON",
                    "columns": 2,
                    "rows": 1,
                    "name": "bank$i",
                    "messages": [{"midi_cc": "$i0"}],
                    "repeat": 2,
                }
            ],
            "frame": [0, 0, 100, 10],
        }
    )
    assert [c.get("name") for c in doc.root.children] == ["bank1", "bank2"]
    assert [m.message.data1 for c in doc.root.children for m in c.messages] == [0, 1]


def test_the_two_forms_mix_in_one_list():
    doc = built(
        {
            "row": [
                {"fader": "master"},
                {"fader": "ch$i", "repeat": 2},
                {"repeat": 2, "of": {"button": "b$i"}},
            ],
            "frame": [0, 0, 100, 10],
        }
    )
    assert [c.get("name") for c in doc.root.children] == [
        "master", "ch1", "ch2", "b1", "b2",
    ]


@pytest.mark.parametrize(
    "outer, inner",
    [
        ({"repeat": 2, "as": "bank", "of": None}, {"repeat": 3, "of": None}),
        ({"repeat": 2, "as": "bank", "of": None}, None),
        (None, {"repeat": 3, "of": None}),
        (None, None),
    ],
)
def test_nested_repeats_hold_their_counters_back_in_either_form(outer, inner):
    """Which keys the inner pass owns depends on the form, so all four pair up.

    The outer pass has to leave `$i` alone whether the inner repeat keeps its
    template under `of` or is the template.
    """
    button = {"button": "b$bank-$i"}
    row = {"row": [dict(inner, of=button) if inner else {**button, "repeat": 3}]}
    node = dict(outer, of=row) if outer else {**row, "repeat": 2, "as": "bank"}

    doc = built({"column": [node], "frame": [0, 0, 90, 60]})
    assert [[k.get("name") for k in r.children] for r in doc.root.children] == [
        ["b1-1", "b1-2", "b1-3"],
        ["b2-1", "b2-2", "b2-3"],
    ]


def test_each_builds_one_node_per_row():
    """What a counter cannot do: names and numbers that follow no sequence."""
    doc = built(
        {
            "row": [
                {
                    "each": [
                        {"n": "kick", "cc": 20},
                        {"n": "snare", "cc": 24},
                        {"n": "hat", "cc": 31},
                    ],
                    "of": {"fader": "$n", "messages": [{"midi_cc": "$cc"}]},
                }
            ],
            "frame": [0, 0, 90, 10],
        }
    )
    assert [c.get("name") for c in doc.root.children] == ["kick", "snare", "hat"]
    assert [c.messages[0].message.data1 for c in doc.root.children] == [20, 24, 31]


def test_each_takes_the_short_form_too():
    rows = [{"n": "a", "shade": "ff0000ff"}, {"n": "b", "shade": "00ff00ff"}]
    short = built({"row": [{"fader": "$n", "color": "$shade", "each": rows}],
                   "frame": [0, 0, 20, 10]})
    long = built({"row": [{"each": rows, "of": {"fader": "$n", "color": "$shade"}}],
                  "frame": [0, 0, 20, 10]})
    assert [c.get("name") for c in short.root.children] == ["a", "b"]
    assert [c.color for c in short.root.children] == [c.color for c in long.root.children]


def test_each_binds_the_counters_as_well_as_the_row():
    doc = built(
        {"row": [{"button": "$n-$i", "each": [{"n": "a"}, {"n": "b"}], "from": 10}],
         "frame": [0, 0, 20, 10]}
    )
    assert [c.get("name") for c in doc.root.children] == ["a-10", "b-11"]


def test_a_field_keeps_its_type_alone_and_is_spelled_the_files_way_in_a_string():
    """The `$i0` rule, extended to whatever a row holds."""
    doc = built(
        {"row": [{"button": "$n", "outline": "$edge", "tag": "edge=$edge",
                  "each": [{"n": "a", "edge": True}, {"n": "b", "edge": False}]}],
         "frame": [0, 0, 20, 10]}
    )
    assert [c.outline for c in doc.root.children] == [True, False]
    assert [c.tag for c in doc.root.children] == ["edge=true", "edge=false"]


def test_each_nests_inside_a_repeat_and_keeps_its_own_names():
    doc = built(
        {"column": [{"row": [{"button": "$bank$n", "each": [{"n": "1"}, {"n": "2"}]}],
                     "repeat": 2, "as": "bank"}],
         "frame": [0, 0, 40, 40]}
    )
    assert [[k.get("name") for k in r.children] for r in doc.root.children] == [
        ["11", "12"],
        ["21", "22"],
    ]


def test_an_each_of_nothing_builds_nothing():
    """A generator with nothing to emit writes an empty list, which is not a typo.

    Where `repeat: 0` is refused -- nobody writes one on purpose -- an `each`
    is as long as its data, and data runs out.
    """
    doc = built(
        {"row": [{"fader": "solo"}, {"each": [], "of": {"fader": "$n"}}],
         "frame": [0, 0, 20, 10]}
    )
    assert [c.get("name") for c in doc.root.children] == ["solo"]


def test_text_sets_what_a_label_says():
    """The obvious spelling, which the tag namespace used to take.

    A label's text is a *value*, not a property, so saying it the long way is
    `{"values": [{"key": "text", "default": "Hello"}]}` for the second most
    common thing anyone does to a label.
    """
    doc = built({"label": "readout", "text": "Hello", "frame": [0, 0, 40, 20]})
    assert [(v.key, v.default) for v in doc.root.values] == [
        ("text", "Hello"),
        ("touch", False),
    ]


def test_a_text_control_is_still_what_a_bare_text_key_means():
    """The tag only loses the tie when something else in the node is one."""
    doc = built({"column": [{"text": "notes"}, {"label": "l", "text": "hi"}],
                 "frame": [0, 0, 40, 40]})
    assert [c.control_type.value for c in doc.root.children] == ["TEXT", "LABEL"]
    assert doc.root.children[0].get("name") == "notes"


def test_the_sugar_is_refused_where_the_type_carries_no_such_value():
    """A fader has no text, so `text` there is the unknown key it always was."""
    with pytest.raises(FormatError, match="unknown key 'text'"):
        built({"fader": "f", "text": "hi"})


# -- comments ----------------------------------------------------------------


def test_a_comment_is_ignored_wherever_a_key_may_appear():
    """JSON has no comment, and a description is written to be reviewed."""
    doc = built(
        {
            "//": "the channel strip",
            "column": [
                {
                    "fader": "a",
                    "//why": "left wide on purpose",
                    "values": [{"key": "x", "//": "halfway", "default": 0.5}],
                    "messages": [{"osc": "/a", "// and": "on any change"}],
                }
            ],
            "frame": [0, 0, 40, 40],
        },
        **{"//": "a note about the whole file"},
    )
    fader = doc.root.children[0]
    assert [(v.key, v.default) for v in fader.values] == [("x", 0.5)]
    assert len(fader.messages) == 1


def test_a_comment_is_not_a_custom_property():
    """`props` is the one place an unrecognised key is kept, but not this one."""
    doc = built({"fader": "a", "props": {"//": "not a property"}, "frame": [0, 0, 9, 9]})
    assert not [key for key in doc.root.properties if key.startswith("//")]


def test_a_comment_inside_a_repeat_is_not_substituted_into():
    """A note about a layout may talk about dollars without meaning a counter."""
    doc = built(
        {"row": [{"fader": "ch$i", "//": "$5 a channel", "repeat": 2}],
         "frame": [0, 0, 20, 10]},
    )
    assert [c.get("name") for c in doc.root.children] == ["ch1", "ch2"]


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


# -- partials ----------------------------------------------------------------


def test_every_partial_kind_builds():
    doc = built(
        {
            "label": "readout",
            "messages": [
                {
                    "osc": "/mix",
                    "args": [
                        {"value": "text", "conversion": "STRING"},
                        {"const": "#"},
                        {"prop": "parent.name"},
                        {"index": None},
                    ],
                }
            ],
            "frame": [0, 0, 40, 20],
        }
    )
    assert [
        (str(p.type), str(p.conversion), p.value) for p in doc.root.messages[0].arguments
    ] == [
        ("VALUE", "STRING", "text"),
        ("CONSTANT", "STRING", "#"),
        ("PROPERTY", "STRING", "parent.name"),
        ("INDEX", "INTEGER", ""),
    ]


def test_a_partial_reads_the_same_as_the_combinator_it_names():
    """The notation is `ui`'s four constructors, so it has to agree with them."""
    doc = built(
        {
            "label": "readout",
            "messages": [{"osc": "/a", "args": [{"value": "y", "scale": [0, 127]}]}],
            "frame": [0, 0, 40, 20],
        }
    )
    assert doc.root.messages[0].arguments == [ui.value("y", scale=(0, 127))]


def test_a_local_binding_may_send_a_constant():
    """What the numpad needs, and what a bare string cannot say.

    `source` reads a string as the key of a value, as `ui.connect` does, so a
    constant has to be written as one -- and the two spellings build the two
    different bindings they name.
    """
    doc = built(
        {
            "column": [
                {"button": "key", "messages": [
                    {"connect": "readout", "source": {"const": "#7"}, "to": "text"}
                ]},
                {"label": "readout"},
            ],
            "frame": [0, 0, 40, 40],
        }
    )
    sent = doc.root.children[0].messages[0]
    assert (str(sent.type), sent.value) == ("CONSTANT", "#7")
    assert doc.validate() == []


def test_a_partial_may_be_written_where_a_number_belongs():
    """`midi_note(prop("name"))` is a keyboard that names its own notes."""
    doc = built(
        {
            "button": "C3",
            "messages": [{"midi_note": {"prop": "name"}, "channel": {"index": None}}],
            "frame": [0, 0, 10, 10],
        }
    )
    channel, note = doc.root.messages[0].values[0], doc.root.messages[0].values[1]
    assert (str(note.type), note.key) == ("PROPERTY", "name")
    assert str(channel.type) == "INDEX"


def test_triggers_replace_on_and_var_entirely():
    """39 corpus messages watch two values; this is how one says so."""
    doc = built(
        {
            "xy": "pad",
            "messages": [{"osc": "/pad", "triggers": [{"var": "x"}, {"var": "y"}]}],
            "frame": [0, 0, 20, 20],
        }
    )
    assert doc.root.messages[0].triggers == [Trigger("x", "ANY"), Trigger("y", "ANY")]


def test_the_numpad_demo_written_as_a_description_builds_the_same_layout():
    """The widest thing this dialect is asked to do, against the Python it mirrors.

    45 controls, nested layouts, a Lua script carried as a property, a caption
    over every key, and twelve local bindings sending a constant into one
    readout -- plus the OSC binding that sends the total, which needs an
    argument partial. The two documents are compared as bytes with node ids
    normalised, so nothing can differ: not a colour, not a frame, not a
    trigger, and not the script, which the description carries in full.
    """
    ported = py2tosc.load(DATA / "numpad.ui.json")
    native = demo("numpad").build()

    assert normalized_ids(ported.dumps()) == normalized_ids(native.dumps())
    assert ported.validate() == []


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
        ({"fader": {"name": "a"}}, "fader takes its name, found an object"),
        ({"fader": "a", "name": "b"}, "fader is named twice"),
        ({"fader": "a", "props": {"name": "b"}}, "fader is named twice"),
        (
            {"inset": {"button": "b"}, "by": 0.1, "props": {"custom": 1}},
            "inset returns the control it was handed",
        ),
        ({"grid": "SLIDER"}, "not a control type"),
        ({"grid": 4}, "grid takes the control type"),
        ({"labelled": {"button": "b"}}, "labelled needs a caption"),
        ({"inset": {"button": "b"}}, "inset needs a `by`"),
        ({"fader": "a", "id": 7}, "id should be a string"),
        ({"fader": "a", "values": [{"keys": "x"}]}, "did you mean 'key'?"),
        ({"fader": "a", "messages": [{}]}, "a binding is one of"),
        ({"fader": "a", "messages": [{"osc": "/a", "midi_cc": 1}]}, "found 'osc' and"),
        ({"fader": "a", "messages": [{"osc": "/a", "args": ["x"]}]}, "a partial is an object"),
        ({"fader": "a", "messages": [{"osc": "/a", "args": [{}]}]}, "a partial is one of"),
        ({"fader": "a", "messages": [{"osc": "/a", "args": [{"value": 7}]}]}, "value takes the key"),
        (
            {"fader": "a", "messages": [{"osc": "/a", "args": [{"index": "first"}]}]},
            "index reads the control's own position",
        ),
        (
            {"fader": "a", "messages": [{"osc": "/a", "args": [{"value": "x", "scaled": 2}]}]},
            "did you mean 'scale'?",
        ),
        ({"fader": "a", "messages": [{"osc": "/a", "triggers": [{"on": "NOPE"}]}]}, "TriggerCondition"),
        ({"fader": "a", "messages": [{"osc": "/a", "triggers": [{"vars": "x"}]}]}, "did you mean 'var'?"),
        ({"fader": "a", "messages": [{"osc": "/a", "onn": "RISE"}]}, "did you mean 'on'?"),
        ({"fader": "a", "messages": [{"connect": 7}]}, "connect takes the name"),
        (
            {"fader": "a", "messages": [{"midi_cc": "7"}]},
            "midi_cc takes a controller number or a partial that reads one, found a string",
        ),
        (
            {"fader": "a", "messages": [{"midi_note": "60"}]},
            "midi_note takes a note number or a partial that reads one, found a string",
        ),
        ({"fader": "a", "messages": [{"midi_cc": True}]}, "found a boolean"),
        ({"fader": "a", "messages": [{"osc": 7}]}, "osc takes an address, found a number"),
        ({"fader": "a", "messages": [{"osc": "/a", "on": "NOPE"}]}, "root.messages[0]: "),
        ({"fader": "a", "messages": [{"connect": "nobody"}]}, "no control is named"),
        (
            {"row": [{"fader": "same"}, {"fader": "same"},
                     {"button": "b", "messages": [{"connect": "same"}]}]},
            "2 controls are named",
        ),
        ({"row": [{"repeat": 2}]}, "a repeat needs an `of`"),
        ({"row": [{"repeat": 2, "of": {"fader": "a"}, "fader": "b"}]}, "not both"),
        ({"label": "l", "text": 7}, "text takes the text to show, found a number"),
        (
            {"label": "l", "text": "hi", "values": [{"key": "text", "default": "no"}]},
            "both set what this control starts at",
        ),
        (
            {"row": [{"each": [{"n": "a"}], "repeat": 2, "of": {"fader": "$n"}}]},
            "counts with `repeat` or walks a list with `each`",
        ),
        ({"row": [{"each": {"n": "a"}, "of": {"fader": "$n"}}]}, "each should be a list"),
        ({"row": [{"each": [{"i": 1}], "of": {"fader": "a"}}]}, "is this repeat's own counter"),
        ({"row": [{"each": [{"n": None}], "of": {"fader": "$n"}}]}, "found null"),
        ({"row": [{"each": [{"n": ["a"]}], "of": {"fader": "$n"}}]}, "found a list"),
        ({"row": [{"each": [{"a-b": 1}], "of": {"fader": "x"}}]}, "cannot be written that way"),
        (
            {"row": [{"each": [{"n": "a"}, {"n": "b", "cc": 1}],
                      "of": {"fader": "$n", "messages": [{"midi_cc": "$cc"}]}}]},
            "$cc is not one of the names this repeat binds ($i, $i0, $n)",
        ),
        ({"fader": "$n", "each": [{"n": "a"}]}, "expands where children"),
        ({"labelled": {"button": "b", "repeat": 2}, "caption": "x"}, "expands where children"),
        ({"fader": "a", "repeat": 2}, "expands where children"),
        ({"row": [{"repeat": 0, "of": {"fader": "a"}}]}, "less than 1"),
        ({"row": [{"repeat": "two", "of": {"fader": "a"}}]}, "repeat should be a number"),
        ({"row": [{"repeat": 1, "of": {"fader": "$j"}}]}, "$j is not one of the names this repeat binds"),
        ({"row": [{"repeat": 1, "as": 7, "of": {"fader": "a"}}]}, "as should name a counter"),
        ({"row": [{"repeat": 1, "off": {"fader": "a"}}]}, "did you mean 'of'?"),
        # what a combinator itself refuses, reported where it was asked for
        ({"fader": "a", "color": "not a colour"}, "root: color: 'not a colour' is not"),
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


def test_a_value_a_control_cannot_take_names_its_key():
    """A node can carry twenty properties, and one of them is wrong."""
    with pytest.raises(FormatError) as caught:
        built({"row": [{"fader": "a"}, {"fader": "b", "color": "nope", "grid": False}]})
    assert "root.row[1]: color: 'nope' is not" in str(caught.value)


def test_a_layout_that_will_not_divide_names_the_control():
    """Resolution happens after the file is read, so the path is the layout's.

    A description fails against a size rather than against a key, and by then
    what there is to name is the control -- as `validate` names one.
    """
    with pytest.raises(FormatError) as caught:
        built(
            {
                "name": "mixer",
                "frame": [0, 0, 100, 100],
                "column": [
                    {"row": [{"fader": "a"}, {"fader": "b"}],
                     "name": "faders", "gap": 100, "pad": 50}
                ],
            }
        )
    assert "mixer/faders: a width of 100 cannot hold" in str(caught.value)


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


def test_only_the_tags_that_have_to_lose_a_tie_do():
    """A pin on the tag/property collision, which is not a fixed set.

    `_AMBIGUOUS` is computed from the property tables, so a property named
    after a tag joins it silently -- and the day that happens, an already
    written file stops meaning what it meant, with nothing to say so. The set
    is small enough to write down, so it is written down: a change here is a
    change to the dialect and has to be a deliberate one.

    Three, for two reasons. `grid` and `inset` collide with a property and an
    argument that were already called that. `text` is deliberate: it is made
    to lose so that `{"label": "readout", "text": "Hello"}` can mean what it
    obviously means.
    """
    assert ui_json._AMBIGUOUS == frozenset({"grid", "inset", "text"})


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
