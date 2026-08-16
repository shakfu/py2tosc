"""Enumerations mirroring Hexler's TouchOSC design.

These values are the file format's own vocabulary and are written verbatim into
`.tosc` files, so their spelling is fixed by TouchOSC and not by this library.

The integer enumerations name numbers a property already stored as a bare `int`,
so they are `IntEnum` and interchangeable with the numbers everywhere: `shape ==
1` and `shape is Shape.RECTANGLE` are both true of a rectangle, and a layout
written before these existed loads unchanged.

Their names come from the TouchOSC manual, which lists them in order but gives
no numbers. The numbers come from the corpus, and the two are joined by one
observation: a property whose lowest written value is `0` is numbered from `0`,
and one whose lowest is `1` is numbered from `1`. TouchOSC is inconsistent about
which it uses -- `shape`, `textAlignH` and `textAlignV` start at 1 and the rest
start at 0 -- so guessing from the manual's ordering alone gets three of them
wrong. `tests/test_enums.py` checks every value the corpus contains against
these members.
"""

from enum import Enum, IntEnum

__all__ = [
    "AlignH",
    "AlignV",
    "ButtonType",
    "ControlType",
    "Conversion",
    "CursorDisplay",
    "Font",
    "GamepadInput",
    "MidiType",
    "Orientation",
    "OutlineStyle",
    "PartialType",
    "PointerPriority",
    "PropertyType",
    "RadioType",
    "Response",
    "Shape",
    "TriggerCondition",
]


class _StrEnum(str, Enum):
    """A string enum whose ``str()`` is the value, on Python 3.10 and up."""

    def __str__(self) -> str:
        return str(self.value)


class _IntEnum(IntEnum):
    """An int enum whose ``str()`` is the number the file stores.

    Python 3.11 made `IntEnum.__str__` return the number, but 3.10 -- which this
    package supports -- returns `Shape.CIRCLE`. Writing that into a `<value>`
    would produce a file TouchOSC cannot read, so the behaviour is pinned here
    rather than left to the interpreter version.
    """

    def __str__(self) -> str:
        return str(self.value)


class ControlType(_StrEnum):
    """The `type` attribute of a `<node>` element."""

    BOX = "BOX"
    BUTTON = "BUTTON"
    LABEL = "LABEL"
    TEXT = "TEXT"
    FADER = "FADER"
    XY = "XY"
    RADIAL = "RADIAL"
    ENCODER = "ENCODER"
    RADAR = "RADAR"
    RADIO = "RADIO"
    GROUP = "GROUP"
    PAGER = "PAGER"
    GRID = "GRID"


class PropertyType(_StrEnum):
    """The `type` attribute of a `<property>` element.

    `FRAME` and `COLOR` are the two composite types: their `<value>` holds four
    named child elements rather than text.
    """

    STRING = "s"
    BOOLEAN = "b"
    INTEGER = "i"
    FLOAT = "f"
    FRAME = "r"
    COLOR = "c"


class PartialType(_StrEnum):
    """What a path or argument partial draws its content from."""

    CONSTANT = "CONSTANT"
    PROPERTY = "PROPERTY"
    VALUE = "VALUE"
    INDEX = "INDEX"


class Conversion(_StrEnum):
    """The type a partial is converted to before being sent."""

    BOOLEAN = "BOOLEAN"
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    STRING = "STRING"


class TriggerCondition(_StrEnum):
    """When a trigger fires in response to a value change."""

    ANY = "ANY"
    RISE = "RISE"
    FALL = "FALL"


class MidiType(_StrEnum):
    """The MIDI status byte a message carries.

    These eight are the whole of it, and are exactly what the editor's own Type
    menu offers on a MIDI message. Four were already corroborated by layouts the
    editor wrote; the menu confirms the other four, which until then had only
    been inferred from the MIDI specification.

    The manual's scripting reference names a longer `MIDIMessageType` with nine
    more -- `CLOCK`, `START`, `STOP`, `CONTINUE`, `SONGPOSITION`, `SONGSELECT`,
    `QUARTERFRAME`, `ACTIVESENSING`, `SYSTEMRESET`. Those belong to `sendMIDI`
    in a script, which is a different thing from a message binding: the editor
    will not store one on a control, so they are deliberately absent here. A
    layout cannot express "send MIDI Start on press" as a binding; it takes a
    script.
    """

    NOTE_OFF = "NOTE_OFF"
    NOTE_ON = "NOTE_ON"
    POLYPRESSURE = "POLYPRESSURE"
    CONTROLCHANGE = "CONTROLCHANGE"
    PROGRAMCHANGE = "PROGRAMCHANGE"
    CHANNELPRESSURE = "CHANNELPRESSURE"
    PITCHBEND = "PITCHBEND"
    SYSTEMEXCLUSIVE = "SYSTEMEXCLUSIVE"


class GamepadInput(_StrEnum):
    """The button or axis a `GamepadMessage` binds to.

    All twenty-one appear in `gamepad.tosc`, the example TouchOSC ships, so
    every spelling here is one the editor wrote.
    """

    STICK_LEFT_X = "STICK_LEFT_X"
    STICK_LEFT_Y = "STICK_LEFT_Y"
    STICK_RIGHT_X = "STICK_RIGHT_X"
    STICK_RIGHT_Y = "STICK_RIGHT_Y"
    TRIGGER_LEFT = "TRIGGER_LEFT"
    TRIGGER_RIGHT = "TRIGGER_RIGHT"
    BUTTON_UP = "BUTTON_UP"
    BUTTON_DOWN = "BUTTON_DOWN"
    BUTTON_LEFT = "BUTTON_LEFT"
    BUTTON_RIGHT = "BUTTON_RIGHT"
    BUTTON_A = "BUTTON_A"
    BUTTON_B = "BUTTON_B"
    BUTTON_X = "BUTTON_X"
    BUTTON_Y = "BUTTON_Y"
    BUTTON_STICK_LEFT = "BUTTON_STICK_LEFT"
    BUTTON_STICK_RIGHT = "BUTTON_STICK_RIGHT"
    BUMPER_LEFT = "BUMPER_LEFT"
    BUMPER_RIGHT = "BUMPER_RIGHT"
    BUTTON_START = "BUTTON_START"
    BUTTON_SELECT = "BUTTON_SELECT"
    BUTTON_HOME = "BUTTON_HOME"


class Shape(_IntEnum):
    """The `shape` property. Numbered from 1.

    All six are corroborated by files the TouchOSC editor wrote. The bundled
    examples cover four, `HEXAGON` most convincingly, by the 119 hexagonal
    buttons in `hexkeys.tosc`. `DIAMOND` and `PENTAGON` appear nowhere in them
    and were settled by drawing one of each in the editor; that file is
    `tests/data/enums.tosc`, where every control is named after the shape it
    was given, so the mapping is checked rather than asserted.
    """

    RECTANGLE = 1
    CIRCLE = 2
    TRIANGLE = 3
    DIAMOND = 4
    PENTAGON = 5
    HEXAGON = 6


class AlignH(_IntEnum):
    """The `textAlignH` property. Numbered from 1."""

    LEFT = 1
    CENTER = 2
    RIGHT = 3


class AlignV(_IntEnum):
    """The `textAlignV` property. Numbered from 1.

    All three are corroborated. The bundled examples write only `TOP` and
    `MIDDLE`; `BOTTOM` was settled by a label drawn in the editor, in
    `tests/data/enums.tosc`.
    """

    TOP = 1
    MIDDLE = 2
    BOTTOM = 3


class Orientation(_IntEnum):
    """The `orientation` property: which way a control faces. Numbered from 0.

    All four are written by the corpus. A `RADIO` is never `NORTH`, since a
    radio runs horizontally or vertically.
    """

    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3


class ButtonType(_IntEnum):
    """The `buttonType` property: when a button reports a press. Numbered from 0.

    All three are written by the corpus.
    """

    MOMENTARY = 0
    TOGGLE_RELEASE = 1
    TOGGLE_PRESS = 2


class OutlineStyle(_IntEnum):
    """The `outlineStyle` property. Numbered from 0.

    All three are written by the corpus, `CORNERS` most often.
    """

    FULL = 0
    CORNERS = 1
    EDGES = 2


class CursorDisplay(_IntEnum):
    """The `cursorDisplay` and `barDisplay` properties. Numbered from 0.

    All three are corroborated. The bundled examples write only `ALWAYS` and
    `ACTIVE`; `INACTIVE` was settled by a fader drawn in the editor, in
    `tests/data/enums.tosc`, which carries it on `barDisplay`.
    """

    ALWAYS = 0
    ACTIVE = 1
    INACTIVE = 2


class Font(_IntEnum):
    """The `font` property. Numbered from 0. Both are written by the corpus."""

    DEFAULT = 0
    MONOSPACED = 1


class Response(_IntEnum):
    """The `response` property: how a drag maps to a value. Numbered from 0.

    Both are written by the corpus.
    """

    ABSOLUTE = 0
    RELATIVE = 1


class RadioType(_IntEnum):
    """The `radioType` property. Numbered from 0. Both are written by the corpus."""

    SELECT = 0
    METER = 1


class PointerPriority(_IntEnum):
    """The `pointerPriority` property. Numbered from 0.

    Both are written by the corpus, `OLDEST` almost always.
    """

    OLDEST = 0
    NEWEST = 1
