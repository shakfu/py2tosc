#!/usr/bin/env python3
"""Regenerate the tables inside `scripts/check_json.py`.

    uv run python scripts/make_check_json.py

The checker is a standalone file for people who do not have py2tosc, which
means the tables it checks against are a copy, and a copy is a thing that
drifts. This is the one place that copy is made, from the same objects the
reader itself uses -- no table is retyped here, every one is read off the live
module -- and `tests/test_check_json.py` fails when the committed file no
longer matches what this produces.

Only the block between the two markers is rewritten. Everything else in the
checker is ordinary hand-written source, linted and typechecked like the rest.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

from py2tosc import json_codec, ui_json
from py2tosc.defaults import allowed_properties, default_values_for
from py2tosc.enums import ControlType, TriggerCondition
from py2tosc.messages import Value
from py2tosc.properties import KNOWN_TYPES

OPEN = "# --- generated tables: do not edit, see scripts/make_check_json.py ----------"
CLOSE = "# --- end generated tables ---------------------------------------------------"

CHECKER = Path(__file__).resolve().parent / "check_json.py"


def tables() -> dict[str, Any]:
    """Every table the checker needs, read off py2tosc rather than retyped."""
    return {
        "ui": {
            "dialect": ui_json.DIALECT,
            "schemas": list(ui_json.SCHEMAS),
            "envelope_keys": sorted(ui_json._ENVELOPE_KEYS),
            "repeat_keys": sorted(ui_json._REPEAT_KEYS | ui_json._CHOICE_KEYS),
            "common_keys": sorted(ui_json._COMMON_KEYS),
            "value_sugar": sorted(ui_json._VALUE_SUGAR),
            "tags": sorted(ui_json._TAGS),
            "ambiguous": sorted(ui_json._AMBIGUOUS),
            "arrange": sorted(ui_json._ARRANGE),
            "options": {k: sorted(v) for k, v in ui_json._OPTIONS.items()},
            "produces": {k: v.value for k, v in ui_json._PRODUCES.items()},
            "control_types": [t.value for t in ControlType],
            "properties": {t.value: sorted(allowed_properties(t)) for t in ControlType},
            "carries": {
                t.value: sorted(k for k, _ in default_values_for(t))
                for t in ControlType
            },
            "messages": {
                k: sorted(v.__kwdefaults__ or {}) for k, v in ui_json._MESSAGES.items()
            },
            "takes": {
                k: [[t.__name__ for t in v[0]], v[1]] for k, v in ui_json._TAKES.items()
            },
            "partials": sorted(ui_json._PARTIALS),
            "partial_args": {k: sorted(v) for k, v in ui_json._PARTIAL_ARGS.items()},
            "value_fields": [f.name for f in fields(Value)],
            "triggers": [t.value for t in TriggerCondition],
        },
        "layout": {
            "format": json_codec.FORMAT,
            "schemas": list(json_codec.SCHEMAS),
            "envelope_keys": sorted(json_codec._ENVELOPE_KEYS),
            "node_keys": sorted(json_codec._NODE_KEYS),
            "control_types": [t.value for t in ControlType],
            "messages": sorted(json_codec._MESSAGES),
            "known_types": dict(sorted(KNOWN_TYPES.items())),
        },
    }


def block() -> str:
    """The generated section, formatted the way the repository writes JSON."""
    body = json.dumps(tables(), indent=4, sort_keys=True)
    return f"{OPEN}\nTABLES: dict[str, Any] = {body}\n{CLOSE}"


def rewrite(text: str) -> str:
    """One checker with its table block replaced."""
    start = text.index(OPEN)
    end = text.index(CLOSE) + len(CLOSE)
    return text[:start] + block() + text[end:]


def committed() -> Any:
    """The tables the checker currently carries, read as data.

    Compared as data rather than as text on purpose: `json.dumps` and `ruff
    format` lay the same literal out differently, so a textual comparison would
    call the file stale every time it was formatted.
    """
    spec = importlib.util.spec_from_file_location("check_json", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TABLES


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="make_check_json.py",
        description="Regenerate the tables inside scripts/check_json.py.",
        epilog=(
            "exit codes: 0 the tables are current or were rewritten, "
            "1 --check found them stale."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="report whether the tables are current and write nothing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Bring the checker's tables back in step with the library.

    Args:
        argv: The arguments, or None to read them from `sys.argv`.

    Returns:
        0 when the tables are current or were rewritten, and 1 when `--check`
        found them stale -- the code a CI step wants, where writing to the
        checkout is not the answer.
    """
    args = _parser().parse_args(argv)
    current = committed() == tables()

    if current:
        print(f"{CHECKER.name}: already current")
        return 0
    if args.check:
        print(
            f"{CHECKER.name}: tables are stale; run "
            f"`uv run python scripts/make_check_json.py`",
            file=sys.stderr,
        )
        return 1

    CHECKER.write_text(rewrite(CHECKER.read_text()))
    print(f"{CHECKER.name}: tables rewritten; run `uv run ruff format scripts/`")
    return 0


if __name__ == "__main__":
    sys.exit(main())
