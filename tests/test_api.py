"""The public API and the API reference must describe the same thing.

Before this existed there were three answers to "what is public": `__all__`
listed 48 names, `docs/api/` documented 72 objects, and every internal module
was importable regardless. The disagreement was harmless while the version was
below 1.0 and becomes a compatibility question the moment it is not, which is
what these tests are here to prevent.
"""

import re

import pytest
from _corpus import PROJECT_ROOT

import py2tosc

#: Documented by their members rather than by a `::: py2tosc.<name>` directive
#: of their own. `py2tosc.ui.row` appears in the reference; `py2tosc.ui` does
#: not, and should not, since the module docstring is not the interesting part.
SUBMODULES = {"json_codec", "layout", "properties", "surface", "ui", "ui_json"}


def documented():
    """Every object the API reference renders, by dotted name."""
    api = PROJECT_ROOT / "docs" / "api"
    if not api.is_dir():
        pytest.skip("running against an installed package, not a source tree")

    names = set()
    for page in api.glob("*.md"):
        names |= set(re.findall(r"^:::+\s+(py2tosc[\w.]*)", page.read_text(), re.M))
    assert names, "found no ::: directives; the parser is wrong, not the docs"
    return names


def test_everything_exported_is_documented():
    """A name in `__all__` is a promise, so the reference has to explain it."""
    exported = {
        f"py2tosc.{name}"
        for name in py2tosc.__all__
        if not name.startswith("__") and name not in SUBMODULES
    }
    missing = sorted(exported - documented())
    assert not missing, f"exported but undocumented: {missing}"


def test_everything_documented_is_reachable():
    """The reference may only name things a reader can actually get to.

    This is the check that `py2tosc.surface` failed: the page documented
    `py2tosc.surface.read` while the package bound only `layout` and `ui` as
    attributes, so following the reference raised `AttributeError`.
    """
    for name in sorted(documented()):
        target = py2tosc
        for part in name.split(".")[1:]:
            assert hasattr(target, part), f"{name}: no attribute {part!r}"
            target = getattr(target, part)


def test_submodules_named_in_the_reference_are_exported():
    """`py2tosc.ui.row` in the docs implies `py2tosc.ui` after a bare import."""
    for name in documented():
        parts = name.split(".")
        if len(parts) > 2:
            assert parts[1] in py2tosc.__all__, (
                f"{name} is documented, but {parts[1]!r} is not in __all__"
            )


def test_all_is_sorted_and_has_no_duplicates():
    """`__all__` is sorted rather than grouped; see the note in __init__.py."""
    assert py2tosc.__all__ == sorted(py2tosc.__all__)
    assert len(py2tosc.__all__) == len(set(py2tosc.__all__))


def test_private_modules_are_not_documented():
    """Importable is not the same as public. `_geometry` is reachable and is not.

    Nothing stops a caller importing `py2tosc._geometry`, and nothing should:
    the leading underscore is the whole convention. What matters is that the
    reference never points at one, since that is what turns a private module
    into a promise.
    """
    private = sorted(n for n in documented() if any(p.startswith("_") for p in n.split(".")))
    assert not private, f"the API reference names private objects: {private}"
