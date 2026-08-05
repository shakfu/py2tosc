"""Copy one control's Lua script onto every child of another group.

    python tests/demos/copy_scripts.py tests/data/test.tosc out.tosc source target
"""

import sys

import py2tosc


def main(input_path: str, output_path: str, source_name: str, target_name: str) -> None:
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

    doc.save(output_path)
    print(f"copied {len(script)} characters onto {len(target)} controls -> {output_path}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
