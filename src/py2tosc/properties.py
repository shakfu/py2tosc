"""Control properties, and the mapping between Python and file-format names.

TouchOSC property keys are camelCase because that is what the format stores
(`cornerRadius`, `textSize`, `gridSteps`). This module translates at the
boundary so Python code can stay in `snake_case`: `corner_radius` addresses the
`cornerRadius` key, and nothing in the file changes.
"""

from __future__ import annotations

import re
from typing import Any, NamedTuple

from .enums import PropertyType

__all__ = ["Color", "Frame", "Property", "to_color", "to_frame"]

_SNAKE_BOUNDARY = re.compile(r"_([a-z0-9])")
_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def to_camel(name: str) -> str:
    """Convert a `snake_case` Python name to its camelCase format key.

    Names that contain no underscore are returned unchanged, so already-camelCase
    keys pass through untouched.

    Args:
        name: A property name in either convention.

    Returns:
        The camelCase key as it is stored in the file.
    """
    return _SNAKE_BOUNDARY.sub(lambda m: m.group(1).upper(), name)


def to_snake(key: str) -> str:
    """Convert a camelCase format key to its `snake_case` Python name.

    Args:
        key: A property key as stored in the file.

    Returns:
        The `snake_case` equivalent.
    """
    return _CAMEL_BOUNDARY.sub("_", key).lower()


class Frame(NamedTuple):
    """A control's position and size, in points.

    Components are floats: TouchOSC positions controls at sub-pixel offsets, and
    its own layouts are full of frames like `x=417.439`. Rounding them would
    move every such control.

    Comparable and unpackable as a plain `(x, y, w, h)` tuple, and an integral
    frame compares equal to a tuple of ints.
    """

    x: float
    y: float
    w: float
    h: float


class Color(NamedTuple):
    """An RGBA colour with components from 0.0 to 1.0.

    Comparable and unpackable as a plain `(r, g, b, a)` tuple.
    """

    r: float
    g: float
    b: float
    a: float


def to_frame(value: Any) -> Frame:
    """Coerce a 4-item sequence into a [`Frame`][py2tosc.Frame].

    Args:
        value: Any sequence of four numbers.

    Returns:
        The frame, with components as floats. They are not rounded: TouchOSC
        stores sub-pixel positions and rounding would move the control.

    Raises:
        ValueError: If `value` does not hold exactly four items.
    """
    if isinstance(value, Frame):
        return value
    items = tuple(value)
    if len(items) != 4:
        raise ValueError(f"a frame needs 4 values (x, y, w, h), got {len(items)}")
    return Frame(*(float(i) for i in items))


def to_color(value: Any) -> Color:
    """Coerce a colour in any accepted notation into a [`Color`][py2tosc.Color].

    Accepts floats already in 0.0-1.0, integers in 0-255, and hex strings with
    or without a leading `#` and with or without an alpha pair.

    Args:
        value: `(1.0, 0.0, 0.0, 1.0)`, `(255, 0, 0, 255)`, `"#ff0000"` or
            `"#ff0000ff"`.

    Returns:
        The colour normalised to 0.0-1.0.

    Raises:
        ValueError: If the string is not 6 or 8 hex digits, or the sequence does
            not hold three or four items.
    """
    if isinstance(value, Color):
        return value

    if isinstance(value, str):
        text = value.lstrip("#")
        if len(text) not in (6, 8):
            raise ValueError(f"{value!r} is not a 6 or 8 digit hex colour")
        pairs = [text[i : i + 2] for i in range(0, len(text), 2)]
        components = [int(p, 16) / 255 for p in pairs]
        if len(components) == 3:
            components.append(1.0)
        return Color(*components)

    items = tuple(value)
    if len(items) not in (3, 4):
        raise ValueError(f"a colour needs 3 or 4 values, got {len(items)}")

    rgb = items[:3]
    alpha = items[3] if len(items) == 4 else None

    # The scale is decided by the RGB components alone. Integers above 1 mean
    # 0-255; anything else is already normalised. A tuple of ints that are all
    # 0 or 1 is ambiguous, and (0, 0, 0, 1) is a far more common way to write
    # opaque black than "almost transparent almost-black".
    scaled = all(isinstance(i, int) for i in rgb) and any(i > 1 for i in rgb)
    components = [i / 255 if scaled else float(i) for i in rgb]

    # Alpha is judged on its own: in 0-255 notation an alpha of 1 still reads as
    # "opaque", because nobody writes 0.4% opacity as an integer.
    if alpha is None:
        components.append(1.0)
    elif isinstance(alpha, int) and alpha > 1:
        components.append(alpha / 255)
    else:
        components.append(float(alpha))

    return Color(*components)


#: Property keys whose type cannot be inferred from a Python value alone.
#: Frames and colours are both 4-tuples, `1` could be an int or a float, and a
#: boolean written as `1` is indistinguishable from an integer.
#:
#: `gridX` and `gridY` are deliberately absent: they are element counts on a
#: GRID control and on/off switches on an XY or RADAR. That conflict is settled
#: in `infer_type`, which lets a real `bool` override this table.
KNOWN_TYPES: dict[str, PropertyType] = {
    "frame": PropertyType.FRAME,
    "color": PropertyType.COLOR,
    "textColor": PropertyType.COLOR,
    "gridColor": PropertyType.COLOR,
    "tabColorOff": PropertyType.COLOR,
    "tabColorOn": PropertyType.COLOR,
    "textColorOff": PropertyType.COLOR,
    "textColorOn": PropertyType.COLOR,
    "name": PropertyType.STRING,
    "tag": PropertyType.STRING,
    "script": PropertyType.STRING,
    "tabLabel": PropertyType.STRING,
    "cornerRadius": PropertyType.FLOAT,
    "outlineStyle": PropertyType.INTEGER,
    "pointerPriority": PropertyType.INTEGER,
    "orientation": PropertyType.INTEGER,
    "shape": PropertyType.INTEGER,
    "font": PropertyType.INTEGER,
    "textAlignH": PropertyType.INTEGER,
    "textAlignV": PropertyType.INTEGER,
    "textLength": PropertyType.INTEGER,
    "textSize": PropertyType.INTEGER,
    "textSizeOff": PropertyType.INTEGER,
    "textSizeOn": PropertyType.INTEGER,
    "buttonType": PropertyType.INTEGER,
    "response": PropertyType.INTEGER,
    "responseFactor": PropertyType.INTEGER,
    "gridSteps": PropertyType.INTEGER,
    "gridStepsX": PropertyType.INTEGER,
    "gridStepsY": PropertyType.INTEGER,
    "cursorDisplay": PropertyType.INTEGER,
    "linesDisplay": PropertyType.INTEGER,
    "barDisplay": PropertyType.INTEGER,
    "steps": PropertyType.INTEGER,
    "radioType": PropertyType.INTEGER,
    "gridNaming": PropertyType.INTEGER,
    "gridOrder": PropertyType.INTEGER,
    "gridStart": PropertyType.INTEGER,
    "gridType": PropertyType.INTEGER,
    "gridX": PropertyType.INTEGER,
    "gridY": PropertyType.INTEGER,
    "tabbarSize": PropertyType.INTEGER,
    # Booleans, so that `control.visible = 1` is still stored as type 'b'.
    "background": PropertyType.BOOLEAN,
    "bar": PropertyType.BOOLEAN,
    "centered": PropertyType.BOOLEAN,
    "cursor": PropertyType.BOOLEAN,
    "exclusive": PropertyType.BOOLEAN,
    "grabFocus": PropertyType.BOOLEAN,
    "grid": PropertyType.BOOLEAN,
    "interactive": PropertyType.BOOLEAN,
    "inverted": PropertyType.BOOLEAN,
    "lines": PropertyType.BOOLEAN,
    "lockX": PropertyType.BOOLEAN,
    "lockY": PropertyType.BOOLEAN,
    "locked": PropertyType.BOOLEAN,
    "outline": PropertyType.BOOLEAN,
    "press": PropertyType.BOOLEAN,
    "release": PropertyType.BOOLEAN,
    "tabLabels": PropertyType.BOOLEAN,
    "tabbar": PropertyType.BOOLEAN,
    "tabbarDoubleTap": PropertyType.BOOLEAN,
    "textClip": PropertyType.BOOLEAN,
    "textWrap": PropertyType.BOOLEAN,
    "valuePosition": PropertyType.BOOLEAN,
    "visible": PropertyType.BOOLEAN,
}


def infer_type(key: str, value: Any) -> PropertyType:
    """Decide which `<property type=>` a key and value should be stored as.

    Known TouchOSC keys use their documented type. Anything else -- including
    custom properties -- is inferred from the Python type of `value`.

    Args:
        key: The camelCase property key.
        value: The Python value being stored.

    Returns:
        The property type to write.

    Raises:
        TypeError: If `value` has no representable type.
    """
    # A real bool outranks the table, which is how a `gridX` meaning "show the
    # grid" is told apart from a `gridX` meaning "two columns".
    if isinstance(value, bool):
        return PropertyType.BOOLEAN
    if key in KNOWN_TYPES:
        return KNOWN_TYPES[key]
    if isinstance(value, Frame):
        return PropertyType.FRAME
    if isinstance(value, Color):
        return PropertyType.COLOR
    if isinstance(value, int):
        return PropertyType.INTEGER
    if isinstance(value, float):
        return PropertyType.FLOAT
    if isinstance(value, str):
        return PropertyType.STRING
    if isinstance(value, (tuple, list)) and len(value) == 4:
        return (
            PropertyType.FRAME
            if all(isinstance(i, int) for i in value)
            else PropertyType.COLOR
        )
    raise TypeError(
        f"cannot store {key}={value!r} ({type(value).__name__}) as a property"
    )


class Property:
    """A single `<property>`: a typed, named value on a control.

    A property's Python value is always a native type -- `bool`, `int`, `float`,
    `str`, [`Frame`][py2tosc.Frame] or [`Color`][py2tosc.Color] -- and is
    converted to text only when the file is written.

    Attributes:
        key: The camelCase key as stored in the file.
        type: Which `<property type=>` this is written as.
        value: The native Python value.
    """

    __slots__ = ("_value", "key", "type")

    def __init__(self, key: str, value: Any, type: PropertyType | str | None = None):
        """
        Args:
            key: The property key, in either `snake_case` or camelCase.
            value: The value to store.
            type: Force a property type instead of inferring one. Rarely needed.
        """
        self.key = to_camel(key)
        self.type = (
            PropertyType(type) if type is not None else infer_type(self.key, value)
        )
        self._value = self._coerce(value)

    def _coerce(self, value: Any) -> Any:
        match self.type:
            case PropertyType.FRAME:
                return to_frame(value)
            case PropertyType.COLOR:
                return to_color(value)
            case PropertyType.BOOLEAN:
                return bool(value)
            case PropertyType.INTEGER:
                return int(value)
            case PropertyType.FLOAT:
                return float(value)
            case _:
                return str(value)

    @property
    def value(self) -> Any:
        """The native Python value, coerced to match `type`."""
        return self._value

    @value.setter
    def value(self, new: Any) -> None:
        self._value = self._coerce(new)

    @property
    def python_name(self) -> str:
        """The `snake_case` name this property is reachable by."""
        return to_snake(self.key)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Property):
            return NotImplemented
        return (self.key, self.type, self._value) == (
            other.key,
            other.type,
            other._value,
        )

    def __hash__(self) -> int:
        return hash((self.key, self.type, self._value))

    def __repr__(self) -> str:
        return f"Property({self.key!r}, {self._value!r}, {self.type.value!r})"
