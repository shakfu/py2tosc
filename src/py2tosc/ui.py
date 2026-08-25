"""Combinators for messages and layout, above the raw dataclasses.

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

The layout combinators take the same view of `py2tosc.layout`, which sizes
children as it creates them and so has to be driven outside in. These describe
an arrangement and assign frames later, which lets one be written inside out:

```python
panel = ui.column(
    ui.row(readout, send),
    ui.tiles(*keys, columns=3, gap=4),
    sizes=(1, 3),
    frame=(0, 0, 500, 800),
)
ui.resolve(panel)
```

Nothing here adds vocabulary the format lacks, and nothing here can reach a
file that a hand-built `OscMessage` could not -- the arrangement rides on a
private attribute the codec cannot see. The module is separate from the core
because it encodes opinions about how interfaces are best composed, and
opinions age faster than a file format does.

This module is provisional. Unlike the rest of the public API it may change in
a minor release, and the stability policy in `docs/stability.md` says so
explicitly rather than leaving it to a version number. Everything it builds is
an ordinary `Control` or message, so the escape route is always to write the
dataclasses directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ._geometry import (
    CELLS,
    COLUMN,
    PAGES,
    ROW,
    STACK,
    TILES,
    Layout,
    to_gap,
    to_inset,
    to_pad,
)
from ._geometry import resolve as _resolve
from .control import Control
from .enums import ControlType, Conversion, MidiType, PartialType, TriggerCondition
from .messages import (
    ALL_CONNECTIONS,
    LocalMessage,
    MidiCommand,
    MidiMessage,
    MidiValue,
    OscMessage,
    Partial,
    Trigger,
    Value,
)

__all__ = [
    "column",
    "connect",
    "const",
    "grid",
    "index",
    "inset",
    "labelled",
    "midi_cc",
    "midi_note",
    "osc",
    "pager",
    "path",
    "prop",
    "resolve",
    "row",
    "stack",
    "tiles",
    "value",
]

#: The MIDI channel slot of a MIDI binding, which the corpus writes unchanged
#: whatever channel the message is on: the channel itself lives in the command.
_CHANNEL_SLOT = (0.0, 15.0)

_LOCAL_TARGETS = (str(PartialType.VALUE), str(PartialType.PROPERTY))

#: How a page styles its own tab. These belong to the page rather than to the
#: pager, and no control type declares them: a group is only a page when a
#: pager holds it, so nothing about the type can know. They are not merely
#: cosmetic either -- left unset, the label is drawn in no colour at all and
#: the tab comes out blank. The values are what the corpus agrees on across
#: roughly a thousand pages.
#:
#: Only keys no type defaults are listed here, so filling them in can never
#: overwrite a caller's choice. The editor also makes its pages
#: non-interactive and un-outlined, near enough unanimously, but a group
#: already defaults both the other way and there is no telling an untouched
#: default from a deliberate one -- so that convention is documented rather
#: than imposed.
_PAGE_TAB_STYLE = {
    "tabColorOff": (0.25, 0.25, 0.25, 1.0),
    "tabColorOn": (0.5, 0.5, 0.5, 1.0),
    "textColorOff": (1.0, 1.0, 1.0, 1.0),
    "textColorOn": (1.0, 1.0, 1.0, 1.0),
}


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

    Raises:
        ValueError: If `conversion` is not one the format defines.
    """
    return Partial(PartialType.VALUE, Conversion(conversion), key, scale[0], scale[1])


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

    Raises:
        ValueError: If `conversion` is not one the format defines.
    """
    return Partial(
        PartialType.CONSTANT, Conversion(conversion), text, scale[0], scale[1]
    )


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

    Raises:
        ValueError: If `conversion` is not one the format defines.
    """
    return Partial(
        PartialType.PROPERTY, Conversion(conversion), key, scale[0], scale[1]
    )


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

    Raises:
        ValueError: If `conversion` is not one the format defines.
    """
    return Partial(PartialType.INDEX, Conversion(conversion), "", scale[0], scale[1])


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
    if triggers is not None:
        return list(triggers)
    # A string is legitimate -- a loaded message holds one where a built one
    # holds the enum -- but only a string the format knows. An unchecked one
    # reaches the file as a condition TouchOSC has never heard of, and nothing
    # downstream looks at it again: not the codec, which writes what it is
    # given, and not `validate`, which has no rule for it.
    return [Trigger(var, TriggerCondition(on))]


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


# -- layout ------------------------------------------------------------------


def _arranged(
    spec: Layout,
    children: Sequence[Control],
    props: dict[str, Any],
    control_type: ControlType = ControlType.GROUP,
) -> Control:
    group = Control(control_type, children=list(children), **props)
    group._layout = spec
    return group


def row(
    *children: Control,
    sizes: int | Sequence[float] | None = None,
    gap: float | Sequence[float] = 0,
    pad: float | Sequence[float] = 0,
    **props: Any,
) -> Control:
    """Arrange controls left to right inside a group.

    The group is returned rather than the children, so the result goes wherever
    a control goes and layouts nest by ordinary composition:

    ```python
    row(column(meter, label), fader, sizes=(1, 3))
    ```

    No frames are assigned here. The arrangement is recorded and applied by
    [`resolve`][py2tosc.ui.resolve] once the frame at the top is known, which is
    what lets a layout be described from the inside out.

    Args:
        *children: The controls to arrange, in order.
        sizes: Relative widths, one per child. Omitted, they share equally.
        gap: Space between children, in pixels.
        pad: Inset around the whole row -- a number, a `(horizontal, vertical)`
            pair, or `(left, top, right, bottom)`.
        **props: Properties to set on the group, such as `name` or `color`.

    Returns:
        A `GROUP` holding the children, waiting to be resolved.
    """
    return _arranged(
        Layout(ROW, sizes=sizes, gap=to_gap(gap), pad=to_pad(pad)), children, props
    )


def column(
    *children: Control,
    sizes: int | Sequence[float] | None = None,
    gap: float | Sequence[float] = 0,
    pad: float | Sequence[float] = 0,
    **props: Any,
) -> Control:
    """Arrange controls top to bottom inside a group.

    Args:
        *children: The controls to arrange, in order.
        sizes: Relative heights, one per child. Omitted, they share equally.
        gap: Space between children, in pixels.
        pad: Inset around the whole column.
        **props: Properties to set on the group.

    Returns:
        A `GROUP` holding the children, waiting to be resolved.
    """
    return _arranged(
        Layout(COLUMN, sizes=sizes, gap=to_gap(gap), pad=to_pad(pad)), children, props
    )


def tiles(
    *children: Control,
    columns: int = 4,
    rows: int | None = None,
    gap: float | Sequence[float] = 0,
    pad: float | Sequence[float] = 0,
    **props: Any,
) -> Control:
    """Tile controls in a grid, filling row by row.

    Args:
        *children: The controls to arrange, in row-major order.
        columns: How many columns.
        rows: How many rows, or `None` to take just enough for the children.
        gap: Space between cells, in pixels.
        pad: Inset around the whole grid.
        **props: Properties to set on the group.

    Returns:
        A `GROUP` holding the children, waiting to be resolved.

    Raises:
        ValueError: If `columns`, or `rows` when it is given, is less than
            one. Checked here rather than left to the geometry, which divides
            by both and would otherwise fail at `resolve` with a
            `ZeroDivisionError` a long way from the call that caused it.
    """
    if columns < 1:
        raise ValueError(f"tiles needs at least one column, asked for {columns}")
    if rows is not None and rows < 1:
        raise ValueError(f"tiles needs at least one row, asked for {rows}")

    return _arranged(
        Layout(TILES, columns=columns, rows=rows, gap=to_gap(gap), pad=to_pad(pad)),
        children,
        props,
    )


def stack(
    *children: Control,
    pad: float | Sequence[float] = 0,
    **props: Any,
) -> Control:
    """Overlay controls, each filling the group.

    A label sitting on a button is the commonest idiom in TouchOSC and the one
    the eager layout functions cannot express at all, since they divide a frame
    rather than share it. The last child is on top.

    Args:
        *children: The controls to overlay, back to front.
        pad: Inset applied to every child.
        **props: Properties to set on the group.

    Returns:
        A `GROUP` holding the children, waiting to be resolved.
    """
    return _arranged(Layout(STACK, pad=to_pad(pad)), children, props)


def resolve(control: Control, frame: Sequence[float] | None = None) -> Control:
    """Assign frames to everything the layout combinators described.

    Placement runs top down, because a layout can only divide a frame it knows.
    A parent decides its children's frames outright: a control inside a layout
    does not keep a frame it was built with. To place something by hand, leave
    it out of a layout group, or put it in a [`stack`][py2tosc.ui.stack].

    [`Document.resolve`][py2tosc.Document.resolve] calls this against the root.

    Args:
        control: The control to place, along with everything beneath it.
        frame: The frame to give `control`. Omitted, it keeps the one it has.

    Returns:
        `control`, placed.

    Raises:
        ValueError: If a layout cannot fit its children into the space it has,
            or if `sizes` does not match the number of children.
    """
    return _resolve(control, frame)


# -- idioms ------------------------------------------------------------------


def inset(control: Control, amount: float | Sequence[float]) -> Control:
    """Shrink a control within the frame its layout gives it.

    Padding is in pixels, which is no use for anything proportional in a
    deferred layout: the size to take a fraction of is not known until the
    frame comes down from above. An inset is a fraction, applied then.

    Unlike a group's `pad`, this belongs to one control, so a `stack` can inset
    its label without insetting the button underneath -- which is what the
    caption on a key needs, and the one thing `pad` cannot say.

    ```python
    stack(button, inset(caption, 0.1))
    ```

    Args:
        control: The control to inset. It is modified and returned, so this
            reads as a wrapper without building a group to be one.
        amount: A fraction of the frame -- a number, a
            `(horizontal, vertical)` pair, or `(left, top, right, bottom)`.

    Returns:
        `control`.
    """
    control._inset = to_inset(amount)
    return control


def labelled(
    control: Control,
    text: str,
    *,
    size: float = 48,
    inset: float | Sequence[float] = 0.0,
    **props: Any,
) -> Control:
    """A control with a caption laid over it.

    The label is not interactive and has no background, so the control beneath
    receives the touch and shows through. It takes the control's colour and its
    name is the caption, which is what a local message sends when the control
    is pressed.

    Args:
        control: The control to caption.
        text: The caption, which is also the label's name.
        size: Text size.
        inset: A fraction of the frame to inset the caption by, for padding.
            The control underneath is not inset.
        **props: Properties to set on the group holding the two.

    Returns:
        A `GROUP` holding the control and its caption, waiting to be resolved.
    """
    caption = Control(
        ControlType.LABEL,
        name=text,
        color=control.color,
        background=False,
        interactive=False,
        text_size=size,
        values=[Value("text", default=text), Value("touch", default=False)],
    )
    if inset:
        caption._inset = to_inset(inset)
    return stack(control, caption, **props)


def pager(
    *pages: Control,
    pad: float | Sequence[float] = 0,
    **props: Any,
) -> Control:
    """Stack groups as the pages of a `PAGER`.

    A pager shows one page at a time and switches between them itself, so every
    page gets the same frame -- the arrangement [`stack`][py2tosc.ui.stack]
    makes, on a `PAGER` rather than a `GROUP`, and minus the tab bar. A page
    sized to the whole pager would sit underneath the tabs, so `resolve` reads
    the pager's own `tabbar`, `tabbar_size` and `orientation` and reserves that
    much from whichever edge the bar is on. With `tabbar` off a page fills the
    pager exactly, which is what most of the corpus does.

    Pages should be groups, which the other combinators already return:

    ```python
    pager(row(a, b, name="1"), grid(*keys, name="2"))
    ```

    The tab a page is reached by shows its `tab_label`, which is a different
    property from its `name`. A page with a name and no label of its own is
    given its name, since a pager whose tabs are all blank is not usable; set
    `tab_label` on the page to say something else.

    A page also styles its own tab, through `tab_color_on`, `tab_color_off`,
    `text_color_on` and `text_color_off`. Those belong to the page rather than
    to the pager, so no control type declares them as defaults, and a page left
    without them draws its label in no colour at all -- a tab bar with nothing
    written on it. Any it does not already carry are filled in with the values
    the corpus agrees on. The editor also makes its pages non-interactive and
    un-outlined; a group defaults both the other way, and since an untouched
    default cannot be told from a deliberate one, that is left to you.

    A pager must not be the document root. TouchOSC treats the root as the
    canvas and gives it none of its type's behaviour, so a `PAGER` there draws
    a tab bar and then stacks every page instead of paging between them. Put it
    inside a group. Both that and a page that is not a `GROUP` are reported by
    [`validate`][py2tosc.validate] rather than rejected here, since TouchOSC
    loads them either way.

    Args:
        *pages: The pages, in tab order.
        pad: Inset applied to every page, on top of the tab bar.
        **props: Properties to set on the pager.

    Returns:
        A `PAGER` holding the pages, waiting to be resolved.
    """
    for page in pages:
        # Only groups: a tab property on anything else is one that control type
        # has no use for, which `validate` would rightly report.
        if page.control_type is not ControlType.GROUP:
            continue
        if page.has("name") and not page.has("tabLabel"):
            page.set("tabLabel", page.get("name"))
        for key, colour in _PAGE_TAB_STYLE.items():
            if not page.has(key):
                page.set(key, colour)
    return _arranged(Layout(PAGES, pad=to_pad(pad)), pages, props, ControlType.PAGER)


def grid(
    control_type: ControlType | str,
    *,
    columns: int = 2,
    rows: int = 2,
    **props: Any,
) -> Control:
    """Build a `GRID` control: one control replicated across its cells.

    This is the format's own `GRID`, the same control
    [`py2tosc.grid`][py2tosc.grid] makes, but with the cells it must hold --
    TouchOSC has no empty grid. It fills itself with `columns * rows` controls
    of one type, which is what a multitoggle or a bank of faders is; every grid
    in the corpus holds a single type, so the type is what it takes rather than
    a list of children.

    To arrange controls you already have, and get a `GROUP` rather than a
    `GRID`, use [`tiles`][py2tosc.ui.tiles].

    A `GRID` tiles its cells itself rather than dividing its frame the way a
    layout does: every cell is the same size, with a three-point margin around
    and between, and whatever will not divide evenly is left at the far edge.
    Frames are assigned by [`resolve`][py2tosc.ui.resolve], as everywhere else.

    Cells are named `1` upwards, in the order `grid_order` and `grid_start`
    describe -- by default across each row from the top left. Reach them
    through the returned control to give them messages:

    ```python
    pads = matrix("BUTTON", columns=8, rows=8, name="multitoggle")
    for cell in pads:
        cell.messages.append(midi_note(prop("name")))
    ```

    Args:
        control_type: The control to replicate.
        columns: Cells across, written as `grid_x`.
        rows: Cells down, written as `grid_y`.
        **props: Properties to set on the grid itself.

    Returns:
        A `GRID` holding `columns * rows` controls, waiting to be resolved.

    Raises:
        ValueError: If `columns` or `rows` is less than one.
    """
    if columns < 1 or rows < 1:
        raise ValueError(f"a grid needs at least one cell, asked for {columns}x{rows}")

    kind = ControlType(control_type)
    cells = [Control(kind, name=str(n + 1)) for n in range(columns * rows)]
    props.setdefault("grid_x", columns)
    props.setdefault("grid_y", rows)
    # `gridType` records what the cells are, and the corpus numbers it by the
    # control type's position in the format's own order -- 1 BUTTON, 2 LABEL,
    # 4 FADER, 7 ENCODER, 8 RADAR, all five matching. Left at its default a
    # grid of buttons would announce itself as a grid of faders.
    props.setdefault("grid_type", list(ControlType).index(kind))
    return _arranged(
        Layout(CELLS, columns=columns, rows=rows),
        cells,
        props,
        ControlType.GRID,
    )
