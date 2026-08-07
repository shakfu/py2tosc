"""The demo scripts, run for real.

These are the programs the documentation embeds, so if they stop working the
documentation is wrong. Each is executed as a subprocess exactly the way the
docs say to invoke it, and its output is loaded back to prove it produced a
layout rather than merely exiting zero.
"""

import collections
import subprocess
import sys

import pytest
from _corpus import DATA, DEMOS, EXAMPLES

import py2tosc

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
        "controls.py",
        "custom_property.py",
        "copy_scripts.py",
        "from_json.py",
        "image_converter.py",
        "numpad.py",
        "simple_mk2.py",
    }
    assert {p.name for p in DEMO_SCRIPTS} == covered


@pytest.mark.parametrize("script", DEMO_SCRIPTS, ids=lambda p: p.name)
def test_every_demo_compiles(script):
    """Cheap syntax and import check, so a broken demo fails fast."""
    subprocess.run([sys.executable, "-m", "py_compile", str(script)], check=True)


def test_custom_property(tmp_path):
    out = tmp_path / "custom.tosc"
    result = run("custom_property.py", DATA / "test2.tosc", "-o", out)

    assert "Craig" in result.stdout
    doc = py2tosc.load(out)
    assert doc.root.get("CustomProperty") == "Craig"
    # the rest of the layout is untouched
    assert len(list(doc.walk())) == len(list(py2tosc.load(DATA / "test2.tosc").walk()))


def test_copy_scripts(tmp_path):
    out = tmp_path / "scripts.tosc"
    run("copy_scripts.py", DATA / "test.tosc", "source", "target", "-o", out)

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
            "nonexistent",
            "target",
            "-o",
            str(tmp_path / "out.tosc"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "nonexistent" in result.stderr


def test_from_json(tmp_path):
    out = tmp_path / "fromjson.tosc"
    result = run("from_json.py", DATA / "pro_c_2_fabfilter.json", "-o", out)

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
        "image_converter.py", DATA / "test.tosc", DATA / "logo.jpg", "canvas", "-o", out
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
            str(DATA / "logo.jpg"),
            "no-such-group",
            "-o",
            str(tmp_path / "out.tosc"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "no-such-group" in result.stderr


def test_numpad(tmp_path):
    """The most involved demo: nested layouts, a Lua script, and LOCAL wiring."""
    out = tmp_path / "numpad.tosc"
    result = run("numpad.py", "-o", out)

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
    run("numpad.py", "-o", out)
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
    run("numpad.py", "-o", out)
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
    run("numpad.py", "-o", out)
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
    run("numpad.py", "-o", out)
    assert py2tosc.load(out).validate() == []


def test_control_surface(tmp_path):
    """A whole interface generated from a parameter list, nothing hand-placed."""
    out = tmp_path / "surface.tosc"
    result = run("control_surface.py", DATA / "pro_c_2_fabfilter.json", "-o", out)
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
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", "-o", out)
    assert py2tosc.load(out).validate() == []


def test_control_surface_names_are_addressable(tmp_path):
    """Names reach the wire, so they must be unique and OSC-legal.

    The real data forces both: it repeats `Bypass` and `Internal`, and every
    multi-word name contains spaces, which an OSC address cannot.
    """
    out = tmp_path / "surface.tosc"
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", "-o", out)
    doc = py2tosc.load(out)

    names = [f.name for f in doc.find_all(type="FADER")]
    assert len(set(names)) == len(names) == 54
    reserved = set(" #*,?[]{}/")
    assert not [n for n in names if set(n) & reserved]

    # the caption keeps the text a person reads
    captions = {v.default for c in doc.find_all(type="LABEL") for v in c.values}
    assert "Side Chain High Frequency" in captions


def test_control_surface_takes_an_osc_prefix(tmp_path):
    """The namespace is an argument, not a consequence of the filename.

    Deriving it from the file is convenient and fragile: renaming the data
    moves every address, which is exactly what happened once already.
    """
    out = tmp_path / "surface.tosc"
    run(
        "control_surface.py",
        DATA / "pro_c_2_fabfilter.json",
        "--prefix",
        "Synth/Bank 1",
        "-o",
        out,
    )
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
    run("control_surface.py", DATA / "pro_c_2_fabfilter.json", "-o", out)
    doc = py2tosc.load(out)
    assert doc.root.name == "proC2Fabfilter"


def _absolute(doc):
    """Every leaf control in absolute coordinates, keyed by page, name and type.

    The rebuild nests more groups than the original, so a frame relative to its
    parent is not comparable; where a control ends up on screen is.
    """
    found = {}

    def walk(control, ox, oy, page=None):
        x, y, w, h = control.frame
        ax, ay = ox + x, oy + y
        if control.control_type is py2tosc.ControlType.GROUP and control.get(
            "tabLabel"
        ):
            page = control.get("tabLabel")
        if control.control_type not in (
            py2tosc.ControlType.GROUP,
            py2tosc.ControlType.PAGER,
        ):
            found[(page, control.get("name"), control.control_type.value)] = (
                int(ax),
                int(ay),
                int(w),
                int(h),
            )
        for child in control.children:
            walk(child, ax, ay, page)

    walk(doc.root, 0, 0)
    return found


def test_simple_mk2(tmp_path):
    """The widest thing here that is authored rather than edited."""
    out = tmp_path / "mk2.tosc"
    result = run("simple_mk2.py", "-o", out)
    assert "4 pages" in result.stdout

    doc = py2tosc.load(out)
    reference = py2tosc.load(EXAMPLES / "simple_mk2.tosc")

    # the same controls, by type and by name
    def types(d):
        return collections.Counter(
            c.control_type.value
            for c in d.walk()
            if c.control_type is not py2tosc.ControlType.GROUP
        )

    assert types(doc) == types(reference)
    assert sorted(
        str(c.get("name"))
        for c in doc.walk()
        if c.control_type is not py2tosc.ControlType.GROUP
    ) == sorted(
        str(c.get("name"))
        for c in reference.walk()
        if c.control_type is not py2tosc.ControlType.GROUP
    )

    # the same bindings, to the message
    def messages(d):
        return collections.Counter(
            type(m).__name__ for c in d.walk() for m in c.messages
        )

    assert messages(doc) == messages(reference)
    assert [p.get("tabLabel") for p in doc.find(type="PAGER")] == [
        "FADERS",
        "PADS",
        "XY",
        "MATRIX",
    ]


def test_simple_mk2_lands_where_the_original_does(tmp_path):
    """Positions are the claim the combinators have to earn.

    The readouts are the deliberate exception: they fill the control they
    caption rather than being small boxes placed by eye, so they are counted
    and named rather than quietly tolerated.
    """
    out = tmp_path / "mk2.tosc"
    run("simple_mk2.py", "-o", out)

    mine = _absolute(py2tosc.load(out))
    theirs = _absolute(py2tosc.load(EXAMPLES / "simple_mk2.tosc"))
    shared = set(mine) & set(theirs)
    assert len(shared) == 134

    exact = [k for k in shared if mine[k] == theirs[k]]
    close = [
        k for k in shared if max(abs(a - b) for a, b in zip(mine[k], theirs[k])) <= 1
    ]
    apart = [k for k in shared if k not in close]

    assert len(exact) >= 77, f"only {len(exact)} exact"
    assert len(close) >= 111, f"only {len(close)} within a point"
    assert {k[2] for k in apart} == {"LABEL"}, "only the readouts may differ"


def test_simple_mk2_output_is_a_clean_layout(tmp_path):
    out = tmp_path / "mk2.tosc"
    run("simple_mk2.py", "-o", out)
    assert py2tosc.load(out).validate() == []


def test_simple_mk2_behaves_like_the_original(tmp_path):
    """The properties that decide what a control *does*, not how it looks.

    Every one of these was wrong on the first pass and every one of them was
    invisible to the checks above: the layout validated, round-tripped and had
    the right controls in the right places while nothing on it responded to
    touch. An interactive label swallows the touch meant for the fader under
    it; a momentary button will not latch; a fader is vertical whatever shape
    its frame is.

    A label's text belongs here for the same reason. A caption left empty is
    not a cosmetic difference -- the control reads as missing.
    """
    out = tmp_path / "mk2.tosc"
    run("simple_mk2.py", "-o", out)

    def by_page(doc):
        found = {}
        for page in doc.find(type="PAGER"):
            for control in page.walk():
                if control.control_type not in (
                    py2tosc.ControlType.GROUP,
                    py2tosc.ControlType.PAGER,
                ):
                    key = (page.get("tabLabel"), control.get("name"))
                    found[(*key, control.control_type.value)] = control
        return found

    mine = by_page(py2tosc.load(out))
    theirs = by_page(py2tosc.load(EXAMPLES / "simple_mk2.tosc"))
    shared = set(mine) & set(theirs)
    assert len(shared) == 134

    behaviour = [
        "interactive",
        "visible",
        "buttonType",
        "shape",
        "orientation",
        "response",
        "outline",
        "cursor",
        "centered",
        "pointerPriority",
        "locked",
    ]
    differing = [
        (key, prop, theirs[key].get(prop), mine[key].get(prop))
        for key in shared
        for prop in behaviour
        if theirs[key].get(prop) != mine[key].get(prop)
    ]
    assert not differing, differing[:5]

    def text(control):
        return [v.default for v in control.values if v.key == "text"]

    blank = [
        key
        for key in shared
        if key[2] == "LABEL" and text(mine[key]) != text(theirs[key])
    ]
    assert not blank, blank[:5]


# -- controls: one of every type ---------------------------------------------


def test_controls_builds_one_of_every_type(tmp_path):
    """The six types nothing in the library had ever authored are authored
    here. Confirmed working in TouchOSC, which is the only oracle for whether
    a RADIAL came out round."""
    out = tmp_path / "controls.tosc"
    result = run("controls.py", "-o", out)

    assert "13 control types" in result.stdout
    doc = py2tosc.load(out)

    built = {c.control_type for c in doc.walk()}
    assert built == set(py2tosc.ControlType), sorted(
        t.value for t in set(py2tosc.ControlType) - built
    )
    assert doc.validate() == []


def test_controls_matches_the_editors_own_sheet(tmp_path):
    """`controls.tosc` is the same idea drawn by hand. The behavioural
    properties have to agree, since those are what decide whether a control
    works rather than where it sits."""
    out = tmp_path / "controls.tosc"
    run("controls.py", "-o", out)
    built = py2tosc.load(out)
    reference = py2tosc.load(DATA / "controls.tosc")

    for kind in py2tosc.ControlType:
        mine = next((c for c in built.walk() if c.control_type is kind), None)
        theirs = next((c for c in reference.walk() if c.control_type is kind), None)
        if mine is None or theirs is None:
            continue
        for key in ("shape", "interactive", "gridSteps"):
            if mine.has(key) and theirs.has(key):
                assert mine.get(key) == theirs.get(key), f"{kind.value}.{key}"


def test_controls_captions_are_values_not_properties(tmp_path):
    """`label(text="hi")` sets a custom property of that name, which TouchOSC
    ignores and draws as nothing -- it is the label's `text` *value* that
    holds what it says. Every caption on this sheet was blank until that was
    fixed, and `validate` now reports the mistake."""
    out = tmp_path / "controls.tosc"
    run("controls.py", "-o", out)
    doc = py2tosc.load(out)

    captions = [c for c in doc.walk() if str(c.get("name", "")).endswith("Caption")]
    assert len(captions) > 12
    for caption in captions:
        assert caption.value("text").default
        assert "text" not in caption.properties
