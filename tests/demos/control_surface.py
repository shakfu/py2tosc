"""Generate a paged MIDI and OSC control surface from a plugin's parameters.

Given a JSON list of parameters -- the kind a DAW or a plugin host will export
-- this builds a fader per parameter, laid out in pages, with each fader bound
both to an OSC address and to a MIDI CC. Nothing about the layout is written by
hand: the parameter list decides how many pages there are and what is on them.

    python tests/demos/control_surface.py tests/data/pro_c_2_fabfilter.json
    python tests/demos/control_surface.py params.json --prefix synth/bank1

The work is `py2tosc.surface`, which lives in the package rather than here
because `py2tosc build` needs it too. What this file shows is the shape of
using it: read a file, hand over the parameters, save what comes back. The
same thing from the command line is one line:

    py2tosc build tests/data/pro_c_2_fabfilter.json

Two things about real parameter data drive that module's design, and are worth
knowing before pointing it at your own file. Names are meant for people, so
they contain spaces and repeat, while an OSC address can have neither -- each
control gets a slug for its name and keeps the original text on its caption.
And a plugin's parameter *index* is a host identifier rather than a controller
number: this file's indices run to 182, well past the 127 a CC allows, so the
CC comes from the parameter's position unless an entry names one.

Compare `from_json.py`, which is the smallest version of this idea: one row of
faders, OSC only, using the eager `py2tosc.layout` functions.
"""

import argparse
import json
from pathlib import Path

from py2tosc import surface


def main(parameters_path: Path, output_path: Path, prefix: str = "") -> None:
    parameters = surface.read(json.loads(parameters_path.read_text()))
    doc = surface.build(parameters, prefix=prefix or parameters_path.stem)

    for issue in doc.validate():
        print(f"  {issue}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    pages = len(doc.find(type="PAGER").children)
    print(
        f"{len(parameters)} parameters -> {pages} pages, "
        f"{len(list(doc.walk()))} controls -> {output_path}"
    )


def parse_args() -> argparse.Namespace:
    """Read the command line, so a missing path is a message and not a crash."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "parameters", type=Path, help="a JSON list of plugin parameters"
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="the OSC namespace; defaults to the parameter file's name",
    )
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
    main(args.parameters, args.output, args.prefix)
