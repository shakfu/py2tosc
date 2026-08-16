"""Read a layout and report what its enumerated properties actually hold.

Point this at a file drawn in the TouchOSC editor to confirm the numbers behind
the names. Anything the enums cannot name is reported as UNKNOWN, which is the
answer worth having: it means the editor writes a value this library would not
recognise.

    uv run python scripts/check_enums.py tests/data/shapes.tosc

Naming a control after the setting you gave it makes the output self-checking:
a BUTTON called "pentagon" should come back as PENTAGON.
"""

from __future__ import annotations

import sys
from pathlib import Path

import py2tosc

ENUMS = {
    "shape": py2tosc.Shape,
    "textAlignH": py2tosc.AlignH,
    "textAlignV": py2tosc.AlignV,
    "orientation": py2tosc.Orientation,
    "buttonType": py2tosc.ButtonType,
    "outlineStyle": py2tosc.OutlineStyle,
    "cursorDisplay": py2tosc.CursorDisplay,
    "barDisplay": py2tosc.CursorDisplay,
    "linesDisplay": py2tosc.CursorDisplay,
    "font": py2tosc.Font,
    "response": py2tosc.Response,
    "radioType": py2tosc.RadioType,
    "pointerPriority": py2tosc.PointerPriority,
}


def name_of(enum, value):
    try:
        return enum(value).name, True
    except ValueError:
        return f"UNKNOWN ({value})", False


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    unknown = 0
    for arg in argv:
        path = Path(arg)
        try:
            doc = py2tosc.load(path)
        except py2tosc.FormatError as exc:
            print(f"{path}: {exc}")
            return 3

        print(f"\n{path}  lexml {doc.version}")
        for control in doc.walk():
            rows = []
            for key, enum in ENUMS.items():
                prop = control.properties.get(key)
                if prop is None:
                    continue
                label, ok = name_of(enum, prop.value)
                unknown += not ok
                rows.append(f"      {key:<16} {prop.value:<4} {label}")
            if rows:
                label = control.get("name") or "<unnamed>"
                print(f"  {control.control_type.value:<8} {label}")
                print("\n".join(rows))

        pads = [
            m
            for c in doc.walk()
            for m in c.messages
            if isinstance(m, py2tosc.GamepadMessage)
        ]
        midi = [
            m
            for c in doc.walk()
            for m in c.messages
            if isinstance(m, py2tosc.MidiMessage)
        ]
        for kind, messages, enum, field in (
            ("MIDI", midi, py2tosc.MidiType, "message.type"),
            ("gamepad", pads, py2tosc.GamepadInput, "type"),
        ):
            spellings = set()
            for m in messages:
                spellings.add(m.message.type if field != "type" else m.type)
            for spelling in sorted(spellings):
                known = spelling in {str(x) for x in enum}
                unknown += not known
                mark = "" if known else "   <-- not in the enum"
                print(f"  {kind:<8} type {spelling}{mark}")

    print(f"\n{unknown} value(s) this library cannot name.")
    return 1 if unknown else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
