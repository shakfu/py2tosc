"""Reading and writing the `.tosc` XML dialect.

Serialization is hand-rolled rather than delegated to `ElementTree` for one
reason: TouchOSC wraps keys and string values in CDATA sections, and
`ElementTree` cannot emit them. Writing the format directly also fixes element
order and the handling of the `<includes>` element, which together make output
byte-for-byte identical to what the TouchOSC editor itself produces.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any

from .control import Control
from .enums import ControlType, PropertyType
from .errors import FormatError
from .messages import (
    GamepadMessage,
    LocalMessage,
    Message,
    MidiCommand,
    MidiMessage,
    MidiValue,
    OscMessage,
    Partial,
    Trigger,
    Value,
)
from .properties import Color, Frame, Property

__all__ = ["from_xml", "to_xml"]

_DECLARATION = "<?xml version='1.0' encoding='UTF-8'?>"


def _num(value: Any) -> str:
    """Render a number the way TouchOSC does: no trailing `.0`."""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _Writer:
    """Collects the document as a list of lines, one element or tag per line."""

    def __init__(self) -> None:
        self.lines: list[str] = []

    def open(self, tag: str, **attrs: str) -> None:
        rendered = "".join(f" {k}='{_escape(v)}'" for k, v in attrs.items())
        self.lines.append(f"<{tag}{rendered}>")

    def close(self, tag: str) -> None:
        self.lines.append(f"</{tag}>")

    def leaf(self, tag: str, text: Any, cdata: bool = False) -> None:
        body = f"<![CDATA[{text}]]>" if cdata else _escape(str(text))
        self.lines.append(f"<{tag}>{body}</{tag}>")

    def empty(self, tag: str) -> None:
        self.open(tag)
        self.close(tag)

    def render(self, pretty: bool) -> str:
        if pretty:
            return "\n".join(self.lines) + "\n"
        return "".join(self.lines)


# -- writing ----------------------------------------------------------------


def _write_property(w: _Writer, prop: Property) -> None:
    w.open("property", type=prop.type.value)
    w.leaf("key", prop.key, cdata=True)
    value = prop.value
    if prop.type is PropertyType.FRAME:
        w.open("value")
        for field, item in zip(("x", "y", "w", "h"), value):
            w.leaf(field, _num(item))
        w.close("value")
    elif prop.type is PropertyType.COLOR:
        w.open("value")
        for field, item in zip(("r", "g", "b", "a"), value):
            w.leaf(field, _num(item))
        w.close("value")
    elif prop.type is PropertyType.STRING:
        w.leaf("value", value, cdata=True)
    else:
        w.leaf("value", _num(value))
    w.close("property")


def _default_text(default: Any) -> str:
    """Render a value's default. Booleans are words here, not 1 and 0."""
    if isinstance(default, bool):
        return "true" if default else "false"
    if isinstance(default, str):
        return default
    return _num(default)


def _write_value(w: _Writer, value: Value) -> None:
    w.open("value")
    w.leaf("key", value.key, cdata=True)
    w.leaf("locked", _num(value.locked))
    w.leaf("lockedDefaultCurrent", _num(value.locked_default_current))
    w.leaf("default", _default_text(value.default), cdata=True)
    w.leaf("defaultPull", _num(value.default_pull))
    w.close("value")


def _write_triggers(w: _Writer, triggers: list[Trigger]) -> None:
    # Omitted entirely when empty: across 4817 trigger-less messages in the
    # bundled TouchOSC examples, the editor never writes <triggers></triggers>.
    if not triggers:
        return
    w.open("triggers")
    for trigger in triggers:
        w.open("trigger")
        w.leaf("var", trigger.var, cdata=True)
        w.leaf("condition", str(trigger.condition))
        w.close("trigger")
    w.close("triggers")


def _write_partials(w: _Writer, tag: str, partials: list[Partial]) -> None:
    w.open(tag)
    for partial in partials:
        w.open("partial")
        w.leaf("type", str(partial.type))
        w.leaf("conversion", str(partial.conversion))
        w.leaf("value", partial.value, cdata=True)
        w.leaf("scaleMin", _num(partial.scale_min))
        w.leaf("scaleMax", _num(partial.scale_max))
        w.close("partial")
    w.close(tag)


def _write_message(w: _Writer, message: Message, modern: bool) -> None:
    if isinstance(message, OscMessage):
        w.open("osc")
        w.leaf("enabled", _num(message.enabled))
        w.leaf("send", _num(message.send))
        w.leaf("receive", _num(message.receive))
        w.leaf("feedback", _num(message.feedback))
        if modern:
            w.leaf("noDuplicates", _num(message.no_duplicates))
        w.leaf("connections", message.connections)
        _write_triggers(w, message.triggers)
        _write_partials(w, "path", message.path)
        _write_partials(w, "arguments", message.arguments)
        w.close("osc")

    elif isinstance(message, MidiMessage):
        w.open("midi")
        w.leaf("enabled", _num(message.enabled))
        w.leaf("send", _num(message.send))
        w.leaf("receive", _num(message.receive))
        w.leaf("feedback", _num(message.feedback))
        if modern:
            w.leaf("noDuplicates", _num(message.no_duplicates))
        w.leaf("connections", message.connections)
        _write_triggers(w, message.triggers)
        w.open("message")
        w.leaf("type", str(message.message.type))
        w.leaf("channel", _num(message.message.channel))
        w.leaf("data1", _num(message.message.data1))
        w.leaf("data2", _num(message.message.data2))
        w.close("message")
        w.open("values")
        for item in message.values:
            w.open("value")
            w.leaf("type", str(item.type))
            w.leaf("key", item.key, cdata=True)
            w.leaf("scaleMin", _num(item.scale_min))
            w.leaf("scaleMax", _num(item.scale_max))
            w.close("value")
        w.close("values")
        w.close("midi")

    elif isinstance(message, LocalMessage):
        w.open("local")
        w.leaf("enabled", _num(message.enabled))
        _write_triggers(w, message.triggers)
        w.leaf("type", str(message.type))
        w.leaf("conversion", str(message.conversion))
        w.leaf("value", message.value, cdata=True)
        w.leaf("scaleMin", _num(message.scale_min))
        w.leaf("scaleMax", _num(message.scale_max))
        w.leaf("dstType", message.dst_type)
        w.leaf("dstVar", message.dst_var, cdata=True)
        w.leaf("dstID", message.dst_id, cdata=True)
        w.close("local")

    elif isinstance(message, GamepadMessage):
        w.open("gamepad")
        w.leaf("enabled", _num(message.enabled))
        w.leaf("connections", message.connections)
        w.leaf("type", str(message.type))
        w.leaf("conversion", str(message.conversion))
        w.leaf("scaleMin", _num(message.scale_min))
        w.leaf("scaleMax", _num(message.scale_max))
        w.leaf("targetType", str(message.target_type))
        w.leaf("targetVar", message.target_var, cdata=True)
        w.close("gamepad")

    else:
        raise TypeError(f"{type(message).__name__} is not a message type")


def _is_modern(version: str) -> bool:
    """Whether the document uses lexml 6 conventions.

    Two elements distinguish version 6 from the version 3 files older editors
    and older tosclib releases produced: `<includes>` on the root node, and
    `<noDuplicates>` on OSC and MIDI bindings. Writing either into a version 3
    document would make it something the editor never wrote, so both are gated
    on the version the document declares.

    An unrecognised version is treated as modern, on the grounds that anything
    newer than 6 will keep them.
    """
    try:
        return int(version) >= 6
    except ValueError:
        return True


def _write_control(w: _Writer, control: Control, is_root: bool, includes: bool) -> None:
    w.open("node", ID=control.id, type=control.control_type.value)

    if (is_root and includes) or getattr(control, "_has_includes", False):
        w.empty("includes")

    w.open("properties")
    for key in sorted(control.properties):
        _write_property(w, control.properties[key])
    w.close("properties")

    if control.values:
        w.open("values")
        for value in control.values:
            _write_value(w, value)
        w.close("values")

    if control.messages:
        w.open("messages")
        for message in control.messages:
            _write_message(w, message, modern=includes)
        w.close("messages")

    if control.children:
        w.open("children")
        for child in control.children:
            _write_control(w, child, is_root=False, includes=includes)
        w.close("children")

    w.close("node")


def to_xml(root: Control, version: str = "6", pretty: bool = False) -> str:
    """Serialize a control tree to the `.tosc` XML dialect.

    Args:
        root: The root control of the layout.
        version: The `lexml` format version to declare. Versions below 6 are
            written without the `<includes>` element, which did not exist yet.
        pretty: Emit one element per line, matching the editor's XML export.
            The default single-line form matches what the editor saves inside a
            `.tosc`.

    Returns:
        The complete XML document, including its declaration.
    """
    w = _Writer()
    w.lines.append(_DECLARATION)
    w.open("lexml", version=version)
    _write_control(w, root, is_root=True, includes=_is_modern(version))
    w.close("lexml")
    return w.render(pretty)


# -- reading ----------------------------------------------------------------


def _text(element: ET.Element | None, default: str = "") -> str:
    if element is None or element.text is None:
        return default
    return element.text


def _flag(element: ET.Element | None, default: bool = False) -> bool:
    raw = _text(element)
    return default if raw == "" else raw not in ("0", "false")


def _number(element: ET.Element | None, default: float = 0) -> float:
    raw = _text(element)
    try:
        return float(raw)
    except ValueError:
        return default


def _read_property(element: ET.Element) -> Property:
    key = _text(element.find("key"))
    kind = PropertyType(element.get("type", "s"))
    value_element = element.find("value")

    def part(name: str) -> ET.Element | None:
        """A composite value's child, tolerating a property with no <value>."""
        return None if value_element is None else value_element.find(name)

    raw: Any
    match kind:
        case PropertyType.FRAME:
            raw = Frame(*(_number(part(f)) for f in "xywh"))
        case PropertyType.COLOR:
            raw = Color(*(_number(part(f)) for f in "rgba"))
        case PropertyType.BOOLEAN:
            raw = _flag(value_element)
        case PropertyType.INTEGER:
            raw = int(_number(value_element))
        case PropertyType.FLOAT:
            raw = _number(value_element)
        case _:
            raw = _text(value_element)

    return Property(key, raw, kind)


def _read_default(key: str, raw: str) -> bool | float | str:
    if key == "text":
        return raw
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return float(raw)
    except ValueError:
        return raw


def _read_value(element: ET.Element) -> Value:
    key = _text(element.find("key"))
    return Value(
        key=key,
        locked=_flag(element.find("locked")),
        locked_default_current=_flag(element.find("lockedDefaultCurrent")),
        default=_read_default(key, _text(element.find("default"))),
        default_pull=int(_number(element.find("defaultPull"))),
    )


def _read_triggers(element: ET.Element | None) -> list[Trigger]:
    if element is None:
        return []
    return [
        Trigger(var=_text(t.find("var")), condition=_text(t.find("condition"), "ANY"))
        for t in element.findall("trigger")
    ]


def _read_partials(element: ET.Element | None) -> list[Partial]:
    if element is None:
        return []
    return [
        Partial(
            type=_text(p.find("type"), "CONSTANT"),
            conversion=_text(p.find("conversion"), "STRING"),
            value=_text(p.find("value")),
            scale_min=_number(p.find("scaleMin")),
            scale_max=_number(p.find("scaleMax"), 1),
        )
        for p in element.findall("partial")
    ]


def _read_message(element: ET.Element) -> Message:
    if element.tag == "osc":
        return OscMessage(
            enabled=_flag(element.find("enabled"), True),
            send=_flag(element.find("send"), True),
            receive=_flag(element.find("receive"), True),
            feedback=_flag(element.find("feedback")),
            no_duplicates=_flag(element.find("noDuplicates")),
            connections=_text(element.find("connections")),
            triggers=_read_triggers(element.find("triggers")),
            path=_read_partials(element.find("path")),
            arguments=_read_partials(element.find("arguments")),
        )

    if element.tag == "midi":
        command = element.find("message")
        values = element.find("values")
        return MidiMessage(
            enabled=_flag(element.find("enabled"), True),
            send=_flag(element.find("send"), True),
            receive=_flag(element.find("receive"), True),
            feedback=_flag(element.find("feedback")),
            no_duplicates=_flag(element.find("noDuplicates")),
            connections=_text(element.find("connections")),
            triggers=_read_triggers(element.find("triggers")),
            message=MidiCommand(
                type=_text(command.find("type"), "CONTROLCHANGE")
                if command is not None
                else "CONTROLCHANGE",
                channel=int(_number(command.find("channel")))
                if command is not None
                else 0,
                data1=int(_number(command.find("data1"))) if command is not None else 0,
                data2=int(_number(command.find("data2"))) if command is not None else 0,
            ),
            values=[
                MidiValue(
                    type=_text(v.find("type"), "CONSTANT"),
                    key=_text(v.find("key")),
                    scale_min=_number(v.find("scaleMin")),
                    scale_max=_number(v.find("scaleMax")),
                )
                for v in (values.findall("value") if values is not None else [])
            ],
        )

    if element.tag == "gamepad":
        return GamepadMessage(
            enabled=_flag(element.find("enabled"), True),
            connections=_text(element.find("connections")),
            type=_text(element.find("type"), "BUTTON_A"),
            conversion=_text(element.find("conversion"), "FLOAT"),
            scale_min=_number(element.find("scaleMin")),
            scale_max=_number(element.find("scaleMax"), 1),
            target_type=_text(element.find("targetType"), "VALUE"),
            target_var=_text(element.find("targetVar")),
        )

    if element.tag == "local":
        return LocalMessage(
            enabled=_flag(element.find("enabled"), True),
            triggers=_read_triggers(element.find("triggers")),
            type=_text(element.find("type"), "VALUE"),
            conversion=_text(element.find("conversion"), "FLOAT"),
            value=_text(element.find("value")),
            scale_min=_number(element.find("scaleMin")),
            scale_max=_number(element.find("scaleMax"), 1),
            dst_type=_text(element.find("dstType")),
            dst_var=_text(element.find("dstVar")),
            dst_id=_text(element.find("dstID")),
        )

    raise FormatError(f"<{element.tag}> is not a known message type")


def _read_control(element: ET.Element) -> Control:
    control = Control(
        ControlType(element.get("type", "GROUP")),
        id=element.get("ID"),
        properties={},
        values=[],
        messages=[],
        children=[],
    )
    # Replace the type defaults wholesale: the file is the source of truth.
    control.properties.clear()

    for child in element.findall("./properties/property"):
        prop = _read_property(child)
        control.properties[prop.key] = prop

    control.values.extend(_read_value(v) for v in element.findall("./values/value"))

    messages = element.find("messages")
    if messages is not None:
        control.messages.extend(_read_message(m) for m in messages)

    control.children.extend(
        _read_control(node) for node in element.findall("./children/node")
    )

    if element.find("includes") is not None:
        object.__setattr__(control, "_has_includes", True)

    return control


def from_xml(source: str | bytes) -> tuple[Control, str]:
    """Parse the `.tosc` XML dialect into a control tree.

    Args:
        source: The XML document, as text or bytes.

    Returns:
        The root control and the `lexml` version it declared.

    Raises:
        FormatError: If the source is not XML, or is not a `lexml` root
            holding one node, or holds a type the format does not define.
    """
    try:
        root = ET.fromstring(source)
    except ET.ParseError as exc:
        raise FormatError(f"not valid XML: {exc}") from exc

    if root.tag != "lexml":
        raise FormatError(f"expected a <lexml> root, found <{root.tag}>")

    node = root.find("node")
    if node is None:
        raise FormatError("<lexml> holds no <node>")

    try:
        return _read_control(node), root.get("version", "6")
    except FormatError:
        raise
    except ValueError as exc:
        # An enum refusing an unknown control type, or a field that will not
        # parse. From the caller's side these are all the same statement: this
        # document is not readable. Narrowing to FormatError cannot break an
        # `except ValueError`, since FormatError is one.
        raise FormatError(str(exc)) from exc
