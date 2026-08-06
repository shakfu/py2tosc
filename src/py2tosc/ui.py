"""Combinators for building messages, above the raw dataclasses.

The message dataclasses mirror the file format, so they say everything and
assume nothing. That is right for a binding to someone else's format and wrong
for writing a layout by hand, where one idea costs four objects and a dozen
positional arguments. These helpers return the same dataclasses, built from a
shorter description.

```python
from py2tosc import ui

fader.messages.append(ui.osc("/synth/{name}"))
fader.messages.append(ui.midi_cc(74))
button.messages.append(ui.connect(readout, source=ui.prop("name"), to="text"))
```

Nothing here adds vocabulary the format lacks, and nothing here can reach a
file that a hand-built `OscMessage` could not. The module is separate from the
core because it encodes opinions about how bindings are best described, and
opinions age faster than a file format does. It is unstable below 1.0.
"""

from __future__ import annotations

from collections.abc import Sequence

from .control import Control
from .enums import Conversion, MidiType, PartialType, TriggerCondition
from .messages import (
    ALL_CONNECTIONS,
    LocalMessage,
    MidiCommand,
    MidiMessage,
    MidiValue,
    OscMessage,
    Partial,
    Trigger,
)

__all__ = [
    "connect",
    "const",
    "index",
    "midi_cc",
    "midi_note",
    "osc",
    "path",
    "prop",
    "value",
]

#: The MIDI channel slot of a MIDI binding, which the corpus writes unchanged
#: whatever channel the message is on: the channel itself lives in the command.
_CHANNEL_SLOT = (0.0, 15.0)

_LOCAL_TARGETS = (str(PartialType.VALUE), str(PartialType.PROPERTY))


def value(
    key: str = "x",
    *,
    conversion: Conversion | str = Conversion.FLOAT,
    scale: tuple[float, float] = (0.0, 1.0),
) -> Partial:
    """A partial reading one of the control's live values.

    Args:
        key: The value to read, usually `x`, `touch` or `text`.
        conversion: The type the value is converted to before sending.
        scale: Low and high ends of the output range.

    Returns:
        A `VALUE` partial.
    """
    return Partial(PartialType.VALUE, conversion, key, scale[0], scale[1])


def const(
    text: str,
    *,
    conversion: Conversion | str = Conversion.STRING,
    scale: tuple[float, float] = (0.0, 1.0),
) -> Partial:
    """A partial carrying fixed text.

    Args:
        text: The text to send.
        conversion: The type the text is converted to before sending.
        scale: Low and high ends of the output range. Irrelevant to an OSC
            address, where the text is the whole of the content, but a MIDI
            slot takes its fixed byte from this range instead.

    Returns:
        A `CONSTANT` partial.
    """
    return Partial(PartialType.CONSTANT, conversion, text, scale[0], scale[1])


def prop(
    key: str,
    *,
    conversion: Conversion | str = Conversion.STRING,
    scale: tuple[float, float] = (0.0, 1.0),
) -> Partial:
    """A partial reading one of the control's properties.

    Args:
        key: The property to read. Dotted lookups reach upwards, as in
            `parent.name`.
        conversion: The type the property is converted to before sending.
        scale: Low and high ends of the output range.

    Returns:
        A `PROPERTY` partial.
    """
    return Partial(PartialType.PROPERTY, conversion, key, scale[0], scale[1])


def index(
    *,
    conversion: Conversion | str = Conversion.INTEGER,
    scale: tuple[float, float] = (1.0, 2.0),
) -> Partial:
    """A partial carrying the control's position within its parent.

    The defaults are the only combination the corpus contains: every one of the
    147 `INDEX` partials in it converts to `INTEGER` over a 1-2 range.

    Args:
        conversion: The type the index is converted to before sending.
        scale: Low and high ends of the output range.

    Returns:
        An `INDEX` partial.
    """
    return Partial(PartialType.INDEX, conversion, "", scale[0], scale[1])


def path(address: str) -> list[Partial]:
    """Expand an address into the partials that build it.

    Braces mark a property lookup, mirroring f-strings, and `{#}` marks the
    control's index:

    ```python
    path("/{parent.name}/{name}")
    ```

    Adjacent literal text coalesces into a single `CONSTANT` partial, which is
    how TouchOSC itself stores an address: a constant run is kept as it was
    typed rather than split on every separator. There is no canonical
    segmentation, though, so this expands an address rather than normalising
    one -- feeding a loaded message's partials back through it will not
    necessarily reproduce them.

    Args:
        address: The address, with `{}` around any property lookup. Write `{{`
            and `}}` for a literal brace.

    Returns:
        The partials, in order, ready for `OscMessage.path`.

    Raises:
        ValueError: If the address is empty, or a brace is unmatched or empty.
    """
    if not address:
        raise ValueError("an OSC address cannot be empty")

    partials: list[Partial] = []
    literal: list[str] = []
    position = 0

    while position < len(address):
        char = address[position]

        # A doubled brace is one literal brace, as in an f-string.
        if char in "{}" and address[position + 1 : position + 2] == char:
            literal.append(char)
            position += 2
            continue

        if char == "}":
            raise ValueError(
                f"unmatched '}}' at {position} in {address!r}; "
                f"write '}}}}' for a literal brace"
            )

        if char == "{":
            end = address.find("}", position + 1)
            key = address[position + 1 : end]
            if end == -1 or "{" in key:
                raise ValueError(
                    f"unmatched '{{' at {position} in {address!r}; "
                    f"write '{{{{' for a literal brace"
                )
            if not key:
                raise ValueError(f"empty '{{}}' at {position} in {address!r}")
            if literal:
                partials.append(const("".join(literal)))
                literal.clear()
            partials.append(index() if key == "#" else prop(key))
            position = end + 1
            continue

        literal.append(char)
        position += 1

    if literal:
        partials.append(const("".join(literal)))
    return partials


def _triggers(
    on: TriggerCondition | str, var: str, triggers: Sequence[Trigger] | None
) -> list[Trigger]:
    return list(triggers) if triggers is not None else [Trigger(var, on)]


def osc(
    address: str = "/{name}",
    *,
    args: Sequence[Partial] | None = None,
    on: TriggerCondition | str = TriggerCondition.ANY,
    var: str = "x",
    triggers: Sequence[Trigger] | None = None,
    enabled: bool = True,
    send: bool = True,
    receive: bool = True,
    feedback: bool = False,
    no_duplicates: bool = False,
    connections: str = ALL_CONNECTIONS,
) -> OscMessage:
    """An OSC binding, addressed by an f-string-like template.

    The defaults match [`OscMessage`][py2tosc.OscMessage]'s: `osc()` sends the
    control's `x` value to `/<control name>` on any change, over every
    connection.

    Args:
        address: The OSC address, in the syntax [`path`][py2tosc.ui.path]
            accepts.
        args: The arguments to send. Defaults to the control's `x` value.
        on: When to fire -- `ANY`, `RISE` or `FALL`.
        var: The value watched by `on`.
        triggers: Trigger objects, overriding `on` and `var` entirely. An empty
            sequence means the message carries no triggers at all.
        enabled: Whether the binding is active.
        send: Whether the control transmits.
        receive: Whether the control accepts incoming messages.
        feedback: Whether received messages are echoed back.
        no_duplicates: Whether to suppress repeated identical messages.
        connections: One character per connection slot, `1` for enabled.

    Returns:
        The binding.

    Raises:
        ValueError: If the address cannot be expanded.
    """
    return OscMessage(
        enabled=enabled,
        send=send,
        receive=receive,
        feedback=feedback,
        no_duplicates=no_duplicates,
        connections=connections,
        triggers=_triggers(on, var, triggers),
        path=path(address),
        arguments=[value("x")] if args is None else list(args),
    )


def _slot(source: Partial) -> MidiValue:
    """Read a MIDI slot off the same partial vocabulary as everything else.

    A `MidiValue` is a `Partial` without the conversion: a MIDI byte is a number
    whatever it was drawn from, so there is nothing left to convert it to.
    """
    return MidiValue(source.type, source.value, source.scale_min, source.scale_max)


def _byte(number: int | Partial, limit: int, what: str) -> tuple[int, MidiValue]:
    """The static byte and the slot that supplies it, for one data byte.

    A fixed byte is written twice, as the command's field and as an `INDEX`
    slot scaled from it, which is what lets a row of controls number itself
    from its position. A byte drawn from a partial leaves the command at zero
    and lets the slot decide, which is how the corpus binds a key's note number
    to its name.
    """
    if not isinstance(number, int):
        return 0, _slot(number)
    if not 0 <= number <= limit:
        raise ValueError(f"{number} is out of the 0-{limit} MIDI {what} range")
    return number, MidiValue(PartialType.INDEX, "", number, number + 1)


def _midi(
    command: MidiType,
    data1: int | Partial,
    channel: int | Partial,
    scale: tuple[float, float],
    source: Partial | str,
    on: TriggerCondition | str,
    var: str,
    triggers: Sequence[Trigger] | None,
    enabled: bool,
    send: bool,
    receive: bool,
    feedback: bool,
    no_duplicates: bool,
    connections: str,
) -> MidiMessage:
    number, data_slot = _byte(data1, 127, "data")

    # The channel slot keeps its 0-15 range whatever channel the message is on,
    # because a fixed channel lives in the command rather than in the slot.
    if isinstance(channel, int):
        if not 0 <= channel <= 15:
            raise ValueError(f"{channel} is out of the 0-15 MIDI channel range")
        channel_number, channel_slot = (
            channel,
            MidiValue(PartialType.CONSTANT, "", *_CHANNEL_SLOT),
        )
    else:
        channel_number, channel_slot = 0, _slot(channel)

    sent = value(source, scale=scale) if isinstance(source, str) else source

    return MidiMessage(
        enabled=enabled,
        send=send,
        receive=receive,
        feedback=feedback,
        no_duplicates=no_duplicates,
        connections=connections,
        triggers=_triggers(on, var, triggers),
        message=MidiCommand(command, channel=channel_number, data1=number),
        # The three slots supply the channel, the first data byte and the
        # second, in that order.
        values=[channel_slot, data_slot, _slot(sent)],
    )


def midi_cc(
    controller: int | Partial,
    *,
    channel: int | Partial = 0,
    scale: tuple[float, float] = (0.0, 127.0),
    source: Partial | str = "x",
    on: TriggerCondition | str = TriggerCondition.ANY,
    var: str = "x",
    triggers: Sequence[Trigger] | None = None,
    enabled: bool = True,
    send: bool = True,
    receive: bool = True,
    feedback: bool = False,
    no_duplicates: bool = False,
    connections: str = ALL_CONNECTIONS,
) -> MidiMessage:
    """A MIDI control change binding.

    Args:
        controller: The CC number, 0-127, or a partial to draw it from.
        channel: The MIDI channel, 0-15, or a partial to draw it from.
        scale: Low and high ends of the range the value is sent over. Applies
            only when `source` is a bare string; a partial carries its own.
        source: The control value driving the message, or a partial.
        on: When to fire -- `ANY`, `RISE` or `FALL`.
        var: The value watched by `on`.
        triggers: Trigger objects, overriding `on` and `var` entirely.
        enabled: Whether the binding is active.
        send: Whether the control transmits.
        receive: Whether the control accepts incoming messages.
        feedback: Whether received messages are echoed back.
        no_duplicates: Whether to suppress repeated identical messages.
        connections: One character per connection slot, `1` for enabled.

    Returns:
        The binding.

    Raises:
        ValueError: If `controller` or `channel` is a number out of range.
    """
    return _midi(
        MidiType.CONTROLCHANGE,
        controller,
        channel,
        scale,
        source,
        on,
        var,
        triggers,
        enabled,
        send,
        receive,
        feedback,
        no_duplicates,
        connections,
    )


def midi_note(
    note: int | Partial,
    *,
    channel: int | Partial = 0,
    scale: tuple[float, float] = (0.0, 127.0),
    source: Partial | str = "x",
    on: TriggerCondition | str = TriggerCondition.ANY,
    var: str = "x",
    triggers: Sequence[Trigger] | None = None,
    enabled: bool = True,
    send: bool = True,
    receive: bool = True,
    feedback: bool = False,
    no_duplicates: bool = False,
    connections: str = ALL_CONNECTIONS,
) -> MidiMessage:
    """A MIDI note-on binding, with the control's value as velocity.

    A whole keyboard of buttons can name its own notes rather than being
    numbered one at a time, which is what the corpus does:

    ```python
    midi_note(prop("name"))
    ```

    Args:
        note: The note number, 0-127, or a partial to draw it from.
        channel: The MIDI channel, 0-15, or a partial to draw it from.
        scale: Low and high ends of the velocity range. Applies only when
            `source` is a bare string; a partial carries its own.
        source: The control value driving the velocity, or a partial.
        on: When to fire -- `ANY`, `RISE` or `FALL`.
        var: The value watched by `on`.
        triggers: Trigger objects, overriding `on` and `var` entirely.
        enabled: Whether the binding is active.
        send: Whether the control transmits.
        receive: Whether the control accepts incoming messages.
        feedback: Whether received messages are echoed back.
        no_duplicates: Whether to suppress repeated identical messages.
        connections: One character per connection slot, `1` for enabled.

    Returns:
        The binding.

    Raises:
        ValueError: If `note` or `channel` is a number out of range.
    """
    return _midi(
        MidiType.NOTE_ON,
        note,
        channel,
        scale,
        source,
        on,
        var,
        triggers,
        enabled,
        send,
        receive,
        feedback,
        no_duplicates,
        connections,
    )


def connect(
    dst: Control | str,
    *,
    source: Partial | str = "x",
    to: Partial | str = "x",
    on: TriggerCondition | str = TriggerCondition.ANY,
    var: str = "x",
    triggers: Sequence[Trigger] | None = None,
    enabled: bool = True,
) -> LocalMessage:
    """A binding to another control in the same layout.

    Both ends are described with the same three constructors used for OSC
    arguments, so `source=prop("name"), to="text"` reads as one idea rather
    than seven keyword arguments:

    ```python
    connect(readout, source=prop("name"), to="text", on="RISE")
    connect(readout, source=const("0"), to=prop("sum"), on="RISE")
    ```

    Args:
        dst: The destination control, or its id. Passing a control reads its
            `id`, so the destination has to exist before the binding is made.
        source: What to send. A bare string names one of this control's values.
        to: What to write on the destination. A bare string names one of its
            values; a [`prop`][py2tosc.ui.prop] partial names a property.
        on: When to fire -- `ANY`, `RISE` or `FALL`.
        var: The value watched by `on`.
        triggers: Trigger objects, overriding `on` and `var` entirely.
        enabled: Whether the binding is active.

    Returns:
        The binding.

    Raises:
        ValueError: If `to` is a partial that names neither a value nor a
            property.
    """
    sent = value(source) if isinstance(source, str) else source
    target = value(to) if isinstance(to, str) else to

    # Loaded messages hold plain strings where a built one holds an enum, so
    # compare the text rather than the member.
    if str(target.type) not in _LOCAL_TARGETS:
        raise ValueError(
            f"a local message can write a value or a property, not {str(target.type)!r}"
        )

    return LocalMessage(
        enabled=enabled,
        triggers=_triggers(on, var, triggers),
        type=sent.type,
        conversion=sent.conversion,
        value=sent.value,
        scale_min=sent.scale_min,
        scale_max=sent.scale_max,
        dst_type=str(target.type),
        dst_var=target.value,
        dst_id=dst if isinstance(dst, str) else dst.id,
    )
