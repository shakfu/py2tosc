"""The JSON encoding, held to the same fidelity bar as the XML one.

The corpus is the whole correctness argument. A representation that fails to
carry something changes the bytes that come out of `dumps`, so running every
layout in `tests/data` and `tests/examples` through JSON and back -- lexml 3
and 6, gamepad bindings, scripts, custom properties, the 4715-control generated
image -- is what proves the format complete. The unit tests below only pin the
traps that a passing corpus would not explain.
"""

import json
import math

import pytest

import py2tosc
from py2tosc import json_codec, ui
from py2tosc.errors import FormatError, SchemaError

from _corpus import CORPUS, DATA, EDITOR_WRITTEN, payload
from py2tosc.cli import CANNOT_RUN, OK, main

ALL = pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
EDITOR = pytest.mark.parametrize("path", EDITOR_WRITTEN, ids=lambda p: p.name)


def revive(doc: py2tosc.Document) -> py2tosc.Document:
    """The document after a full trip through JSON text."""
    return json_codec.from_json(json_codec.to_json(doc))


# -- the corpus -------------------------------------------------------------


@ALL
def test_every_file_survives_a_trip_through_json(path):
    doc = py2tosc.load(path)
    reloaded = revive(doc)

    assert reloaded.dumps() == doc.dumps()
    assert reloaded.version == doc.version
    assert len(list(reloaded.walk())) == len(list(doc.walk()))


@EDITOR
def test_json_round_trips_editor_written_files_byte_for_byte(path):
    """The fidelity guarantee, by way of JSON rather than of XML.

    The two exclusions are the ones `test_corpus` documents: a frame coordinate
    of `-0` and a colour component of `-nan(ind)` are both normalised on read,
    so neither can come back. They are excluded here for the same reason and
    detected the same way, rather than being anything JSON does badly.
    """
    expected = payload(path)
    doc = revive(py2tosc.load(path))
    produced = doc.dumps(pretty=path.suffix == ".xml").encode("utf-8")

    if produced == expected:
        return

    if b">-0<" in expected or b"nan" in expected or b"inf" in expected:
        pytest.xfail("holds a value that is normalised on read")

    assert produced == expected


@ALL
def test_every_property_keeps_its_type_tag(path):
    """The reason a property is written as `[tag, value]` and not as a value.

    `infer_type` cannot recover every tag from a Python value alone, so a
    format that left them out would quietly rewrite the ones it guessed wrong.
    """
    doc = py2tosc.load(path)

    def tags(document):
        # Keyed rather than listed, because property order is not part of the
        # format: `codec` writes them sorted, and a loaded file holds them in
        # the order the file happened to use.
        return {
            (control.id, key): prop.type
            for control in document.walk()
            for key, prop in control.properties.items()
        }

    assert tags(revive(doc)) == tags(doc)


@ALL
def test_the_output_is_json_and_nothing_but_json(path):
    """No NaN, no infinity, no Python repr leaking through a value."""
    text = json_codec.to_json(py2tosc.load(path))
    assert json.loads(text)  # strict by default: bare NaN would not parse


@ALL
def test_encoding_is_deterministic_and_converges(path):
    """Writing what was read, twice, must converge on the first pass.

    It need not match the first encoding, and for one corpus file it does not.
    `codec._number` returns its integer default for a component that will not
    parse, so the `-nan(ind)` in `o_custom.xml` reaches the model as `0` rather
    than `0.0` and is written as `0`; reading that back gives the float, since
    `to_color` floats what it is handed. Neither reaches the XML, where
    `codec._num` renders both as `0` -- which is why the byte-for-byte test
    above passes on the same file.
    """
    doc = py2tosc.load(path)
    assert json_codec.to_json(doc) == json_codec.to_json(doc)

    once = json_codec.to_json(revive(doc))
    assert json_codec.to_json(revive(revive(doc))) == once


# -- the traps --------------------------------------------------------------


def test_a_numeric_default_does_not_come_back_as_a_boolean():
    """`0.0 == False` in Python, and the two are written differently.

    A thinning pass that dropped a field on equality alone would turn every
    fader's `x` default into `false`, which TouchOSC reads as a different
    document.
    """
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.add(py2tosc.fader(name="ch1"))

    revived = revive(doc)
    default = revived.find("ch1").value("x").default

    assert default == 0
    assert not isinstance(default, bool)
    assert b">0<" in revived.dumps().encode()
    assert b">false<" not in revived.dumps().encode()


def test_a_true_boolean_default_stays_a_boolean():
    """The other half of the same trap, which the corpus does not reach."""
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.add(
        py2tosc.button(name="pad", values=[py2tosc.Value("x", default=True)])
    )

    default = revive(doc).find("pad").value("x").default
    assert default is True


def test_text_that_looks_like_a_boolean_stays_text():
    """JSON carries more here than the XML does, which has to guess from the key."""
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.add(
        py2tosc.label(name="caption", values=[py2tosc.Value("text", default="true")])
    )

    assert revive(doc).find("caption").value("text").default == "true"


def test_an_empty_trigger_list_is_not_a_default_trigger_list():
    """Thinning must compare by value: `[]` and `[Trigger()]` are both falsy."""
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.add(py2tosc.fader(name="ch1", messages=[py2tosc.OscMessage(triggers=[])]))

    assert revive(doc).find("ch1").messages[0].triggers == []


def test_an_empty_connection_string_survives():
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.add(py2tosc.fader(name="ch1", messages=[py2tosc.OscMessage(connections="")]))

    assert revive(doc).find("ch1").messages[0].connections == ""


def test_a_frame_under_a_custom_key_is_not_mistaken_for_a_colour():
    """Four floats are a frame or a colour, and only the tag says which."""
    control = py2tosc.box(name="odd")
    control.set("myFrame", (0.5, 0.5, 100.0, 100.0), type="r")
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.add(control)

    prop = revive(doc).find("odd").properties["myFrame"]
    assert prop.type is py2tosc.PropertyType.FRAME
    assert prop.value == (0.5, 0.5, 100.0, 100.0)


def test_node_ids_are_preserved_because_local_messages_point_at_them():
    doc = py2tosc.Document(root=py2tosc.group(name="root"))
    target = py2tosc.fader(name="target")
    source = py2tosc.button(
        name="source", messages=[py2tosc.LocalMessage(dst_id=target.id, dst_var="x")]
    )
    doc.root.add(target, source)

    revived = revive(doc)
    assert revived.find("source").messages[0].dst_id == revived.find("target").id


def test_the_includes_element_is_carried_on_the_node_that_had_it():
    """A child node's `<includes/>` exists only because the file said so."""
    path = next(p for p in CORPUS if p.name == "newTemplate.tosc")
    doc = py2tosc.load(path)

    before = [getattr(c, "_has_includes", False) for c in doc.walk()]
    after = [getattr(c, "_has_includes", False) for c in revive(doc).walk()]
    assert after == before


def test_the_format_version_survives():
    older = py2tosc.Document(root=py2tosc.group(), version="3")
    assert revive(older).version == "3"


def test_decoding_applies_no_type_defaults():
    """A node with no properties is a control with none, not a stock FADER."""
    control = json_codec.decode({"type": "FADER", "id": "x", "properties": {}})
    assert control.properties == {}
    assert control.values == []


def test_a_node_without_an_id_is_given_one():
    control = json_codec.decode({"type": "FADER", "properties": {}})
    assert control.id


def test_a_hand_written_layout_needs_no_envelope_markers():
    doc = json_codec.from_json('{"root": {"type": "GROUP", "properties": {}}}')
    assert doc.root.control_type is py2tosc.ControlType.GROUP
    assert doc.version == "6"


# -- what it refuses --------------------------------------------------------


@pytest.mark.parametrize(
    "source, message",
    [
        # the envelope
        ("{", "not valid JSON"),
        ("[]", "the layout should be an object, found a list"),
        ('{"format": "something.else", "root": {}}', "not a py2tosc layout"),
        ('{"schema": 99, "root": {}}', "newer than this release"),
        ('{"roots": {}}', "did you mean 'root'?"),
        ("{}", "no root node"),
        ('{"lexml": 6, "root": {"type": "GROUP"}}', "lexml should be a string"),
        # the node
        ('{"root": {"properties": {}}}', "root: a node needs a type"),
        ('{"root": {"type": "SLIDER"}}', "not a control type"),
        ('{"root": {"type": "GROUP", "childs": []}}', "did you mean 'children'?"),
        ('{"root": {"type": "GROUP", "id": 7}}', "id should be a string"),
        ('{"root": {"type": "GROUP", "properties": []}}', "properties should be an object"),
        ('{"root": {"type": "GROUP", "children": {}}}', "root.children should be a list"),
        ('{"root": {"type": "GROUP", "children": [7]}}', "children[0] should be an object"),
        # a property
        (
            '{"root": {"type": "GROUP", "properties": {"name": "x"}}}',
            "root.properties.name: a property is a [type, value] pair",
        ),
        (
            '{"root": {"type": "GROUP", "properties": {"name": ["z", "x"]}}}',
            "'z' is not a property type",
        ),
        (
            '{"root": {"type": "GROUP", "properties": {"frame": ["r", [1, 2]]}}}',
            "root.properties.frame: a frame needs 4 values",
        ),
        (
            '{"root": {"type": "GROUP", "properties":'
            ' {"color": ["c", [{"$float": "huge"}, 0, 0, 1]]}}}',
            "not an infinity or a NaN",
        ),
        # a value
        ('{"root": {"type": "GROUP", "values": [{"nope": 1}]}}', "unknown key 'nope'"),
        ('{"root": {"type": "GROUP", "values": [{"keys": "x"}]}}', "did you mean 'key'?"),
        ('{"root": {"type": "GROUP", "values": "x"}}', "root.values should be a list"),
        # a binding
        (
            '{"root": {"type": "GROUP", "messages": [{"kind": "sysex"}]}}',
            "'sysex' is not a binding kind",
        ),
        (
            '{"root": {"type": "GROUP", "messages": [{}]}}',
            "root.messages[0]: None is not a binding kind",
        ),
        (
            '{"root": {"type": "GROUP", "messages": [{"kind": "osc", "nope": 1}]}}',
            "root.messages[0]: unknown key 'nope'",
        ),
        (
            '{"root": {"type": "GROUP", "messages": [{"kind": "osc", "path": 1}]}}',
            "root.messages[0].path should be a list",
        ),
        (
            '{"root": {"type": "GROUP", "messages":'
            ' [{"kind": "osc", "path": [{"values": "x"}]}]}}',
            "root.messages[0].path[0]: unknown key 'values'",
        ),
        (
            '{"root": {"type": "GROUP", "messages":'
            ' [{"kind": "midi", "message": {"kind": 1}}]}}',
            "root.messages[0].message: unknown key 'kind'",
        ),
    ],
)
def test_unreadable_input_is_a_format_error(source, message):
    with pytest.raises(FormatError) as caught:
        json_codec.from_json(source)
    assert message in str(caught.value)


def test_a_message_names_the_node_it_gave_up_on():
    """The reason every reader takes a breadcrumb: a layout is a deep tree, and
    `a frame needs 4 values` alone does not say which of 4715 controls it is."""
    source = json.dumps(
        {
            "root": {
                "type": "GROUP",
                "children": [
                    {"type": "GROUP", "children": [{"type": "FADER"}]},
                    {"type": "FADER", "properties": {"frame": ["r", [1, 2]]}},
                ],
            }
        }
    )

    with pytest.raises(FormatError) as caught:
        json_codec.from_json(source)
    assert str(caught.value).startswith("root.children[1].properties.frame:")


def test_a_key_nothing_reads_is_never_ignored():
    """The failure this format has to refuse: a subtree that vanishes quietly."""
    layout = {"root": {"type": "GROUP", "children": [{"type": "FADER"}]}}
    assert json_codec.from_json(json.dumps(layout)).root.children

    layout["root"]["childs"] = layout["root"].pop("children")
    with pytest.raises(FormatError, match="did you mean 'children'"):
        json_codec.from_json(json.dumps(layout))


def test_a_format_error_is_still_a_value_error():
    """The type `load` and `loads` have always documented."""
    with pytest.raises(ValueError):
        json_codec.from_json("not json")


def test_an_infinity_survives_because_the_corpus_holds_ninety_of_them():
    """`o_custom.xml` was written with `inf` colour components, and the XML
    codec has carried them ever since. JSON has no such number, so it is
    escaped rather than dropped, refused or turned into `Infinity`."""
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.color = (math.inf, 0.0, 0.0, 1.0)

    text = json_codec.to_json(doc)
    assert "Infinity" not in text
    assert json.loads(text)["root"]["properties"]["color"][1][0] == {"$float": "inf"}
    assert revive(doc).root.color.r == math.inf


def test_a_nan_survives_too():
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.set("cornerRadius", math.nan)

    assert "NaN" not in json_codec.to_json(doc)
    assert math.isnan(revive(doc).root.corner_radius)


def test_text_that_says_inf_is_not_a_number():
    """The escape is an object, so no string can collide with it."""
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.add(
        py2tosc.label(name="caption", values=[py2tosc.Value("text", default="inf")])
    )

    assert revive(doc).find("caption").value("text").default == "inf"


def test_an_unknown_message_type_is_a_type_error():
    control = py2tosc.fader(name="ch1")
    control.messages.append(object())

    with pytest.raises(TypeError):
        json_codec.encode(control)


# -- shape ------------------------------------------------------------------


def test_the_envelope_says_what_it_is():
    doc = py2tosc.Document(root=py2tosc.group(name="root"), version="6")
    data = json.loads(json_codec.to_json(doc))

    assert data["format"] == json_codec.FORMAT
    assert data["schema"] == json_codec.SCHEMA
    assert data["lexml"] == "6"
    assert data["root"]["type"] == "GROUP"


def test_properties_are_written_sorted_and_tagged():
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 8, 8)))
    properties = json.loads(json_codec.to_json(doc))["root"]["properties"]

    assert list(properties) == sorted(properties)
    assert properties["frame"] == ["r", [0.0, 0.0, 8.0, 8.0]]
    assert properties["name"] == ["s", "root"]
    assert properties["visible"] == ["b", True]


def test_a_binding_at_its_defaults_is_written_as_its_kind_alone():
    """The thinning that keeps a generated layout readable."""
    control = py2tosc.fader(name="ch1", messages=[py2tosc.OscMessage()])
    assert json_codec.encode(control)["messages"] == [{"kind": "osc"}]


def test_what_a_thing_is_survives_the_thinning():
    """A slot at its defaults must still say which slot it is.

    `{}` decodes correctly and reads as a hole, which is the one place where
    what the file says and what a person can follow come apart.
    """
    control = py2tosc.fader(
        name="ch1",
        values=[py2tosc.Value("touch")],
        messages=[py2tosc.MidiMessage(values=[py2tosc.MidiValue()])],
    )
    node = json_codec.encode(control)

    assert node["values"] == [{"key": "touch"}]
    assert node["messages"][0]["values"] == [{"type": "CONSTANT"}]


def test_a_property_is_one_line_and_so_is_a_colour():
    """`json.dumps(indent=2)` would spend seven lines on a colour. A layout is
    a file people read diffs of, so the renderer keeps a leaf on its line."""
    doc = py2tosc.Document(root=py2tosc.group(name="root", color="#ff0000"))
    lines = json_codec.to_json(doc).splitlines()

    assert '      "color": ["c", [1.0, 0.0, 0.0, 1.0]],' in lines
    assert '      "name": ["s", "root"],' in lines


def test_an_escaped_number_stays_inline_with_the_numbers_beside_it():
    doc = py2tosc.Document(root=py2tosc.group())
    doc.root.color = (math.inf, 0.0, 0.0, 1.0)

    assert '["c", [{"$float": "inf"}, 0.0, 0.0, 1.0]]' in json_codec.to_json(doc)


def test_a_node_is_never_inlined():
    """The other half of the rule: what nests gets a line each."""
    doc = py2tosc.Document(root=py2tosc.group(name="root"))
    doc.root.add(py2tosc.fader(name="ch1"))
    lines = json_codec.to_json(doc).splitlines()

    assert '    "children": [' in lines
    assert sum('"type": "FADER"' in line for line in lines) == 1


def test_the_compact_form_is_one_line():
    doc = py2tosc.Document(root=py2tosc.group())
    text = json_codec.to_json(doc, indent=None)

    assert "\n" not in text
    assert json_codec.from_json(text).dumps() == doc.dumps()


# -- through Document and the command line -----------------------------------


@ALL
def test_a_json_file_saves_and_loads_like_any_other(path, tmp_path):
    """The point of the extension dispatch: `.json` is a layout format now."""
    doc = py2tosc.load(path)
    out = tmp_path / "round.json"
    doc.save(out)

    reloaded = py2tosc.load(out)
    assert reloaded.dumps() == doc.dumps()
    assert reloaded.version == doc.version


def test_the_form_written_follows_the_extension(tmp_path):
    doc = py2tosc.Document(root=py2tosc.group(name="root"))

    doc.save(tmp_path / "layout.json")
    doc.save(tmp_path / "layout.tosc")
    doc.save(tmp_path / "layout.xml")

    assert (tmp_path / "layout.json").read_text().startswith("{\n  \"format\"")
    assert (tmp_path / "layout.tosc").read_bytes()[0] == 0x78  # zlib
    assert (tmp_path / "layout.xml").read_text().startswith("<?xml")


def test_pretty_still_overrides_what_the_extension_chose(tmp_path):
    doc = py2tosc.Document(root=py2tosc.group(name="root"))
    doc.save(tmp_path / "compact.json", pretty=False)

    text = (tmp_path / "compact.json").read_text()
    assert "\n" not in text
    assert py2tosc.load(tmp_path / "compact.json").dumps() == doc.dumps()


def test_an_unresolved_layout_is_placed_before_it_is_written(tmp_path):
    """`save` resolves whatever the combinators left unsized, in either format."""
    doc = py2tosc.Document(
        root=ui.row(py2tosc.fader(name="a"), py2tosc.fader(name="b"), frame=(0, 0, 80, 40))
    )
    doc.save(tmp_path / "row.json")

    assert py2tosc.load(tmp_path / "row.json").find("b").frame.w == 40


@pytest.mark.parametrize(
    "source",
    [
        '{"root": {"type": "GROUP", "properties": {}}}',
        '   \n {"root": {"type": "GROUP", "properties": {}}}',
        b'{"root": {"type": "GROUP", "properties": {}}}',
        b'\xef\xbb\xbf{"root": {"type": "GROUP", "properties": {}}}',
    ],
)
def test_json_is_told_from_xml_by_its_first_character(source):
    """`loads` takes all three forms without being told which it was given."""
    assert py2tosc.loads(source).root.control_type is py2tosc.ControlType.GROUP


def test_xml_still_reads_as_xml():
    assert py2tosc.loads(payload(DATA / "fader_with_label.tosc")).version == "6"


def test_convert_writes_json_and_reads_it_back(tmp_path, capsys):
    out = tmp_path / "mixer.json"
    code = main(["convert", str(DATA / "fader_with_label.tosc"), "-o", str(out)])
    assert code == OK
    assert out.read_text().startswith("{")

    back = tmp_path / "mixer.tosc"
    assert main(["convert", str(out), "-o", str(back)]) == OK
    assert py2tosc.load(back).dumps() == py2tosc.load(DATA / "fader_with_label.tosc").dumps()
    capsys.readouterr()


def test_every_subcommand_accepts_a_json_layout(tmp_path, capsys):
    layout = tmp_path / "mixer.json"
    py2tosc.load(DATA / "fader_with_label.tosc").save(layout)

    assert main(["show", str(layout)]) == OK
    assert "3 controls" in capsys.readouterr().out

    assert main(["validate", str(layout)]) == OK
    assert "clean" in capsys.readouterr().out

    assert main(["decompile", str(layout)]) == OK
    assert "py2tosc" in capsys.readouterr().out


def test_an_unreadable_json_layout_is_a_message_and_not_a_traceback(tmp_path, capsys):
    broken = tmp_path / "broken.json"
    broken.write_text('{"root": {"type": "GROUP", "childs": []}}')

    with pytest.raises(SystemExit) as caught:
        main(["show", str(broken)])

    assert caught.value.code == CANNOT_RUN
    assert "did you mean 'children'?" in capsys.readouterr().err


# -- what this release reads -------------------------------------------------


def test_the_schema_range_is_what_the_newest_says():
    assert json_codec.SCHEMAS == range(1, json_codec.SCHEMA + 1)
    assert json_codec.supports(json_codec.SCHEMA)
    assert not json_codec.supports(json_codec.SCHEMA + 1)
    assert not json_codec.supports(0)


def test_a_schema_this_release_does_not_read_has_its_own_type():
    """A `FormatError` is about the file; this one is about the reader."""
    with pytest.raises(SchemaError) as caught:
        json_codec.from_json('{"schema": 99, "root": {"type": "GROUP"}}')
    assert "upgrade py2tosc" in str(caught.value)
    assert isinstance(caught.value, FormatError)


def test_a_schema_that_is_not_a_number_is_an_envelope_problem():
    with pytest.raises(FormatError) as caught:
        json_codec.from_json('{"schema": "one", "root": {"type": "GROUP"}}')
    assert "schema should be a number, found a string" in str(caught.value)
    assert not isinstance(caught.value, SchemaError)
