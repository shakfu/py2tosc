"""Malformed and minimal input.

py2tosc reads files written by other tools and by older versions of itself, so
degrading gracefully matters more than rejecting early.
"""

import pytest

import py2tosc

MINIMAL = (
    "<?xml version='1.0' encoding='UTF-8'?>"
    "<lexml version='6'><node ID='a' type='GROUP'/></lexml>"
)


def test_a_node_with_nothing_in_it():
    doc = py2tosc.loads(MINIMAL)
    assert doc.root.id == "a"
    assert doc.root.properties == {}
    assert doc.root.values == []
    assert doc.root.messages == []
    assert doc.root.children == []


def test_a_property_with_no_value_element():
    doc = py2tosc.loads(
        "<lexml version='6'><node ID='a' type='GROUP'><properties>"
        "<property type='r'><key>frame</key></property>"
        "<property type='c'><key>color</key></property>"
        "<property type='s'><key>name</key></property>"
        "</properties></node></lexml>"
    )
    assert doc.root.frame == (0, 0, 0, 0)
    assert doc.root.color == (0.0, 0.0, 0.0, 0.0)
    assert doc.root.name == ""


def test_a_property_with_unparseable_numbers():
    doc = py2tosc.loads(
        "<lexml version='6'><node ID='a' type='GROUP'><properties>"
        "<property type='i'><key>textSize</key><value>huge</value></property>"
        "</properties></node></lexml>"
    )
    assert doc.root.text_size == 0


def test_a_midi_message_with_no_command_block():
    doc = py2tosc.loads(
        "<lexml version='6'><node ID='a' type='GROUP'><messages>"
        "<midi><enabled>1</enabled></midi>"
        "</messages></node></lexml>"
    )
    midi = doc.root.messages[0]
    assert midi.message.type == "CONTROLCHANGE"
    assert midi.values == []


def test_an_unknown_message_type_is_rejected():
    with pytest.raises(ValueError, match="not a known message type"):
        py2tosc.loads(
            "<lexml version='6'><node ID='a' type='GROUP'><messages>"
            "<telepathy><enabled>1</enabled></telepathy>"
            "</messages></node></lexml>"
        )


def test_an_unknown_control_type_is_rejected():
    with pytest.raises(ValueError):
        py2tosc.loads("<lexml version='6'><node ID='a' type='SPACESHIP'/></lexml>")


def test_a_document_with_no_node():
    with pytest.raises(ValueError, match="no <node>"):
        py2tosc.loads("<lexml version='6'></lexml>")


def test_not_xml_at_all():
    with pytest.raises(Exception):
        py2tosc.loads("this is not a layout")


def test_truncated_compressed_data(tmp_path):
    path = tmp_path / "broken.tosc"
    path.write_bytes(b"\x78\x9c" + b"garbage")
    with pytest.raises(Exception):
        py2tosc.load(path)


def test_minimal_document_round_trips():
    doc = py2tosc.loads(MINIMAL)
    assert py2tosc.loads(doc.dumps()).dumps() == doc.dumps()


def test_empty_containers_are_not_written():
    out = py2tosc.loads(MINIMAL).dumps()
    assert "<values>" not in out
    assert "<messages>" not in out
    assert "<children>" not in out
