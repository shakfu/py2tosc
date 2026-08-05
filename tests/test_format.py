"""Fidelity against files written by TouchOSC 1.5.2.262.

The strongest guarantee this library offers is that reading a layout and writing
it back reproduces the editor's own bytes exactly, in both the compressed
`.tosc` form and the `.xml` export. If that holds, no property, value, message,
element order or CDATA section was lost on the way through.
"""

import zlib

import pytest

import py2tosc
from py2tosc import ControlType


def test_compact_round_trip_is_byte_exact(doc, sample_bytes):
    assert doc.dumps().encode("utf-8") == sample_bytes


def test_pretty_round_trip_is_byte_exact(doc, sample_xml):
    assert doc.dumps(pretty=True).encode("utf-8") == sample_xml


def test_saved_file_round_trips_through_disk(doc, sample_bytes, tmp_path):
    out = tmp_path / "out.tosc"
    doc.save(out)
    assert zlib.decompress(out.read_bytes()) == sample_bytes


def test_xml_extension_selects_the_readable_export(doc, sample_xml, tmp_path):
    out = tmp_path / "out.xml"
    doc.save(out)
    assert out.read_bytes() == sample_xml


def test_both_sample_formats_parse_to_the_same_document(doc, sample_xml_path):
    assert py2tosc.load(sample_xml_path).dumps() == doc.dumps()


def test_version_is_preserved(doc):
    assert doc.version == "6"


def test_includes_element_survives(doc, sample_bytes):
    # <includes> is new in lexml 6 and carries no data py2tosc models, but
    # dropping it would change the file. The byte-exact check above covers it;
    # this pins the intent.
    assert b"<includes>" in sample_bytes
    assert "<includes>" in doc.dumps()


def test_cdata_is_preserved(doc):
    out = doc.dumps()
    assert "<key><![CDATA[background]]></key>" in out
    assert "<value><![CDATA[fader1]]></value>" in out


def test_group_is_parsed(doc):
    root = doc.root
    assert root.control_type is ControlType.GROUP
    assert root.id == "c36776ac-90b0-11f1-990b-f2a3060a23c2"
    assert root.frame == (0, 0, 640, 860)
    assert root.color == (0.0, 0.0, 0.0, 1.0)
    assert len(root.children) == 2


def test_fader_is_parsed(doc):
    fader = doc.find("fader1")
    assert fader.control_type is ControlType.FADER
    assert fader.frame == (77, 60, 50, 200)
    assert fader.color == (1.0, 0.0, 0.0, 1.0)
    assert fader.grid_steps == 13
    assert fader.response_factor == 100
    assert [v.key for v in fader.values] == ["x", "touch"]


def test_label_is_parsed(doc):
    label = doc.find("label1")
    assert label.control_type is ControlType.LABEL
    assert label.text_size == 14
    assert label.text_color == (1.0, 1.0, 1.0, 1.0)
    assert label.value("text").default == "My label"
    assert label.value("text").locked_default_current is True
    assert label.messages == []


def test_connections_are_ten_slots_wide(doc):
    fader = doc.find("fader1")
    assert [m.connections for m in fader.messages] == ["1" * 10, "1" * 10]
    # and a message built from scratch matches the format the editor writes
    assert py2tosc.OscMessage().connections == "1" * 10
    assert py2tosc.MidiMessage().connections == "1" * 10


def test_reading_does_not_mutate(doc):
    before = doc.dumps()
    doc.find("label1").messages
    doc.find("label1").children
    list(doc.walk())
    assert doc.dumps() == before


def test_edits_survive_a_round_trip(doc, tmp_path):
    fader = doc.find("fader1")
    fader.name = "cutoff"
    fader.frame = (10, 20, 30, 40)
    fader.color = "#804020"

    out = tmp_path / "edited.tosc"
    doc.save(out)
    reloaded = py2tosc.load(out)

    edited = reloaded.find("cutoff")
    assert edited.frame == (10, 20, 30, 40)
    assert edited.color == pytest.approx((128 / 255, 64 / 255, 32 / 255, 1.0))
    assert reloaded.find("label1") is not None


def test_loads_accepts_compressed_and_plain(sample_bytes):
    compressed = py2tosc.loads(zlib.compress(sample_bytes))
    plain = py2tosc.loads(sample_bytes)
    assert compressed.dumps() == plain.dumps()


def test_loads_rejects_a_non_lexml_document():
    with pytest.raises(ValueError, match="lexml"):
        py2tosc.loads("<other><node/></other>")
