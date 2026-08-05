"""Add a custom property to a layout's root node.

TouchOSC keeps properties it does not recognise and exposes them to Lua, which
makes them a place to store configuration a layout needs to remember.

    python tests/demos/custom_property.py tests/data/test2.tosc out.tosc
"""

import sys

import py2tosc


def main(input_path: str, output_path: str) -> None:
    doc = py2tosc.load(input_path)

    # On the root node, so every control can reach it as self.parent.<key>.
    doc.root.set("CustomProperty", "Craig")

    doc.save(output_path)
    print(f"CustomProperty = {doc.root.get('CustomProperty')!r} -> {output_path}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
