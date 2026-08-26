"""The standalone checker, against the reader it stands in for.

`scripts/check_json.py` exists to be copied into a project that writes these
files and does not have py2tosc, which makes it a second implementation of the
same tables. Two things have to hold for that to be worth having, and both are
checked here.

The tables must not drift, which is what regenerating and comparing does. And
the checker must be *conservative*: everything it calls an error, py2tosc has
to refuse as well. A false positive is the failure that would matter, because
it would send someone looking for a defect in a file that is fine.

The reverse is deliberately not required. The checker sees neither geometry nor
whether a value coerces, so a description it passes may still not build, and
its own docstring says so.
"""

import ast
import importlib.util
import json
import subprocess
import sys

import pytest

import py2tosc
from _corpus import CORPUS, DATA, PROJECT_ROOT
from py2tosc import ui_json
from py2tosc.errors import FormatError

SCRIPTS = PROJECT_ROOT / "scripts"
CHECKER = SCRIPTS / "check_json.py"
GENERATOR = SCRIPTS / "make_check_json.py"

#: Every description in the corpus, which is what the checker is for.
DESCRIPTIONS = sorted(DATA.glob("*.ui.json"))


def _module():
    """The checker, loaded the way the project it is copied into would."""
    spec = importlib.util.spec_from_file_location("check_json", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_json = _module()


def errors(data):
    return [line for line in check_json.check(data) if line.startswith("error")]


def warnings(data):
    return [line for line in check_json.check(data) if line.startswith("warning")]


def described(root, **envelope):
    return {"format": ui_json.DIALECT, "root": root, **envelope}


# -- it stands alone ---------------------------------------------------------


def test_the_checker_imports_nothing_but_the_standard_library():
    """The whole point: a project that copies this file needs nothing else.

    Run in a subprocess with the source tree off the path, so importing
    py2tosc would fail rather than quietly succeed from the checkout.
    """
    result = subprocess.run(
        [sys.executable, "-c", "import check_json; print(check_json.__name__)"],
        cwd=SCRIPTS,
        capture_output=True,
        text=True,
        env={"PATH": "", "PYTHONPATH": "", "PYTHONHOME": ""},
    )
    assert result.returncode == 0, result.stderr
    assert "check_json" in result.stdout


def test_the_checker_imports_only_modules_that_ship_with_python():
    """Read off the imports rather than the text, since `py2tosc.ui` is data.

    The dialect's own name appears in the tables, so grepping would fail on a
    file that is fine. What matters is what it imports.
    """
    tree = ast.parse(CHECKER.read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "a relative import needs a package around it"
            imported.add((node.module or "").split(".")[0])
    assert imported <= set(sys.stdlib_module_names) | {"__future__"}, imported


def test_the_tables_have_not_drifted():
    """The copy against what it was copied from, compared as data.

    Not as text: `json.dumps` and `ruff format` lay the same literal out
    differently, so comparing the file byte for byte would fail every time it
    was formatted, which trains people to regenerate without reading.
    """
    spec = importlib.util.spec_from_file_location("make_check_json", GENERATOR)
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    assert check_json.TABLES == generator.tables(), (
        "the checker's tables no longer match py2tosc; run "
        "`uv run python scripts/make_check_json.py` and commit the result"
    )


# -- it agrees with the reader -----------------------------------------------


@pytest.mark.parametrize("path", DESCRIPTIONS, ids=lambda p: p.name)
def test_a_description_that_builds_has_no_errors(path):
    """The no-false-positive check, on every description in the corpus."""
    data = json.loads(path.read_text())
    ui_json.build(data)  # the reader accepts it, so the checker has to
    assert errors(data) == []


@pytest.mark.parametrize("path", sorted(CORPUS), ids=lambda p: p.name)
def test_a_layout_that_round_trips_has_no_errors(path):
    """The same, for the faithful encoding, over every layout in the corpus."""
    data = json.loads(py2tosc.to_json(py2tosc.load(path)))
    assert errors(data) == []


#: Descriptions py2tosc refuses, each for a reason the checker can see too.
REFUSED = [
    ({"row": [{"fader": "a", "gpa": 4}]}, "gpa"),
    ({"row": [{"fader": "a", "column": []}]}, "both name something"),
    ({"row": [{"nothing": "here"}]}, "names a control or a layout"),
    ({"row": [{"repeat": 0, "of": {"fader": "a"}}]}, "less than 1"),
    ({"row": [{"repeat": 2, "each": [], "of": {"fader": "a"}}]}, "not both"),
    ({"row": [{"repeat": 1, "of": {"fader": "$j"}}]}, "$j is not one of the names"),
    ({"row": [{"repeat": 1, "off": {"fader": "a"}}]}, "did you mean 'of'?"),
    ({"row": [{"fader": "a", "messages": [{"osc": 7}]}]}, "osc takes an address"),
    ({"row": [{"fader": "a", "messages": [{"nope": 1}]}]}, "a binding is one of"),
    ({"row": [{"grid": "SLIDER", "columns": 2, "rows": 2}]}, "not a control type"),
    ({"row": [{"labelled": {"fader": "a"}}]}, "needs a caption"),
    ({"row": [{"inset": {"fader": "a"}}]}, "needs a `by`"),
    ({"row": [{"each": [{"i": 1}], "of": {"fader": "a"}}]}, "own counter"),
    ({"row": [{"each": [{"n": [1]}], "of": {"fader": "$n"}}]}, "should be a string"),
    (
        {"row": [{"each": [{"k": "a"}], "of": {"case": "$k", "when": {"b": {"fader": "x"}}}}]},
        "no branch is written for it",
    ),
    (
        {"row": [{"each": [{"k": "a"}], "of": {"case": "$k", "when": {"a": {"nope": 1}}}}]},
        "names a control or a layout",
    ),
    ({"row": [{"each": [{"k": "a"}], "of": {"case": "$k"}}]}, "'when' is missing"),
    ({"row": [{"each": [{"k": "a"}], "of": {"case": "$k", "when": {}}}]}, "needs a branch"),
    # schema 3: a choice among children or among bindings
    (
        {"row": [{"each": [{"k": "a"}], "of": {"fader": "x", "messages": [
            {"case": "$k", "when": {"a": {"osc": "/x"}, "b": {"nope": 1}}}]}}]},
        "when['b']: a binding is one of",
    ),
    (
        {"row": [{"each": [{"k": "a"}], "of": {"row": [
            {"case": "$k", "when": {"a": {"fader": "x"}, "b": {"nope": 1}}}]}}]},
        "when['b']: nothing here names a control",
    ),
    (
        {"row": [{"case": "$k", "when": {"a": {"fader": "x"}}}]},
        "nothing here is inside a repeat",
    ),
]


@pytest.mark.parametrize("root, message", REFUSED, ids=[m for _, m in REFUSED])
def test_what_the_checker_refuses_the_reader_refuses_too(root, message):
    """The contract: an error here is an error there, and says the same thing."""
    data = described(root)
    with pytest.raises(FormatError) as caught:
        ui_json.build(data)

    found = errors(data)
    assert found, f"the reader said {caught.value}, the checker said nothing"
    assert any(message in line for line in found), found


def test_the_checker_may_pass_what_the_reader_still_refuses():
    """Stated rather than worked around: it sees shape, not arithmetic.

    A layout that cannot divide its space is a real refusal the checker has no
    way to reach, since nothing here resolves a frame.
    """
    data = described({"tiles": [{"fader": "a"}], "columns": 0})
    with pytest.raises(FormatError):
        ui_json.build(data)
    assert errors(data) == []


# -- what it says about the stamp --------------------------------------------


CHOICE = {
    "row": [
        {
            "each": [{"k": "a", "n": "x"}, {"k": "b", "n": "y"}],
            "of": {
                "case": "$k",
                "when": {"a": {"fader": "$n"}, "b": {"button": "$n"}},
            },
        }
    ]
}


def test_required_schema_matches_the_library():
    """The two implementations of the same table, on the same descriptions."""
    for data in [described(CHOICE), described({"row": [{"fader": "c$i", "repeat": 2}]})]:
        assert check_json.required_schema(data) == ui_json.required_schema(data)


def test_a_description_that_understates_its_schema_is_a_warning():
    """The generator's mistake, and the reason this file is worth copying."""
    found = warnings(described(CHOICE, schema=1))
    assert any("declares schema 1 and uses schema 2" in line for line in found)
    assert errors(described(CHOICE, schema=1)) == []


def test_a_description_that_stamps_nothing_is_a_warning_only_when_it_matters():
    assert any("carries no schema key" in line for line in warnings(described(CHOICE)))
    plain = described({"row": [{"fader": "c$i", "repeat": 2}]})
    assert check_json.check(plain) == []


def test_a_description_stamped_right_is_clean():
    assert check_json.check(described(CHOICE, schema=2)) == []


def test_a_schema_newer_than_the_tables_says_to_regenerate():
    """The one answer a copied file has to give about its own age."""
    found = warnings(described(CHOICE, schema=99))
    assert any("regenerate this checker" in line for line in found)


# -- the command line --------------------------------------------------------


def run(*argv):
    result = subprocess.run(
        [sys.executable, str(CHECKER), *[str(a) for a in argv]],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def test_the_command_line_reports_a_clean_file(tmp_path):
    code, out = run(DATA / "mixer.ui.json")
    assert code == 0
    assert "clean" in out


def test_the_command_line_exits_one_on_an_error(tmp_path):
    path = tmp_path / "bad.ui.json"
    path.write_text(json.dumps(described({"row": [{"fader": "a", "gpa": 1}]})))
    code, out = run(path)
    assert code == 1
    assert "gpa" in out


def test_the_command_line_exits_two_on_a_file_it_cannot_read(tmp_path):
    path = tmp_path / "junk.json"
    path.write_text("{not json")
    code, out = run(path)
    assert code == 2
    assert "not a readable layout" in out


def test_the_command_line_says_how_to_use_it():
    """argparse exits 2 on a command line it cannot parse, which is the code
    this already reserves for "nothing was learned about any layout"."""
    code, out = run()
    assert code == 2
    assert "usage:" in out

    code, out = run("--help")
    assert code == 0
    assert "exit codes:" in out


def test_the_command_line_says_nothing_about_a_clean_file_when_quiet():
    code, out = run("--quiet", DATA / "mixer.ui.json")
    assert code == 0
    assert out == ""


def test_the_generator_can_report_without_writing():
    """The form a CI step wants, where writing to the checkout is not an answer."""
    before = CHECKER.read_bytes()
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "already current" in result.stdout
    assert CHECKER.read_bytes() == before
