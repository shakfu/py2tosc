"""The message combinators in `py2tosc.ui`.

The combinators are meant to be pure sugar: everything they build could be
written by hand as the raw dataclasses, and nothing they build can put anything
in a file that a hand-built message could not. Most of what follows pins that
claim, either against the dataclass defaults or against shapes taken from the
corpus.
"""

import pytest

import py2tosc
from py2tosc import (
    Conversion,
    LocalMessage,
    MidiMessage,
    OscMessage,
    Partial,
    PartialType,
    Trigger,
    TriggerCondition,
    ui,
)


def shape(partials):
    """The part of a partial list worth comparing: what it says, in order."""
    return [(str(p.type), p.value) for p in partials]


# -- source constructors


def test_source_constructors_fill_the_partial_fields():
    assert ui.value("y", scale=(0, 127)) == Partial("VALUE", "FLOAT", "y", 0, 127)
    assert ui.const("hello") == Partial("CONSTANT", "STRING", "hello", 0, 1)
    assert ui.prop("parent.name") == Partial("PROPERTY", "STRING", "parent.name", 0, 1)


def test_index_defaults_to_the_only_shape_the_corpus_contains():
    """Every INDEX partial in the corpus is INTEGER over 1-2, not STRING over 0-1.

    Guessing from the other three constructors would have got this wrong.
    """
    assert ui.index() == Partial("INDEX", "INTEGER", "", 1, 2)


def test_value_matches_the_default_osc_argument():
    assert [ui.value("x")] == OscMessage().arguments


PARTIALS = [
    lambda **kw: ui.value("x", **kw),
    lambda **kw: ui.const("hello", **kw),
    lambda **kw: ui.prop("name", **kw),
    lambda **kw: ui.index(**kw),
]


@pytest.mark.parametrize("make", PARTIALS)
def test_a_conversion_the_format_has_no_concept_of_is_refused(make):
    """The same constraint as a trigger condition, one layer down.

    A conversion is stored as text, so an unchecked one reaches the file as a
    `<conversion>` TouchOSC has never heard of -- and like a condition, nothing
    after this point looks at it again.
    """
    with pytest.raises(ValueError):
        make(conversion="NOPE")


@pytest.mark.parametrize("make", PARTIALS)
def test_a_conversion_may_be_the_enum_or_its_text(make):
    assert make(conversion=Conversion.BOOLEAN) == make(conversion="BOOLEAN")


# -- addresses


def test_path_reproduces_the_library_default():
    """`osc()` and `OscMessage()` must describe the same address."""
    assert ui.path("/{name}") == OscMessage().path


def test_osc_defaults_match_the_dataclass():
    assert ui.osc() == OscMessage()


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        # The four commonest path shapes in the corpus, and the REAPER one that
        # proves constant runs are stored unsegmented.
        ("/{name}", [("CONSTANT", "/"), ("PROPERTY", "name")]),
        (
            "/{parent.name}/{name}",
            [
                ("CONSTANT", "/"),
                ("PROPERTY", "parent.name"),
                ("CONSTANT", "/"),
                ("PROPERTY", "name"),
            ],
        ),
        (
            "/{parent.name}/{#}",
            [
                ("CONSTANT", "/"),
                ("PROPERTY", "parent.name"),
                ("CONSTANT", "/"),
                ("INDEX", ""),
            ],
        ),
        ("/action/str", [("CONSTANT", "/action/str")]),
        (
            "/channel/track/{parent.parent.name}/fxparam/{parent.name}/{name}",
            [
                ("CONSTANT", "/channel/track/"),
                ("PROPERTY", "parent.parent.name"),
                ("CONSTANT", "/fxparam/"),
                ("PROPERTY", "parent.name"),
                ("CONSTANT", "/"),
                ("PROPERTY", "name"),
            ],
        ),
    ],
)
def test_corpus_address_shapes_expand_exactly(address, expected):
    assert shape(ui.path(address)) == expected


def test_adjacent_literal_text_coalesces():
    """One CONSTANT per run, not one per separator.

    Splitting on every `/` would also be a valid address, but it is not what
    TouchOSC writes, and the point of the syntax is to produce what the editor
    would have.
    """
    assert shape(ui.path("/synth/cutoff/{name}")) == [
        ("CONSTANT", "/synth/cutoff/"),
        ("PROPERTY", "name"),
    ]


def test_doubled_braces_are_literal():
    assert shape(ui.path("/{{raw}}/{name}")) == [
        ("CONSTANT", "/{raw}/"),
        ("PROPERTY", "name"),
    ]


def test_no_empty_constant_between_adjacent_lookups():
    assert shape(ui.path("{a}{b}")) == [("PROPERTY", "a"), ("PROPERTY", "b")]


@pytest.mark.parametrize("address", ["", "/{", "/}", "/{}", "/{a{b}", "{name"])
def test_malformed_addresses_raise(address):
    with pytest.raises(ValueError):
        ui.path(address)


def test_arguments_are_not_shared_between_messages():
    """`Partial` is mutable, so a shared default would alias across messages."""
    first, second = ui.osc(), ui.osc()
    first.arguments[0].value = "y"
    assert second.arguments[0].value == "x"


# -- MIDI


def test_midi_cc_defaults_match_the_dataclass():
    assert ui.midi_cc(0) == MidiMessage()


def test_midi_cc_numbers_the_command_and_the_index_slot_together():
    """The corpus pairs `data1=n` with an INDEX slot scaled `(n, n + 1)`.

    Seen at n=13 and n=29 in the examples, which is what makes a row of
    controls number itself from its position.
    """
    message = ui.midi_cc(13)
    assert (message.message.type, message.message.data1) == ("CONTROLCHANGE", 13)
    assert (message.values[1].scale_min, message.values[1].scale_max) == (13, 14)


def test_midi_channel_lives_in_the_command_not_the_slot():
    """Every corpus MIDI message keeps slot one at 0-15 whatever the channel."""
    message = ui.midi_cc(0, channel=7)
    assert message.message.channel == 7
    assert (message.values[0].scale_min, message.values[0].scale_max) == (0, 15)


def test_midi_note_sends_note_on_with_the_value_as_velocity():
    message = ui.midi_note(60, scale=(0, 100), source="y")
    assert (message.message.type, message.message.data1) == ("NOTE_ON", 60)
    assert message.values[2] == py2tosc.MidiValue("VALUE", "y", 0, 100)


@pytest.mark.parametrize(
    ("kwargs", "bad"),
    [({}, 128), ({}, -1), ({"channel": 16}, 0), ({"channel": -1}, 0)],
)
def test_midi_ranges_are_checked(kwargs, bad):
    with pytest.raises(ValueError):
        ui.midi_cc(bad, **kwargs)


def midi_shape(message):
    """A MIDI binding reduced to the parts the corpus can be compared against."""
    command = message.message
    return (
        (str(command.type), command.channel, command.data1, command.data2),
        tuple((str(v.type), v.key, v.scale_min, v.scale_max) for v in message.values),
    )


@pytest.mark.parametrize(
    ("built", "expected"),
    [
        # Each of these is a MIDI shape counted in the corpus, reproduced from
        # the combinator that is meant to express it.
        (
            lambda: ui.midi_note(ui.prop("name")),
            (
                ("NOTE_ON", 0, 0, 0),
                (
                    ("CONSTANT", "", 0, 15),
                    ("PROPERTY", "name", 0, 1),
                    ("VALUE", "x", 0, 127),
                ),
            ),
        ),
        (
            lambda: ui.midi_note(ui.prop("name"), channel=ui.prop("tag")),
            (
                ("NOTE_ON", 0, 0, 0),
                (
                    ("PROPERTY", "tag", 0, 1),
                    ("PROPERTY", "name", 0, 1),
                    ("VALUE", "x", 0, 127),
                ),
            ),
        ),
        (
            lambda: ui.midi_cc(5, source=ui.const("", scale=(0, 127))),
            (
                ("CONTROLCHANGE", 0, 5, 0),
                (
                    ("CONSTANT", "", 0, 15),
                    ("INDEX", "", 5, 6),
                    ("CONSTANT", "", 0, 127),
                ),
            ),
        ),
    ],
)
def test_corpus_midi_shapes_are_reachable(built, expected):
    """A keyboard naming its own notes, a channel from `tag`, a constant slot.

    All three occur in the examples, and none of them is expressible by a
    combinator that takes only numbers.
    """
    assert midi_shape(built()) == expected


def test_a_byte_drawn_from_a_partial_leaves_the_command_at_zero():
    """The corpus writes `data1=0` when the slot decides the byte."""
    assert ui.midi_note(ui.prop("name")).message.data1 == 0
    assert ui.midi_note(60, channel=ui.prop("tag")).message.channel == 0


def test_a_sourced_byte_skips_the_range_check():
    """Range checking applies to a number, and a partial is not one."""
    assert ui.midi_cc(ui.prop("tag")) is not None


def test_const_and_prop_carry_a_scale():
    """A MIDI slot takes its byte from the scale, so all four sources need one."""
    assert ui.const("", scale=(0, 127)).scale_max == 127
    assert ui.prop("tag", scale=(0, 15)).scale_max == 15


# -- local wiring


def test_connect_defaults_to_wiring_x_to_x():
    message = ui.connect("abc")
    assert message == LocalMessage(
        type="VALUE",
        conversion="FLOAT",
        value="x",
        dst_type="VALUE",
        dst_var="x",
        dst_id="abc",
    )


def test_connect_reads_the_id_of_a_control():
    readout = py2tosc.label(name="readout")
    assert ui.connect(readout).dst_id == readout.id


def test_connect_writes_a_partial_type_not_a_conversion():
    """`dst_type` says what kind of thing is written, not what it converts to.

    The messages guide taught `dst_type="FLOAT"` until this was written, which
    is a `Conversion` value in a `PartialType` field. Nothing catches it: the
    field is annotated as a bare `str` and `validate` has no rule for it.
    """
    assert ui.connect("abc", to="text").dst_type == "VALUE"
    assert ui.connect("abc", to=ui.prop("sum")).dst_type == "PROPERTY"
    assert {m.dst_type for m in _numpad_messages()} <= {"VALUE", "PROPERTY"}


@pytest.mark.parametrize("target", [ui.const("0"), ui.index()])
def test_connect_rejects_a_target_that_is_neither_a_value_nor_a_property(target):
    with pytest.raises(ValueError, match="value or a property"):
        ui.connect("abc", to=target)


def test_connect_accepts_partials_that_hold_strings_rather_than_enums():
    """A loaded message holds plain strings, since the codec never coerces.

    A combinator that compared against enum members would work on a built
    layout and fail on an edited one.
    """
    target = Partial(type="PROPERTY", conversion="STRING", value="sum")
    assert ui.connect("abc", to=target).dst_type == "PROPERTY"


def test_connect_carries_the_source_partial_across_whole():
    message = ui.connect("abc", source=ui.value("y", scale=(0, 127)))
    assert (message.type, message.conversion, message.value) == ("VALUE", "FLOAT", "y")
    assert (message.scale_min, message.scale_max) == (0, 127)


# -- triggers, shared by all three


MAKERS = [
    ui.osc,
    lambda **kw: ui.midi_cc(0, **kw),
    lambda **kw: ui.connect("abc", **kw),
]


@pytest.mark.parametrize("make", MAKERS)
def test_on_and_var_build_one_trigger(make):
    assert make(on="RISE", var="touch").triggers == [Trigger("touch", "RISE")]


@pytest.mark.parametrize("make", MAKERS)
def test_triggers_override_on_and_var(make):
    assert make(on="RISE", triggers=[]).triggers == []


@pytest.mark.parametrize("make", MAKERS)
def test_a_condition_the_format_has_no_concept_of_is_refused(make):
    """The one place a helper could write vocabulary the format lacks.

    A condition is passed through as text, so an unchecked one reaches the
    file as a `<condition>` TouchOSC has never heard of -- and nothing after
    this point looks at it: the codec writes what it is given, and `validate`
    has no rule for it. Refusing here is the only chance.
    """
    with pytest.raises(ValueError):
        make(on="NOPE")


@pytest.mark.parametrize("make", MAKERS)
def test_a_condition_may_be_the_enum_or_its_text(make):
    assert make(on=TriggerCondition.FALL).triggers == make(on="FALL").triggers


def test_a_message_with_no_triggers_omits_the_element():
    """The codec drops an empty `<triggers>`, matching 4817 corpus messages."""
    fader = py2tosc.fader(messages=[ui.osc(triggers=[])])
    assert "<triggers>" not in py2tosc.Document(root=fader).dumps()


# -- end to end


def _numpad_messages():
    return [
        message
        for control in _numpad().walk()
        for message in control.messages
        if isinstance(message, LocalMessage)
    ]


def _numpad():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent / "demos"))
    import numpad

    return numpad.build().root


def test_combinator_messages_survive_a_round_trip():
    """Whatever the helpers build has to be ordinary enough to save and reload."""
    fader = py2tosc.fader(
        name="cutoff",
        messages=[
            ui.osc("/synth/{parent.name}/{name}", args=[ui.value("x", scale=(0, 127))]),
            ui.midi_cc(74, channel=3),
            ui.connect("abc", source=ui.prop("name"), to=ui.prop("sum"), on="RISE"),
        ],
    )
    doc = py2tosc.Document(root=py2tosc.group(children=[fader]))
    reloaded = py2tosc.loads(doc.dumps()).find("cutoff")

    assert [type(m) for m in reloaded.messages] == [
        OscMessage,
        MidiMessage,
        LocalMessage,
    ]
    assert shape(reloaded.messages[0].path) == shape(fader.messages[0].path)
    assert reloaded.messages[1].message.data1 == 74
    assert reloaded.messages[2].dst_type == "PROPERTY"


def test_the_helpers_use_only_vocabulary_the_format_defines():
    """Every enum-typed field must hold a value the enums declare.

    The constraint the whole layer is under: helpers must not write anything
    into a file that TouchOSC has no concept of.
    """
    message = ui.osc("/{parent.name}/{#}")
    for partial in message.path + message.arguments:
        assert PartialType(str(partial.type))
        assert Conversion(str(partial.conversion))
