"""Generate and edit TouchOSC layouts from Python.

```python
import py2tosc

doc = py2tosc.load("layout.tosc")
for fader in doc.find_all(type="FADER"):
    fader.color = "#e76f51"
doc.save("out.tosc")
```

This project has no relation to Hexler, the developer of TouchOSC. Back up your
layouts before editing them with third party tools.
"""

from . import layout, ui
from .control import (
    Control,
    box,
    button,
    encoder,
    fader,
    grid,
    group,
    label,
    pager,
    radar,
    radial,
    radio,
    text,
    xy,
)
from .document import Document, dumps, load, loads, save
from .enums import (
    ControlType,
    Conversion,
    MidiType,
    PartialType,
    PropertyType,
    TriggerCondition,
)
from .messages import (
    ALL_CONNECTIONS,
    ALL_GAMEPADS,
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
from .properties import Color, Frame, Property, to_color, to_frame
from .validate import Issue, ValidationError, validate

#: Keep in step with `version` in pyproject.toml, which the build backend reads
#: and which `uv_build` requires to be static. `test_version_is_declared_once`
#: fails if the two drift apart.
__version__ = "0.2.0"

# Sorted rather than grouped by topic, because RUF022 asks for it and the
# grouping lives in the API reference instead. See docs/api/.
__all__ = [
    "ALL_CONNECTIONS",
    "ALL_GAMEPADS",
    "Color",
    "Control",
    "ControlType",
    "Conversion",
    "Document",
    "Frame",
    "GamepadMessage",
    "Issue",
    "LocalMessage",
    "Message",
    "MidiCommand",
    "MidiMessage",
    "MidiType",
    "MidiValue",
    "OscMessage",
    "Partial",
    "PartialType",
    "Property",
    "PropertyType",
    "Trigger",
    "TriggerCondition",
    "ValidationError",
    "Value",
    "__version__",
    "box",
    "button",
    "dumps",
    "encoder",
    "fader",
    "grid",
    "group",
    "label",
    "layout",
    "load",
    "loads",
    "pager",
    "radar",
    "radial",
    "radio",
    "save",
    "text",
    "to_color",
    "to_frame",
    "ui",
    "validate",
    "xy",
]
