#!/usr/bin/env python3
"""Draw the review set: an SVG and the `.tosc` it was drawn from, side by side.

    uv run python scripts/render_review.py

`py2tosc.to_svg` has no oracle -- TouchOSC is the only thing that knows what a
layout really looks like, and it cannot be scripted. So the check is a person
opening the two and comparing them, and this exists to make that cheap: every
entry writes both files under one stem, plus an `index.html` that shows each
picture next to a link to the layout it came from.

Everything it writes goes under `build/`, which is not tracked. Nothing here is
part of the package.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import py2tosc
from py2tosc import ui
from py2tosc.enums import ControlType

ROOT = Path(__file__).resolve().parent.parent

#: Layouts and descriptions already in the tree, and what each is here to show.
SOURCES = [
    ("tests/data/controls.tosc", "one of every control type, as the editor drew it"),
    ("tests/data/enums.tosc", "the shape and enum settings"),
    ("tests/examples/hexkeys.tosc", "hexagons, and a lot of them"),
    ("tests/data/pagers.tosc", "three pagers, pages fanned out"),
    ("tests/data/grid-faders.tosc", "a GRID of faders"),
    ("tests/examples/simple_mk2.tosc", "editor-written; four pages side by side"),
    ("tests/examples/multi_xy.tosc", "XY controls"),
    ("tests/data/mixer.ui.json", "a description, every control at the default colour"),
    ("tests/data/schemas/schema-3.ui.json", "two faders and two buttons"),
]


def every_kind() -> py2tosc.Document:
    """One of every control type, with nothing coloured.

    The harshest case for the half of the promise that costs something. A
    layout the combinators build carries one default colour throughout, so
    every control is the same grey and the only thing left to say what a
    control *is* is the mark drawn on it.
    """
    tiles = []
    for kind in ControlType:
        if kind is ControlType.PAGER:
            continue  # a pager with no pages is nothing to look at
        if kind is ControlType.GRID:
            control = ui.grid(ControlType.BUTTON, columns=2, rows=2, name="grid")
        else:
            control = py2tosc.Control(kind, name=kind.value.lower())
            if kind in (ControlType.LABEL, ControlType.TEXT):
                control.values[0].default = kind.value.title()
            if kind is ControlType.RADIO:
                control.set("steps", 5)
        tiles.append(ui.labelled(control, kind.value))

    root = ui.tiles(
        *tiles, columns=4, gap=14, pad=14, name="kinds", frame=(0, 0, 820, 620)
    )
    return py2tosc.Document(root=root).resolve()


def combinators() -> py2tosc.Document:
    """A layout the combinators built, with the faders at rising values.

    The leftmost fader sits at zero, which is the case that used to draw as an
    empty box before the bar kept a stroke that does not scale.
    """
    faders = [py2tosc.fader(name=f"ch{n}", color="#e76f51") for n in range(1, 9)]
    for index, fader in enumerate(faders):
        fader.values[0].default = index / (len(faders) - 1)

    buttons = [py2tosc.button(name=f"m{n}", color="#2a9d8f") for n in range(1, 9)]
    radios = [
        py2tosc.radio(name=f"r{n}", steps=4, color="#264653") for n in range(1, 5)
    ]
    root = ui.column(
        ui.row(*faders, gap=6),
        ui.row(*buttons, gap=6),
        ui.tiles(*radios, columns=4, gap=8),
        sizes=[3, 1, 1],
        gap=10,
        pad=12,
        name="root",
        frame=(0, 0, 900, 520),
    )
    return py2tosc.Document(root=root).resolve()


BUILT = [
    ("every-kind", every_kind, "one of every type, nothing coloured"),
    ("built-by-combinators", combinators, "faders from 0 to 1; the first is zero"),
]


def _draw(doc: py2tosc.Document, stem: Path, args: argparse.Namespace) -> None:
    """The picture, and a page around it when one was asked for."""
    stem.with_suffix(".svg").write_text(py2tosc.to_svg(doc, clip=args.clip))
    if args.html:
        stem.with_suffix(".html").write_text(py2tosc.to_html(doc, clip=args.clip))


def page(entries: list[tuple[str, str, int, list[str]]]) -> str:
    """The index, with each picture beside the layout it was drawn from."""
    figures = [
        (
            f'<figure><img src="{stem}.svg" alt="{stem}">'
            f"<figcaption><b>{stem}</b> -- {note} ({count} controls) "
            f'&middot; <a href="{stem}.tosc" download>open the .tosc</a>'
            + ("".join(f"<br><i>{issue}</i>" for issue in issues))
            + "</figcaption></figure>"
        )
        for stem, note, count, issues in entries
    ]
    style = (
        "body{font:14px system-ui;margin:2rem;background:#fafafa}"
        "figure{margin:0 0 2.5rem}"
        "img{max-width:100%;border:1px solid #ccc;background:#fff}"
        "figcaption{margin-top:.5rem;color:#444}"
        "i{color:#a60}"
    )
    return (
        "<!doctype html><meta charset=utf-8>"
        "<title>py2tosc render review</title>"
        f"<style>{style}</style>"
        "<h1>py2tosc <code>to_svg</code> -- review</h1>"
        "<p>Each picture, and the layout it was drawn from. Open the "
        "<code>.tosc</code> in TouchOSC and compare.</p>" + "".join(figures)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="render_review.py",
        description=(
            "Write an SVG and its .tosc for each review layout, plus an index."
        ),
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "build" / "svg",
        help="where to write (default: build/svg)",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="write pages rather than bare pictures",
    )
    parser.add_argument(
        "--clip",
        action="store_true",
        help="cut controls off at their parent's edge, as TouchOSC does",
    )
    args = parser.parse_args(argv)

    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    entries = []
    for stem, build, note in BUILT:
        doc = build()
        _draw(doc, out / stem, args)
        doc.save(out / f"{stem}.tosc")
        entries.append(
            (stem, note, len(list(doc.walk())), [str(i) for i in doc.validate()])
        )

    for name, note in SOURCES:
        source = ROOT / name
        doc = py2tosc.load(source)
        stem = source.name.split(".")[0]
        _draw(doc, out / stem, args)
        if source.suffix == ".tosc":
            # Copied rather than re-saved, so what is opened is the file the
            # picture was drawn from rather than a round trip of it.
            shutil.copyfile(source, out / f"{stem}.tosc")
        else:
            doc.save(out / f"{stem}.tosc")
        entries.append(
            (stem, note, len(list(doc.walk())), [str(i) for i in doc.validate()])
        )

    (out / "index.html").write_text(page(entries))

    for stem, _, count, issues in entries:
        flag = f"  <-- {len(issues)} issue(s)" if issues else ""
        print(f"{stem:<24} {count:>4} controls{flag}")
    print(f"\n{len(entries)} pairs in {out}")
    print(f"open {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
