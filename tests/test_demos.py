"""The demo scripts, run for real.

These are the programs the documentation embeds, so if they stop working the
documentation is wrong. Each is executed as a subprocess exactly the way the
docs say to invoke it, and its output is loaded back to prove it produced a
layout rather than merely exiting zero.
"""

import subprocess
import sys

import pytest

import py2tosc
from _corpus import DATA, DEMOS

DEMO_SCRIPTS = sorted(DEMOS.glob("*.py"))


def run(script: str, *args) -> subprocess.CompletedProcess:
    """Run a demo the way its documentation says to."""
    result = subprocess.run(
        [sys.executable, str(DEMOS / script), *map(str, args)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{script} failed:\n{result.stderr}"
    return result


def test_every_demo_script_is_covered():
    """A new demo must come with a test, or this fails."""
    covered = {
        "custom_property.py",
        "copy_scripts.py",
        "from_json.py",
        "image_converter.py",
        "numpad.py",
    }
    assert {p.name for p in DEMO_SCRIPTS} == covered


@pytest.mark.parametrize("script", DEMO_SCRIPTS, ids=lambda p: p.name)
def test_every_demo_compiles(script):
    """Cheap syntax and import check, so a broken demo fails fast."""
    subprocess.run([sys.executable, "-m", "py_compile", str(script)], check=True)


def test_custom_property(tmp_path):
    out = tmp_path / "custom.tosc"
    result = run("custom_property.py", DATA / "test2.tosc", out)

    assert "Craig" in result.stdout
    doc = py2tosc.load(out)
    assert doc.root.get("CustomProperty") == "Craig"
    # the rest of the layout is untouched
    assert len(list(doc.walk())) == len(list(py2tosc.load(DATA / "test2.tosc").walk()))


def test_copy_scripts(tmp_path):
    out = tmp_path / "scripts.tosc"
    run("copy_scripts.py", DATA / "test.tosc", out, "source", "target")

    doc = py2tosc.load(out)
    source = doc.find("source")
    target = doc.find("target")

    assert source.get("script")
    assert target.children
    assert all(c.get("script") == source.get("script") for c in target.children)


def test_copy_scripts_reports_a_missing_control(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(DEMOS / "copy_scripts.py"),
            str(DATA / "test.tosc"),
            str(tmp_path / "out.tosc"),
            "nonexistent",
            "target",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "nonexistent" in result.stderr


def test_from_json(tmp_path):
    out = tmp_path / "fromjson.tosc"
    result = run("from_json.py", DATA / "Pro-C 2 (FabFilter).json", out)

    assert "Threshold" in result.stdout

    doc = py2tosc.load(out)
    faders = doc.find_all(type="FADER")
    assert len(faders) == 10
    assert [f.name for f in faders][:3] == ["Style", "Threshold", "Ratio"]

    # each fader sends to /<parent name>/<own name>
    assert all(f.messages for f in faders)
    path = faders[0].messages[0].path
    assert [p.value for p in path] == ["/", "parent.name", "/", "name"]

    # laid out edge to edge across the group, no gaps
    group = doc.find("Controls")
    edges = [(f.frame.x, f.frame.x + f.frame.w) for f in faders]
    assert all(a[1] == b[0] for a, b in zip(edges, edges[1:]))
    assert edges[-1][1] == group.frame.w


def test_image_converter(tmp_path):
    pytest.importorskip("PIL", reason="the image demo needs Pillow")

    out = tmp_path / "image.tosc"
    result = run(
        "image_converter.py", DATA / "test.tosc", out, DATA / "logo.jpg", "canvas"
    )

    assert "boxes" in result.stdout

    doc = py2tosc.load(out)
    # the input layout has boxes of its own, so look only inside the canvas
    boxes = doc.find("canvas").children
    assert len(boxes) > 1000
    # every box the demo drew is 4 points square, with a colour from the image
    assert all(b.control_type is py2tosc.ControlType.BOX for b in boxes)
    assert {(b.frame.w, b.frame.h) for b in boxes} == {(4, 4)}
    assert len({b.color for b in boxes}) > 10


def test_image_converter_reports_a_missing_canvas(tmp_path):
    pytest.importorskip("PIL", reason="the image demo needs Pillow")

    result = subprocess.run(
        [
            sys.executable,
            str(DEMOS / "image_converter.py"),
            str(DATA / "test.tosc"),
            str(tmp_path / "out.tosc"),
            str(DATA / "logo.jpg"),
            "no-such-group",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "no-such-group" in result.stderr


def test_numpad(tmp_path):
    """The most involved demo: nested layouts, a Lua script, and LOCAL wiring."""
    out = tmp_path / "numpad.tosc"
    result = run("numpad.py", out)

    assert "45 controls" in result.stdout
    doc = py2tosc.load(out)

    # every key is a button with a label on top, inside its own cell
    assert len(doc.find_all(type="BUTTON")) == 14
    assert len(doc.find_all(type="LABEL")) == 14

    readout = doc.find("valueLabel")
    assert readout.get("max") == "127"
    assert "onValueChanged" in readout.script

    # the ten digits plus CLR and DEL all drive the readout, nothing else
    wired = {c.name for c in doc.walk() if c.messages}
    assert wired == {*"0123456789", "CLR", "DEL"}
    assert all(
        m.dst_id == readout.id
        for c in doc.walk()
        for m in c.messages
        if isinstance(m, py2tosc.LocalMessage)
    )


def test_numpad_output_is_a_clean_layout(tmp_path):
    out = tmp_path / "numpad.tosc"
    run("numpad.py", out)
    assert py2tosc.load(out).validate() == []
