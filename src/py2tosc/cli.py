"""The `py2tosc` command.

Everything the library does is file-shaped -- look at a layout, check it,
convert it, read it back as source, generate one -- and none of it should need
a script written first.

    py2tosc show mixer.tosc
    py2tosc validate mixer.tosc
    py2tosc decompile mixer.tosc
    py2tosc convert mixer.tosc -o mixer.json
    py2tosc build params.json -o surface.tosc

Exit codes separate the two things that can go wrong, because a script that
runs `py2tosc validate` in CI needs to tell "this layout is broken" from "the
path is wrong". Those used to share code 1 and no longer do: 1 is now a
statement about a layout, 2 is the command not having run. That is the same
split `grep`, `diff` and `mypy` make.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

from . import surface, ui_json
from .codegen import to_python
from .control import Control
from .document import Document, load
from .validate import ERROR, WARNING, Issue

__all__ = ["main"]

#: The command did what was asked.
OK = 0

#: The layout was read and is wrong: `validate` found an error in it. This is
#: the only code that says anything about the contents of a file, and the only
#: one that reports a result rather than a malfunction.
INVALID = 1

#: The command could not be carried out: a command line that will not parse, or
#: input that cannot be read. Nothing was learned about any layout.
#:
#: These share a number rather than getting one each because no caller acts on
#: the difference -- both mean a human typed something wrong -- and because it
#: is where every comparable tool puts them. `grep`, `diff` and `mypy` all
#: reserve 1 for "what you asked about is bad" and 2 for "I could not look".
#: argparse also exits 2 of its own accord, before any code here runs.
CANNOT_RUN = 2


def _fail(message: str) -> NoReturn:
    """Report a failure to read the input, and exit.

    `SystemExit` given a string prints it and exits 1, which is the code
    reserved for a layout that has errors. Printing here and exiting with an
    explicit code keeps the message and frees the number.
    """
    print(message, file=sys.stderr)
    raise SystemExit(CANNOT_RUN)


def _load(path: Path) -> Document:
    """Read a layout, turning the usual failures into a message."""
    try:
        return load(path)
    except FileNotFoundError:
        _fail(f"no such file: {path}")
    except (OSError, ValueError) as exc:
        _fail(f"{path}: not a readable layout ({exc})")


def _write(text: str, output: Path | None) -> None:
    """Send generated text to a file, or to stdout when there is none."""
    if output is None:
        sys.stdout.write(text)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text)
    print(f"wrote {output}", file=sys.stderr)


def _tree(control: Control, depth: int, limit: int, prefix: str = "") -> None:
    if limit and depth > limit:
        return
    name = control.get("name")
    frame = tuple(int(v) for v in control.frame)
    label = (
        f"{control.control_type.value:7} {name!r}"
        if name
        else control.control_type.value
    )
    extra = f"  {len(control.children)} children" if control.children else ""
    print(f"{prefix}{label}  {frame}{extra}")
    for child in control.children:
        _tree(child, depth + 1, limit, prefix + "  ")


def show(args: argparse.Namespace) -> int:
    """Say what is in a layout."""
    doc = _load(args.file)
    controls = list(doc.walk())
    types = collections.Counter(c.control_type.value for c in controls)
    messages = collections.Counter(
        type(m).__name__ for c in controls for m in c.messages
    )

    print(f"{args.file}  lexml {doc.version}")
    print(
        f"  {len(controls)} controls: "
        + ", ".join(f"{kind} {count}" for kind, count in types.most_common())
    )
    if messages:
        print(
            f"  {sum(messages.values())} messages: "
            + ", ".join(
                f"{kind[:-7]} {count}" for kind, count in messages.most_common()
            )
        )
    scripts = [c for c in controls if c.has("script")]
    if scripts:
        print(f"  {len(scripts)} scripts")

    print()
    _tree(doc.root, 0, args.depth)
    return OK


def _stamped(path: Path) -> list[Issue]:
    """Warn when a layout description claims a schema below the one it uses.

    Only this dialect can get it wrong. The faithful encoding stamps its own
    envelope, so the number there cannot disagree with the content; a
    description is written by something that is not py2tosc, which makes the
    stamp a claim nothing downstream audits.

    Getting it wrong is not caught by building, because the reader that would
    catch it is by definition new enough to build the file. It is caught by
    whoever opens the file on an older release, and what they see is a message
    about a node rather than about their py2tosc. So this is a warning for the
    producer, and it is worth having only before the file is shipped.
    """
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return []
    if not isinstance(data, dict) or data.get("format") != ui_json.DIALECT:
        return []

    needed = ui_json.required_schema(data)
    declared = data.get("schema")
    if isinstance(declared, bool) or not isinstance(declared, (int, type(None))):
        # `build` has the better complaint about a schema that is not a
        # number, and there is nothing to add to it here.
        return []
    if declared is None:
        # No stamp means "whatever the reader is", which is only wrong once
        # the description needs more than the oldest release would assume.
        if needed == ui_json.SCHEMAS.start:
            return []
        said = "carries no schema key"
    elif declared >= needed:
        return []
    else:
        said = f"declares schema {declared}"

    return [
        Issue(
            WARNING,
            "<envelope>",
            f"the description {said} and uses schema {needed}; a release "
            f"reading only schema {needed - 1} will refuse it with a message "
            f"about a node",
        )
    ]


def validate(args: argparse.Namespace) -> int:
    """Report what TouchOSC will reject or quietly ignore."""
    issues = _stamped(args.file) + _load(args.file).validate()
    for issue in issues:
        print(issue)
    if not issues:
        print(f"{args.file}: clean")
    return INVALID if any(issue.level == ERROR for issue in issues) else OK


def decompile(args: argparse.Namespace) -> int:
    """Write the layout back out as the Python that would build it."""
    _write(to_python(_load(args.file)), args.output)
    return OK


def convert(args: argparse.Namespace) -> int:
    """Rewrite a layout in another format, chosen by the output's extension."""
    doc = _load(args.file)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(args.output)
    print(f"wrote {args.output}", file=sys.stderr)
    return OK


def _size(text: str) -> tuple[int, int]:
    """Read a `WIDTHxHEIGHT` canvas, so a typo is a message and not a crash."""
    parts = text.lower().replace(",", "x").split("x")
    try:
        width, height = (int(part) for part in parts)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"{text!r} is not a size; write it as WIDTHxHEIGHT, such as 568x320"
        ) from None
    if width < 1 or height < 1:
        raise argparse.ArgumentTypeError(f"{text!r} has a side of no width")
    return width, height


def build(args: argparse.Namespace) -> int:
    """Generate a control surface from a list of parameters."""
    try:
        payload = json.loads(args.parameters.read_text())
    except FileNotFoundError:
        _fail(f"no such file: {args.parameters}")
    except UnicodeDecodeError:
        _fail(
            f"{args.parameters}: not text, so not a parameter list -- "
            f"`build` takes JSON, not a layout"
        )
    except json.JSONDecodeError as exc:
        _fail(f"{args.parameters}: not valid JSON ({exc})")

    try:
        parameters = surface.read(payload)
        doc = surface.build(
            parameters,
            prefix=args.prefix or args.parameters.stem,
            midi=not args.osc_only,
            osc=not args.midi_only,
            columns=args.columns,
            rows=args.rows,
            frame=(0, 0, *args.size),
        )
    except (TypeError, ValueError) as exc:
        _fail(f"{args.parameters}: {exc}")

    output = args.output or Path("build") / f"{args.parameters.stem}.tosc"
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    pager = doc.find(type="PAGER")
    pages = len(pager.children) if pager is not None else 1
    print(
        f"{len(parameters)} parameters -> {pages} page{'s' * (pages != 1)}, "
        f"{len(list(doc.walk()))} controls -> {output}"
    )
    return OK


def parser() -> argparse.ArgumentParser:
    """The whole command line, so it can be tested without running it."""
    root = argparse.ArgumentParser(
        prog="py2tosc",
        description="Generate and edit TouchOSC layouts.",
    )
    commands = root.add_subparsers(dest="command", required=True, metavar="COMMAND")

    look = commands.add_parser("show", help="say what is in a layout")
    look.add_argument("file", type=Path, help="the layout to read")
    look.add_argument(
        "--depth",
        type=int,
        default=2,
        help="how deep to print the tree, 0 for all of it (default: %(default)s)",
    )
    look.set_defaults(run=show)

    check = commands.add_parser(
        "validate", help="report what TouchOSC will reject or ignore"
    )
    check.add_argument("file", type=Path, help="the layout to check")
    check.set_defaults(run=validate)

    source = commands.add_parser(
        "decompile", help="write the layout out as the Python that builds it"
    )
    source.add_argument("file", type=Path, help="the layout to read")
    source.add_argument(
        "-o", "--output", type=Path, help="where to write it (default: stdout)"
    )
    source.set_defaults(run=decompile)

    swap = commands.add_parser(
        "convert",
        help="rewrite a layout as .tosc, .xml or .json, whichever the output is",
    )
    swap.add_argument(
        "file", type=Path, help="the layout to read, in any of the three formats"
    )
    swap.add_argument(
        "-o", "--output", type=Path, required=True, help="where to write it"
    )
    swap.set_defaults(run=convert)

    make = commands.add_parser(
        "build", help="generate a control surface from a list of parameters"
    )
    make.add_argument(
        "parameters",
        type=Path,
        help='JSON: ["Threshold", ...] or [{"name": "Threshold", "cc": 20}, ...]',
    )
    make.add_argument(
        "-o",
        "--output",
        type=Path,
        help="where to write it (default: build/<parameters>.tosc)",
    )
    make.add_argument(
        "--prefix", help="the OSC namespace (default: the parameter file's name)"
    )
    make.add_argument(
        "--columns",
        type=int,
        default=surface.COLUMNS,
        help="controls across each page (default: %(default)s)",
    )
    make.add_argument(
        "--rows",
        type=int,
        default=surface.ROWS,
        help="controls down each page (default: %(default)s)",
    )
    make.add_argument(
        "--size",
        type=_size,
        default=surface.SIZE,
        metavar="WxH",
        help="the design canvas, which TouchOSC scales to the screen "
        f"(default: {surface.SIZE[0]}x{surface.SIZE[1]})",
    )
    bindings = make.add_mutually_exclusive_group()
    bindings.add_argument("--midi-only", action="store_true", help="no OSC addresses")
    bindings.add_argument("--osc-only", action="store_true", help="no MIDI bindings")
    make.set_defaults(run=build)

    return root


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    Args:
        argv: Arguments, or `None` to take them from `sys.argv`.

    Returns:
        The exit code.
    """
    args = parser().parse_args(argv)
    return int(args.run(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
