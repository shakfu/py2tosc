"""Enumerations mirroring Hexler's TouchOSC design.

These values are the file format's own vocabulary and are written verbatim into
`.tosc` files, so their spelling is fixed by TouchOSC and not by this library.
"""

from enum import Enum

__all__ = [
    "ControlType",
    "Conversion",
    "MidiType",
    "PartialType",
    "PropertyType",
    "TriggerCondition",
]


class _StrEnum(str, Enum):
    """A string enum whose ``str()`` is the value, on Python 3.10 and up."""

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

    `CONTROLCHANGE`, `NOTE_ON`, `PITCHBEND` and `PROGRAMCHANGE` are corroborated
    by layouts the TouchOSC editor wrote, including the examples bundled with
    the application. The remaining four are inferred from the MIDI
    specification and have not been seen in a real file, so if one is rejected,
    pass the spelling the editor uses as a plain string instead --
    `MidiCommand(type="...")` accepts any string.
    """

    NOTE_OFF = "NOTE_OFF"
    NOTE_ON = "NOTE_ON"
    POLYPRESSURE = "POLYPRESSURE"
    CONTROLCHANGE = "CONTROLCHANGE"
    PROGRAMCHANGE = "PROGRAMCHANGE"
    CHANNELPRESSURE = "CHANNELPRESSURE"
    PITCHBEND = "PITCHBEND"
    SYSTEMEXCLUSIVE = "SYSTEMEXCLUSIVE"
