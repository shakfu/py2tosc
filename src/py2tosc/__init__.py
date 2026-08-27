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

from . import json_codec, layout, properties, render, surface, ui, ui_json
from .codegen import to_python
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
from .document import Document, dumps, edit, load, loads, save
from .enums import (
    AlignH,
    AlignV,
    ButtonType,
    ControlType,
    Conversion,
    CursorDisplay,
    Font,
    GamepadInput,
    MidiType,
    Orientation,
    OutlineStyle,
    PartialType,
    PointerPriority,
    PropertyType,
    RadioType,
    Response,
    Shape,
    TriggerCondition,
)
from .errors import FormatError, Py2ToscError, SchemaError
from .json_codec import from_json, to_json
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
from .render import to_html, to_svg
from .validate import Issue, ValidationError, validate

__version__ = "0.6.0"

# Sorted rather than grouped by topic, because RUF022 asks for it and the
# grouping lives in the API reference instead. See docs/api/.
__all__ = [
    "ALL_CONNECTIONS",
    "ALL_GAMEPADS",
    "AlignH",
    "AlignV",
    "ButtonType",
    "Color",
    "Control",
    "ControlType",
    "Conversion",
    "CursorDisplay",
    "Document",
    "Font",
    "FormatError",
    "Frame",
    "GamepadInput",
    "GamepadMessage",
    "Issue",
    "LocalMessage",
    "Message",
    "MidiCommand",
    "MidiMessage",
    "MidiType",
    "MidiValue",
    "Orientation",
    "OscMessage",
    "OutlineStyle",
    "Partial",
    "PartialType",
    "PointerPriority",
    "Property",
    "PropertyType",
    "Py2ToscError",
    "RadioType",
    "Response",
    "SchemaError",
    "Shape",
    "Trigger",
    "TriggerCondition",
    "ValidationError",
    "Value",
    "__version__",
    "box",
    "button",
    "dumps",
    "edit",
    "encoder",
    "fader",
    "from_json",
    "grid",
    "group",
    "json_codec",
    "label",
    "layout",
    "load",
    "loads",
    "pager",
    "properties",
    "radar",
    "radial",
    "radio",
    "render",
    "save",
    "surface",
    "text",
    "to_color",
    "to_frame",
    "to_html",
    "to_json",
    "to_python",
    "to_svg",
    "ui",
    "ui_json",
    "validate",
    "xy",
]
