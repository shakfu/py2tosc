"""Build a layout of faders from a JSON list of plugin parameters.

Each fader is named after its parameter and sends to /<group>/<fader>.

    python tests/demos/from_json.py tests/data/pro_c_2_fabfilter.json
"""

import argparse
import json
from pathlib import Path

import py2tosc
from py2tosc import OscMessage, layout, ui

LIMIT = 10


def parameter_message() -> OscMessage:
    """An OSC address built from the parent's name and the control's own."""
    return ui.osc("/{parent.name}/{name}")


def main(json_path: str, output_path: Path) -> None:
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    print([fader.name for fader in faders])


def parse_args() -> argparse.Namespace:
    """Read the command line, so a missing path is a message and not a crash."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("parameters", help="a JSON list of plugin parameters")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("build") / f"{Path(__file__).stem}.tosc",
        help="where to write the layout (default: %(default)s)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(args.parameters, args.output)
