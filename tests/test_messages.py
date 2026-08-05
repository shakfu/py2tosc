"""Message serialization.

Three of these are regression tests for defects in 0.3.x, where the XML builder
rebound its parent element inside a nested loop and read a leaked loop variable.
The result was that a control with two messages nested the second inside the
first, and MIDI bindings were written with a trigger's fields in place of the
status bytes.
"""

import re

import py2tosc
from py2tosc import LocalMessage, MidiCommand, MidiMessage, MidiValue, OscMessage


def render(control: py2tosc.Control) -> str:
    return py2tosc.Document(root=control).dumps(pretty=True)


def test_two_messages_are_siblings_not_nested():
    f = py2tosc.fader(name="a")
    f.messages += [OscMessage(), MidiMessage()]
    out = render(f)

    assert out.count("<osc>") == 1
    assert out.count("<midi>") == 1
    # the <midi> must open after the <osc> has closed
    assert out.index("</osc>") < out.index("<midi>")


def test_many_messages_all_survive():
    f = py2tosc.fader()
    f.messages += [OscMessage(), OscMessage(), OscMessage()]
    assert render(f).count("<osc>") == 3


def test_midi_message_carries_status_bytes():
    f = py2tosc.fader()
    f.messages.append(MidiMessage(message=MidiCommand("CONTROLCHANGE", 3, 74, 0)))
    block = re.search(r"<message>.*?</message>", render(f), re.S).group()

    assert "<type>CONTROLCHANGE</type>" in block
    assert "<channel>3</channel>" in block
    assert "<data1>74</data1>" in block
    assert "<data2>0</data2>" in block
    assert "<var>" not in block and "<condition>" not in block


def test_midi_values_use_the_value_tag():
    f = py2tosc.fader()
    f.messages.append(MidiMessage())
    out = render(f)

    assert "<midivalue>" not in out
    assert [t for t in re.findall(r"<type>(\w+)</type>", out)] == [
        "CONTROLCHANGE",
        "CONSTANT",
        "INDEX",
        "VALUE",
    ]


def test_midi_defaults_match_the_editor():
    values = MidiMessage().values
    assert [v.type for v in values] == ["CONSTANT", "INDEX", "VALUE"]
    assert values[-1].key == "x"
    assert values[-1].scale_max == 127


def test_osc_path_and_arguments():
    f = py2tosc.fader()
    f.messages.append(OscMessage())
    out = render(f)

    path = re.search(r"<path>.*?</path>", out, re.S).group()
    assert "<value><![CDATA[/]]></value>" in path
    assert "<value><![CDATA[name]]></value>" in path

    args = re.search(r"<arguments>.*?</arguments>", out, re.S).group()
    assert "<conversion>FLOAT</conversion>" in args


def test_local_message_field_order():
    f = py2tosc.fader()
    f.messages.append(LocalMessage(dst_var="x", dst_id="abc", dst_type="FLOAT"))
    block = re.search(r"<local>.*?</local>", render(f), re.S).group()
    tags = re.findall(r"<(\w+)>", block)

    assert tags[:2] == ["local", "enabled"]
    assert tags[-3:] == ["dstType", "dstVar", "dstID"]


def test_messages_round_trip():
    f = py2tosc.fader(name="a")
    f.messages += [
        OscMessage(feedback=True, no_duplicates=True, connections="1010101010"),
        MidiMessage(message=MidiCommand("NOTE_ON", 2, 60, 100), values=[MidiValue("VALUE", "x", 0, 127)]),
        LocalMessage(dst_var="text", dst_id="node-42"),
    ]

    doc = py2tosc.Document(root=f)
    reloaded = py2tosc.loads(doc.dumps())

    assert reloaded.dumps() == doc.dumps()
    osc, midi, local = reloaded.root.messages
    assert isinstance(osc, OscMessage) and osc.feedback is True and osc.no_duplicates is True
    assert osc.connections == "1010101010"
    assert isinstance(midi, MidiMessage) and midi.message.data1 == 60
    assert isinstance(local, LocalMessage) and local.dst_id == "node-42"
