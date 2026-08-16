"""Default property sets for each control type.

These mirror the properties TouchOSC writes for a newly created control, using
the camelCase keys of the file format. They were cross-checked against a layout
saved by TouchOSC 1.5.2.262; anything TouchOSC omits when empty -- `name`, `tag`
and `script` -- is omitted here too.

See <https://hexler.net/touchosc/manual/script-properties-and-values>.
"""

from __future__ import annotations

from typing import Any

from .enums import (
    AlignH,
    AlignV,
    ButtonType,
    ControlType,
    CursorDisplay,
    Font,
    Orientation,
    OutlineStyle,
    PointerPriority,
    RadioType,
    Response,
    Shape,
)

__all__ = ["allowed_properties", "defaults_for"]

_COMMON: dict[str, Any] = {
    "background": True,
    "color": (0.25, 0.25, 0.25, 1.0),
    "cornerRadius": 0.0,
    "frame": (0, 0, 100, 100),
    "grabFocus": True,
    "interactive": True,
    "locked": False,
    "orientation": Orientation.NORTH,
    "outline": True,
    "outlineStyle": OutlineStyle.CORNERS,
    "pointerPriority": PointerPriority.OLDEST,
    "shape": Shape.RECTANGLE,
    "visible": True,
}

#: `gridSteps` is per type rather than shared: the editor creates a FADER with
#: 13 and a RADIAL or ENCODER with 20, and the corpus follows it both times.
_GRID_LINES: dict[str, Any] = {
    "grid": True,
    "gridColor": (0.0, 0.0, 0.0, 0.25),
}

_RESPONSE: dict[str, Any] = {
    "response": Response.ABSOLUTE,
    "responseFactor": 100,
}

_CURSOR: dict[str, Any] = {
    "cursor": True,
    "cursorDisplay": CursorDisplay.ALWAYS,
}

_LINES: dict[str, Any] = {
    "lines": True,
    "linesDisplay": CursorDisplay.ALWAYS,
}

_TEXT: dict[str, Any] = {
    "font": Font.DEFAULT,
    "textAlignH": AlignH.CENTER,
    "textAlignV": AlignV.MIDDLE,
    "textColor": (1.0, 1.0, 1.0, 1.0),
    "textSize": 14,
}

_XY: dict[str, Any] = {
    "gridColor": (0.0, 0.0, 0.0, 0.25),
    "gridX": True,
    "gridY": True,
    "gridStepsX": 10,
    "gridStepsY": 10,
    "lockX": False,
    "lockY": False,
}

#: Decoration and containers do not take touches. A BOX, LABEL, TEXT or GROUP
#: left interactive swallows the press meant for whatever sits beneath it,
#: which is a layout that looks right and does nothing. Every one of the 5134
#: editor-written instances of these four types says so.
_INERT: dict[str, Any] = {"interactive": False}

#: A RADIAL, ENCODER or RADAR is drawn round: all 171 in the corpus are
#: `CIRCLE` while every rectangular type is `RECTANGLE`, and `controls.tosc` --
#: one freshly made control of each type -- agrees.
_ROUND: dict[str, Any] = {"shape": Shape.CIRCLE}

_CONTAINER: dict[str, Any] = {
    "grabFocus": False,
    "outlineStyle": OutlineStyle.FULL,
}

_BY_TYPE: dict[ControlType, dict[str, Any]] = {
    ControlType.BOX: {**_INERT},
    ControlType.BUTTON: {
        "buttonType": ButtonType.MOMENTARY,
        "press": True,
        "release": True,
        "valuePosition": False,
    },
    ControlType.LABEL: {**_TEXT, **_INERT, "textClip": True, "textLength": 0},
    ControlType.TEXT: {**_TEXT, **_INERT, "textClip": True, "textWrap": True},
    ControlType.FADER: {
        **_RESPONSE,
        **_GRID_LINES,
        **_CURSOR,
        "bar": True,
        "barDisplay": CursorDisplay.ALWAYS,
        "gridSteps": 13,
    },
    ControlType.XY: {**_RESPONSE, **_CURSOR, **_LINES, **_XY},
    ControlType.RADIAL: {
        **_RESPONSE,
        **_GRID_LINES,
        **_CURSOR,
        **_ROUND,
        "gridSteps": 20,
        "outlineStyle": OutlineStyle.FULL,
        "inverted": False,
        "centered": False,
    },
    ControlType.ENCODER: {
        **_RESPONSE,
        **_GRID_LINES,
        **_CURSOR,
        **_ROUND,
        "gridSteps": 20,
        "outlineStyle": OutlineStyle.FULL,
    },
    ControlType.RADAR: {**_CURSOR, **_LINES, **_XY, **_ROUND},
    # A radio runs horizontally or vertically, never facing NORTH: no instance
    # in the corpus does, so it defaults to EAST.
    ControlType.RADIO: {
        "steps": 5,
        "radioType": RadioType.SELECT,
        "orientation": Orientation.EAST,
    },
    ControlType.GROUP: {**_CONTAINER, **_INERT},
    ControlType.GRID: {
        "grabFocus": False,
        "exclusive": False,
        "gridNaming": 0,
        "gridOrder": 0,
        "gridStart": 0,
        "gridType": 4,
        "gridX": 2,
        "gridY": 2,
    },
    ControlType.PAGER: {
        **_CONTAINER,
        "tabLabels": True,
        "tabbar": True,
        "tabbarDoubleTap": False,
        "tabbarSize": 40,
        "textSizeOff": 14,
        "textSizeOn": 14,
    },
}

#: Values a freshly created control of each type starts with.
_VALUES_BY_TYPE: dict[ControlType, tuple[tuple[str, Any], ...]] = {
    ControlType.BOX: (("touch", False),),
    ControlType.BUTTON: (("x", 0.0), ("touch", False)),
    ControlType.LABEL: (("text", ""), ("touch", False)),
    ControlType.TEXT: (("text", ""), ("touch", False)),
    ControlType.FADER: (("x", 0.0), ("touch", False)),
    ControlType.XY: (("x", 0.0), ("y", 0.0), ("touch", False)),
    ControlType.RADIAL: (("x", 0.0), ("touch", False)),
    ControlType.ENCODER: (("x", 0.0), ("y", 0.0), ("touch", False)),
    ControlType.RADAR: (("x", 0.0), ("y", 0.0), ("touch", False)),
    ControlType.RADIO: (("x", 0.0), ("touch", False)),
    ControlType.GROUP: (("touch", False),),
    ControlType.GRID: (("touch", False),),
    ControlType.PAGER: (("page", 0.0), ("touch", False)),
}


def defaults_for(control_type: ControlType) -> dict[str, Any]:
    """Return the default properties for a control type.

    Args:
        control_type: The type to look up.

    Returns:
        A fresh dict of camelCase key to Python value, safe to mutate.
    """
    return {**_COMMON, **_BY_TYPE.get(control_type, {})}


def default_values_for(control_type: ControlType) -> tuple[tuple[str, Any], ...]:
    """Return the `(key, default)` pairs a new control of this type starts with.

    Args:
        control_type: The type to look up.

    Returns:
        A tuple of key and starting value pairs.
    """
    return _VALUES_BY_TYPE.get(control_type, (("touch", False),))


#: Properties TouchOSC omits when empty, which py2tosc leaves to the caller
#: rather than inventing. They are valid on any control.
CALLER_SUPPLIED = frozenset({"name", "tag", "script"})

#: Properties a control type accepts but does not start with, so they are valid
#: without being defaults. Derived from layouts the editor wrote: a `centered`
#: fader is a real thing the editor produces, and a GROUP acting as a PAGER's
#: page carries that page's tab styling.
_ALSO_ALLOWED: dict[ControlType, frozenset[str]] = {
    ControlType.FADER: frozenset({"centered"}),
    ControlType.GROUP: frozenset(
        {"tabColorOff", "tabColorOn", "tabLabel", "textColorOff", "textColorOn"}
    ),
}


def allowed_properties(control_type: ControlType) -> frozenset[str]:
    """Every property key that belongs on this control type.

    Wider than [`defaults_for`][py2tosc.defaults.defaults_for]: a key can be
    valid for a type without the editor writing it on every instance. Used by
    [`validate`][py2tosc.validate] to tell a misplaced format property from a
    deliberate custom one.

    Args:
        control_type: The type to look up.

    Returns:
        The type's default keys, the three the caller supplies, and any the
        editor is known to write for that type.
    """
    return (
        frozenset(defaults_for(control_type))
        | CALLER_SUPPLIED
        | _ALSO_ALLOWED.get(control_type, frozenset())
    )
