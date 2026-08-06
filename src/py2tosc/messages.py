"""Values and messages: what a control holds and what it sends.

A control's *values* are its live state (`x`, `touch`, `text`). Its *messages*
describe what leaves the control when that state changes -- over OSC, over MIDI,
or to another control in the same layout.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import Conversion, MidiType, PartialType, TriggerCondition

__all__ = [
    "ALL_CONNECTIONS",
    "ALL_GAMEPADS",
    "GamepadMessage",
    "LocalMessage",
    "Message",
    "MidiCommand",
    "MidiMessage",
    "MidiValue",
    "OscMessage",
    "Partial",
    "Trigger",
    "Value",
]

#: Every network connection enabled. TouchOSC 1.5 exposes ten.
ALL_CONNECTIONS = "1" * 10

#: Every gamepad enabled. Gamepads have their own, narrower field: TouchOSC 1.5
#: writes four slots, not ten. Confirmed by the editor rewriting a ten-slot
#: value down to four on save.
ALL_GAMEPADS = "1" * 4


@dataclass
class Value:
    """One entry of a control's `<values>`: its live state.

    Args:
        key: `x`, `y`, `touch`, `text` or `page`, depending on the control.
        locked: Whether the value is locked against user interaction.
        locked_default_current: Whether the lock holds the current value rather
            than the default.
        default: The value the control starts at.
        default_pull: How strongly the value returns to its default, 0 to 100.
    """

    key: str = "touch"
    locked: bool = False
    locked_default_current: bool = False
    default: bool | float | str = False
    default_pull: int = 0


@dataclass
class Trigger:
    """A condition under which a message is sent.

    Args:
        var: The value that is watched, usually `x` or `touch`.
        condition: Whether to fire on any change, or only on a rise or fall.
    """

    var: str = "x"
    condition: TriggerCondition | str = TriggerCondition.ANY


@dataclass
class Partial:
    """One segment of an OSC address or one OSC argument.

    An address like `/synth/cutoff` is built from partials: a `CONSTANT` `/`,
    then a `PROPERTY` naming the control, and so on.

    Args:
        type: Where the segment's content comes from.
        conversion: The type the segment is converted to before sending.
        value: The constant text, property key or value key, depending on `type`.
        scale_min: Low end of the output range, for `VALUE` partials.
        scale_max: High end of the output range, for `VALUE` partials.
    """

    type: PartialType | str = PartialType.CONSTANT
    conversion: Conversion | str = Conversion.STRING
    value: str = "/"
    scale_min: float = 0
    scale_max: float = 1


@dataclass
class MidiCommand:
    """The `<message>` inside a MIDI binding: the status bytes to send.

    Args:
        type: The MIDI status byte.
        channel: MIDI channel, 0-15.
        data1: First data byte, for example the CC number.
        data2: Second data byte.
    """

    type: MidiType | str = MidiType.CONTROLCHANGE
    channel: int = 0
    data1: int = 0
    data2: int = 0


@dataclass
class MidiValue:
    """One of the three slots a MIDI message draws its bytes from.

    Args:
        type: `CONSTANT`, `INDEX`, `VALUE` or `PROPERTY`.
        key: The value or property key, when `type` needs one.
        scale_min: Low end of the output range.
        scale_max: High end of the output range.
    """

    type: PartialType | str = PartialType.CONSTANT
    key: str = ""
    scale_min: float = 0
    scale_max: float = 15


def _default_triggers() -> list[Trigger]:
    return [Trigger()]


def _default_path() -> list[Partial]:
    return [
        Partial(PartialType.CONSTANT, Conversion.STRING, "/"),
        Partial(PartialType.PROPERTY, Conversion.STRING, "name"),
    ]


def _default_arguments() -> list[Partial]:
    return [Partial(PartialType.VALUE, Conversion.FLOAT, "x")]


def _default_midi_values() -> list[MidiValue]:
    return [
        MidiValue(PartialType.CONSTANT, "", 0, 15),
        MidiValue(PartialType.INDEX, "", 0, 1),
        MidiValue(PartialType.VALUE, "x", 0, 127),
    ]


@dataclass
class OscMessage:
    """An OSC binding.

    The default sends the control's `x` value to `/<control name>` on every
    change, over every connection.

    Args:
        enabled: Whether the binding is active.
        send: Whether the control transmits.
        receive: Whether the control accepts incoming messages.
        feedback: Whether received messages are echoed back.
        no_duplicates: Whether to suppress repeated identical messages.
        connections: One character per connection slot, `1` for enabled.
        triggers: What causes the message to be sent.
        path: The partials that build the OSC address.
        arguments: The partials that build the OSC arguments.
    """

    enabled: bool = True
    send: bool = True
    receive: bool = True
    feedback: bool = False
    no_duplicates: bool = False
    connections: str = ALL_CONNECTIONS
    triggers: list[Trigger] = field(default_factory=_default_triggers)
    path: list[Partial] = field(default_factory=_default_path)
    arguments: list[Partial] = field(default_factory=_default_arguments)


@dataclass
class MidiMessage:
    """A MIDI binding.

    The default sends the control's `x` value as CC 0 on channel 0, scaled to
    0-127.

    Args:
        enabled: Whether the binding is active.
        send: Whether the control transmits.
        receive: Whether the control accepts incoming messages.
        feedback: Whether received messages are echoed back.
        no_duplicates: Whether to suppress repeated identical messages.
        connections: One character per connection slot, `1` for enabled.
        triggers: What causes the message to be sent.
        message: The status bytes to send.
        values: The three slots the data bytes are drawn from.
    """

    enabled: bool = True
    send: bool = True
    receive: bool = True
    feedback: bool = False
    no_duplicates: bool = False
    connections: str = ALL_CONNECTIONS
    triggers: list[Trigger] = field(default_factory=_default_triggers)
    message: MidiCommand = field(default_factory=MidiCommand)
    values: list[MidiValue] = field(default_factory=_default_midi_values)


@dataclass
class GamepadMessage:
    """A binding to a game controller button or axis.

    Unlike the other three, a gamepad binding is one-directional and carries no
    triggers: the controller drives the control, so there is nothing to send.

    Args:
        enabled: Whether the binding is active.
        connections: One character per gamepad slot, `1` for enabled. This
            field is four wide, unlike the ten of an OSC or MIDI binding.
        type: The button or axis, for example `BUTTON_A` or `AXIS_LEFT_X`.
        conversion: The type the input is converted to.
        scale_min: Low end of the output range.
        scale_max: High end of the output range.
        target_type: Whether the input drives a value or a property.
        target_var: The value or property to write on this control.
    """

    enabled: bool = True
    connections: str = ALL_GAMEPADS
    type: str = "BUTTON_A"
    conversion: Conversion | str = Conversion.FLOAT
    scale_min: float = 0
    scale_max: float = 1
    target_type: PartialType | str = PartialType.VALUE
    target_var: str = "x"


@dataclass
class LocalMessage:
    """A binding to another control in the same layout.

    Args:
        enabled: Whether the binding is active.
        triggers: What causes the message to be sent.
        type: Where the sent content comes from.
        conversion: The type the content is converted to.
        value: The value or property key to read.
        scale_min: Low end of the output range.
        scale_max: High end of the output range.
        dst_type: The type expected by the destination.
        dst_var: The value or property to write on the destination.
        dst_id: The `id` of the destination control.
    """

    enabled: bool = True
    triggers: list[Trigger] = field(default_factory=_default_triggers)
    type: PartialType | str = PartialType.VALUE
    conversion: Conversion | str = Conversion.FLOAT
    value: str = "x"
    scale_min: float = 0
    scale_max: float = 1
    dst_type: str = ""
    dst_var: str = ""
    dst_id: str = ""


Message = OscMessage | MidiMessage | LocalMessage | GamepadMessage
"""Any binding type a control can carry."""
