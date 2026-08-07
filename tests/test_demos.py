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
        "control_surface.py",
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
    result = run("from_json.py", DATA / "pro_c_2_fabfilter.json", out)

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

    # the ten digits, CLR, DEL and SEND drive the readout; the readout itself
    # carries the OSC binding, and nothing else carries anything
    wired = {c.name for c in doc.walk() if c.messages}
    assert wired == {*"0123456789", "CLR", "DEL", "SEND", "valueLabel"}
    assert all(
        m.dst_id == readout.id
        for c in doc.walk()
        for m in c.messages
        if isinstance(m, py2tosc.LocalMessage)
    )


def test_every_numpad_key_is_wired_identically(tmp_path):
    """Each key sends its own name and the script decides what that means.

    Worth pinning, because the alternative is what this demo used to do: CLR
    and DEL carried bespoke messages that wrote a constant somewhere, and DEL's
    was a silent no-op that no test noticed. Uniform wiring makes a key that
    does nothing visible here rather than only in TouchOSC.
    """
    out = tmp_path / "numpad.tosc"
    run("numpad.py", out)
    doc = py2tosc.load(out)

    def shape(control):
        message = control.messages[0]
        trigger = message.triggers[0]
        return (
            message.type,
            message.value,
            message.dst_type,
            message.dst_var,
            trigger.var,
            trigger.condition,
        )

    keys = [c for c in doc.walk() if c.messages and c.name != "valueLabel"]
    assert [len(c.messages) for c in keys] == [1] * 13

    typing = [c for c in keys if c.name != "SEND"]
    assert {shape(c)[:1] + shape(c)[2:] for c in typing} == {
        ("CONSTANT", "VALUE", "text", "x", "RISE")
    }

    # Each key sends its own caption, marked so it cannot be read as a total.
    assert {c.messages[0].value for c in typing} == {
        f"#{c}" for c in [*"0123456789", "CLR", "DEL"]
    }

    # CLR and DEL mean nothing unless the script names them.
    script = doc.find("valueLabel").script
    assert '"CLR"' in script and '"DEL"' in script


def test_a_numpad_key_never_sends_what_the_readout_already_shows(tmp_path):
    """The repeat-keypress defect, pinned.

    Keys land on the very value the readout displays, and TouchOSC reports a
    value only when it changes. Sending a bare caption meant that pressing 7
    while the readout showed 7 was not a change, so the key did nothing. The
    marker keeps a keypress and a total disjoint, whatever the total is.
    """
    out = tmp_path / "numpad.tosc"
    run("numpad.py", out)
    doc = py2tosc.load(out)

    sent = {
        m.value
        for c in doc.walk()
        for m in c.messages
        if isinstance(m, py2tosc.LocalMessage) and m.dst_var == "text"
    }
    assert sent, "no key writes the readout's text"

    # A total is always digits, so nothing a key sends can ever equal one.
    assert all(not value.lstrip("-").isdigit() for value in sent)


def test_numpad_send_pushes_the_total_over_osc(tmp_path):
    """SEND cannot carry the binding: an OSC argument reads its own control.

    So SEND touches the readout and the readout sends. The corpus agrees on
    both halves -- a `text` argument is always VALUE/STRING (892 of 892), and
    `touch` RISE is an attested OSC trigger.
    """
    out = tmp_path / "numpad.tosc"
    run("numpad.py", out)
    doc = py2tosc.load(out)
    readout = doc.find("valueLabel")

    send = next(c for c in doc.walk() if c.name == "SEND" and c.messages)
    assert send.messages[0].dst_var == "touch"
    assert send.messages[0].dst_id == readout.id

    # ANY, not RISE: the pulse has to fall back on release, or a second press
    # writes the 1 that is already there and never re-triggers the send.
    assert [(t.var, t.condition) for t in send.messages[0].triggers] == [("x", "ANY")]

    osc = next(m for m in readout.messages if isinstance(m, py2tosc.OscMessage))
    assert [(p.type, p.value) for p in osc.path] == [("CONSTANT", "/numpad/value")]
    assert [(p.type, p.conversion, p.value) for p in osc.arguments] == [
        ("VALUE", "STRING", "text")
    ]
    assert [(t.var, t.condition) for t in osc.triggers] == [("touch", "RISE")]
    assert osc.send and not osc.receive


def test_numpad_output_is_a_clean_layout(tmp_path):
    out = tmp_path / "numpad.tosc"
    run("numpad.py", out)
    assert py2tosc.load(out).validate() == []


def _control_surface():
    """Import the demo, so its parts can be exercised without a subprocess."""
    sys.path.insert(0, str(DEMOS))
    import control_surface

    return control_surface


def test_control_surface(tmp_path):
    """A whole interface generated from a parameter list, nothing hand-placed."""
    out = tmp_path / "surface.tosc"
    result = run("control_surface.py", DATA / "pro_c_2_fabfilter.json", out)
    assert "54 parameters -> 5 pages" in result.stdout

    doc = py2tosc.load(out)

    # the pager sits inside a group: as the root it would draw a tab bar and
    # then stack every page instead of paging between them
    assert doc.root.control_type is py2tosc.ControlType.GROUP
    pager = doc.find(type="PAGER")
    assert pager is not None and pager in doc.root.children
    assert [p.name for p in pager] == ["1-12", "13-24", "25-36", "37-48", "49-54"]

    # every page shares one frame, sitting below the tab bar rather than under it
    bar = pager.get("tabbarSize")
    assert {tuple(p.frame) for p in pager} == {
        (0.0, bar, pager.frame.w, pager.frame.h - bar)
    }
    assert [p.get("tabLabel") for p in pager] == [p.name for p in pager]
    assert all(c.frame.w > 0 and c.frame.h > 0 for c in doc.walk())

    faders = doc.find_all(type="FADER")
    assert len(faders) == 54
    assert len(doc.find_all(type="LABEL")) == 54


def test_control_surface_output_is_a_clean_layout(tmp_path):
    out = tmp_path / "surface.tosc"
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", out)
    assert py2tosc.load(out).validate() == []


def test_control_surface_names_are_addressable(tmp_path):
    """Names reach the wire, so they must be unique and OSC-legal.

    The real data forces both: it repeats `Bypass` and `Internal`, and every
    multi-word name contains spaces, which an OSC address cannot.
    """
    out = tmp_path / "surface.tosc"
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", out)
    doc = py2tosc.load(out)

    names = [f.name for f in doc.find_all(type="FADER")]
    assert len(set(names)) == len(names) == 54
    reserved = set(" #*,?[]{}/")
    assert not [n for n in names if set(n) & reserved]

    # the caption keeps the text a person reads
    captions = {v.default for c in doc.find_all(type="LABEL") for v in c.values}
    assert "Side Chain High Frequency" in captions


def test_control_surface_numbers_ccs_by_position_not_parameter_index(tmp_path):
    """The plugin's own indices run to 182, past what a CC can carry.

    An index is a host identifier, not a controller number, so using it would
    make `midi_cc` raise on two thirds of this file.
    """
    import json

    parameters = json.loads((DATA / "pro_c_2_fabfilter.json").read_text())
    assert max(p["index"] for p in parameters) > 127

    out = tmp_path / "surface.tosc"
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", out)
    doc = py2tosc.load(out)

    ccs = [
        m.message.data1
        for c in doc.walk()
        for m in c.messages
        if isinstance(m, py2tosc.MidiMessage)
    ]
    assert sorted(ccs) == list(range(54))


def test_control_surface_drops_midi_past_the_cc_range():
    """A plugin with more than 128 parameters still gets an OSC binding."""
    surface = _control_surface()
    doc = surface.build([f"p{n}" for n in range(130)], "big")

    faders = doc.find_all(type="FADER")
    assert len(faders) == 130
    midi = [
        c.name
        for c in faders
        if any(isinstance(m, py2tosc.MidiMessage) for m in c.messages)
    ]
    assert len(midi) == surface.CC_LIMIT
    assert all(
        any(isinstance(m, py2tosc.OscMessage) for m in c.messages) for c in faders
    )


def test_control_surface_slug_is_stable_and_legal():
    surface = _control_surface()
    assert surface.slug("Side Chain High Frequency") == "sideChainHighFrequency"
    assert surface.slug("pro_c_2_fabfilter") == "proC2Fabfilter"
    assert surface.slug("!!!") == "parameter"
    assert surface.unique(["a", "b", "a", "a"]) == ["a", "b", "a2", "a3"]


def test_control_surface_takes_an_osc_prefix(tmp_path):
    """The namespace is an argument, not a consequence of the filename.

    Deriving it from the file is convenient and fragile: renaming the data
    moves every address, which is exactly what happened once already.
    """
    out = tmp_path / "surface.tosc"
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", out, "Synth/Bank 1")
    doc = py2tosc.load(out)

    osc = next(
        m
        for m in doc.find_all(type="FADER")[0].messages
        if isinstance(m, py2tosc.OscMessage)
    )
    assert [(p.type, p.value) for p in osc.path] == [
        ("CONSTANT", "/synth/bank1/"),
        ("PROPERTY", "name"),
    ]
    # a control name cannot hold a path, so the layout takes the last segment
    assert doc.root.name == "bank1"


def test_control_surface_falls_back_to_the_filename(tmp_path):
    out = tmp_path / "surface.tosc"
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", out)
    doc = py2tosc.load(out)
    assert doc.root.name == "proC2Fabfilter"


def test_control_surface_namespace_is_osc_safe():
    surface = _control_surface()
    assert surface.namespace("Synth/Bank 1") == "synth/bank1"
    assert surface.namespace("/leading/and/trailing/") == "leading/and/trailing"
    assert surface.namespace("  ") == ""
    assert surface.namespace("") == ""
