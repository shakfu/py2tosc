"""Malformed and minimal input.

py2tosc reads files written by other tools and by older versions of itself, so
degrading gracefully matters more than rejecting early.
"""

import zlib

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
    with pytest.raises(py2tosc.FormatError, match="not valid XML"):
        py2tosc.loads("this is not a layout")


def test_truncated_compressed_data(tmp_path):
    path = tmp_path / "broken.tosc"
    path.write_bytes(b"\x78\x9c" + b"garbage")
    with pytest.raises(py2tosc.FormatError, match="not a readable .tosc stream"):
        py2tosc.load(path)


def test_every_way_of_being_unreadable_is_one_catchable_type():
    """The point of `FormatError`: one `except` for "that file is not a layout".

    These five failures used to reach the caller as `ParseError`, `zlib.error`
    and `ValueError` -- three types from three modules, only one of them ours.
    A caller wanting to report a bad file had to catch `Exception`, which is
    what the two tests above did before this existed.
    """
    broken = [
        "this is not a layout",
        "<nope/>",
        "<lexml version='6'></lexml>",
        "<lexml version='6'><node ID='a' type='SPACESHIP'/></lexml>",
        "<lexml version='6'><node ID='a' type='GROUP'><messages>"
        "<telepathy><enabled>1</enabled></telepathy></messages></node></lexml>",
    ]
    for source in broken:
        with pytest.raises(py2tosc.FormatError):
            py2tosc.loads(source)

    compressed = zlib.compressobj().compress(b"not xml") + b"truncated"
    with pytest.raises(py2tosc.FormatError):
        py2tosc.loads(b"\x78\x9c" + compressed)


def test_a_format_error_is_still_a_value_error():
    """`load` and `loads` documented `ValueError` before `FormatError` existed.

    Narrowing to a subclass keeps that promise, so code written against the
    older contract keeps working rather than silently stopping catching.
    """
    assert issubclass(py2tosc.FormatError, ValueError)
    with pytest.raises(ValueError):
        py2tosc.loads("this is not a layout")


def test_everything_the_package_raises_shares_a_base():
    assert issubclass(py2tosc.FormatError, py2tosc.Py2toscError)
    assert issubclass(py2tosc.ValidationError, py2tosc.Py2toscError)


def test_minimal_document_round_trips():
    doc = py2tosc.loads(MINIMAL)
    assert py2tosc.loads(doc.dumps()).dumps() == doc.dumps()


def test_empty_containers_are_not_written():
    out = py2tosc.loads(MINIMAL).dumps()
    assert "<values>" not in out
    assert "<messages>" not in out
    assert "<children>" not in out
