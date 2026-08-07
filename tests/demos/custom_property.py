"""Add a custom property to a layout's root node.

TouchOSC keeps properties it does not recognise and exposes them to Lua, which
makes them a place to store configuration a layout needs to remember.

    python tests/demos/custom_property.py tests/data/test2.tosc
"""

import argparse
from pathlib import Path

import py2tosc


def main(input_path: str, output_path: Path) -> None:
    doc = py2tosc.load(input_path)

    # On the root node, so every control can reach it as self.parent.<key>.
    doc.root.set("CustomProperty", "Craig")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    print(f"CustomProperty = {doc.root.get('CustomProperty')!r} -> {output_path}")


def parse_args() -> argparse.Namespace:
    """Read the command line, so a missing path is a message and not a crash."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="the layout to read")
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
    main(args.input, args.output)
