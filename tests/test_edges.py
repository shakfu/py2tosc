"""Corners of the API that the rest of the suite never reaches.

Written from a coverage report rather than from the docs, which is the point:
these are the paths a reader would assume work because they exist. Several were
never executed before this file, including `del control.name`, `control[0]`, and
`Property.__eq__` against a non-Property.
"""

import xml.etree.ElementTree as ET

import pytest

import py2tosc
from py2tosc.codec import _is_modern, _read_default, _read_partials, _write_message
from py2tosc.properties import Frame, Property, PropertyType, infer_type


# -- Control dunders ---------------------------------------------------------


def test_del_removes_a_property():
    control = py2tosc.fader(name="cutoff")
    assert control.has("name")

    del control.name
    assert not control.has("name")


def test_del_on_a_property_that_is_not_set_raises():
    with pytest.raises(AttributeError):
        del py2tosc.fader().nonsense


def test_del_accepts_snake_case():
    control = py2tosc.fader()
    assert control.has("cornerRadius")
    del control.corner_radius
    assert not control.has("corner_radius")


def test_indexing_returns_the_nth_child():
    parent = py2tosc.group()
    first, second = py2tosc.fader(name="a"), py2tosc.fader(name="b")
    parent.add(first, second)

    assert parent[0] is first
    assert parent[1] is second
    assert parent[-1] is second
    with pytest.raises(IndexError):
        parent[2]


def test_document_repr_counts_controls():
    doc = py2tosc.Document.new()
    doc.add(py2tosc.fader(name="a"), py2tosc.group(name="b"))

    text = repr(doc)
    assert "version=6" in text
    assert "2 controls" in text  # the root is not counted


# -- Property ----------------------------------------------------------------


def test_property_value_can_be_reassigned_and_is_recoerced():
    prop = Property("textSize", 14)
    prop.value = "20"  # a string, on an integer property
    assert prop.value == 20
    assert isinstance(prop.value, int)


def test_property_compares_unequal_to_other_types():
    assert Property("name", "a") != "not a property"
    assert Property("name", "a").__eq__(object()) is NotImplemented


def test_property_is_hashable_and_deduplicates():
    a, b = Property("name", "x"), Property("name", "x")
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_a_frame_instance_under_a_custom_key_is_stored_as_a_frame():
    """The inference path for a key the format has never heard of."""
    assert infer_type("myBounds", Frame(0, 0, 10, 20)) is PropertyType.FRAME

    control = py2tosc.group()
    control.set("myBounds", Frame(0, 0, 10, 20))
    assert control.properties["myBounds"].type is PropertyType.FRAME


# -- codec defensive paths ---------------------------------------------------


def test_writing_something_that_is_not_a_message_raises():
    control = py2tosc.fader()
    control.messages.append("not a message")  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="not a message type"):
        py2tosc.Document(root=control).dumps()


def test_an_unparseable_format_version_is_treated_as_modern():
    """Anything newer than 6 will keep `<includes>`, so err that way."""
    assert _is_modern("6") is True
    assert _is_modern("3") is False
    assert _is_modern("not-a-number") is True

    doc = py2tosc.loads("<lexml version='beta'><node ID='a' type='GROUP'/></lexml>")
    assert doc.version == "beta"
    assert "<includes></includes>" in doc.dumps()


def test_a_non_numeric_value_default_is_kept_as_text():
    assert _read_default("x", "0.5") == 0.5
    assert _read_default("touch", "true") is True
    assert _read_default("x", "banana") == "banana"  # neither bool nor number
    assert _read_default("text", "0") == "0"  # text is never coerced


def test_a_non_numeric_default_survives_a_round_trip():
    doc = py2tosc.loads(
        "<lexml version='6'><node ID='a' type='GROUP'><values><value>"
        "<key>x</key><default>banana</default></value></values></node></lexml>"
    )
    assert doc.root.value("x").default == "banana"
    assert py2tosc.loads(doc.dumps()).root.value("x").default == "banana"


def test_an_osc_message_with_no_path_or_arguments():
    assert _read_partials(None) == []

    doc = py2tosc.loads(
        "<lexml version='6'><node ID='a' type='GROUP'><messages>"
        "<osc><enabled>1</enabled></osc>"
        "</messages></node></lexml>"
    )
    message = doc.root.messages[0]
    assert message.path == []
    assert message.arguments == []
    assert message.triggers == []
    # and it still writes back as well-formed XML
    assert ET.fromstring(doc.dumps()) is not None


def test_write_message_rejects_an_unknown_type_directly():
    from py2tosc.codec import _Writer

    with pytest.raises(TypeError, match="not a message type"):
        _write_message(_Writer(), object(), modern=True)  # type: ignore[arg-type]
