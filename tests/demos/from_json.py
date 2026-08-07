"""Build a layout of faders from a JSON list of plugin parameters.

Each fader is named after its parameter and sends to /<group>/<fader>.

    python tests/demos/from_json.py tests/data/pro_c_2_fabfilter.json out.tosc
"""

import json
import sys

import py2tosc
from py2tosc import OscMessage, layout, ui

LIMIT = 10


def parameter_message() -> OscMessage:
    """An OSC address built from the parent's name and the control's own."""
    return ui.osc("/{parent.name}/{name}")


def main(json_path: str, output_path: str) -> None:
    with open(json_path) as file:
        parameters = json.load(file)[:LIMIT]

    doc = py2tosc.Document.new(frame=(0, 0, 1920, 1080), name="template")

    controls = py2tosc.group(name="Controls", frame=(420, 0, 1080, 1080))
    doc.add(controls)

    faders = layout.row(
        controls, "FADER", sizes=len(parameters), colors=("#0000ff", "#ff0000")
    )
    for fader, parameter in zip(faders, parameters):
        fader.name = parameter["name"]
        fader.messages.append(parameter_message())

    doc.save(output_path)
    print([fader.name for fader in faders])


if __name__ == "__main__":
    main(*sys.argv[1:3])
