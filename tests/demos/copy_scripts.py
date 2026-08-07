"""Copy one control's Lua script onto every child of another group.

python tests/demos/copy_scripts.py tests/data/test.tosc source target
"""

import argparse
from pathlib import Path

import py2tosc


def main(
    input_path: str, output_path: Path, source_name: str, target_name: str
) -> None:
    doc = py2tosc.load(input_path)

    source = doc.find(source_name)
    if source is None:
        raise SystemExit(f"no control named {source_name!r}")

    script = source.get("script", "")
    target = doc.find(target_name)
    if target is None:
        raise SystemExit(f"no control named {target_name!r}")

    for child in target.children:
        child.script = script

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output_path)
    print(
        f"copied {len(script)} characters onto {len(target)} controls -> {output_path}"
    )


def parse_args() -> argparse.Namespace:
    """Read the command line, so a missing path is a message and not a crash."""
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input", help="the layout to read")
    parser.add_argument("source", help="the control whose script is copied")
    parser.add_argument("target", help="the group whose children receive it")
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
    main(args.input, args.output, args.source, args.target)
