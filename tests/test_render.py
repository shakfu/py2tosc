"""The picture, against the layout it is a picture of.

There is no oracle here. TouchOSC is the only thing that knows what a layout
really looks like and it cannot be scripted, so nothing below asserts that the
output *looks* right -- that bar is stated in the module and in the guide, and
it is deliberately not "matches a screenshot".

What is checkable is the part a reader depends on and the part a later runtime
would depend on: that every control in the document reaches the output as
exactly one addressable node, that the frames in the picture are the frames in
the document, and that the whole corpus draws without raising. The last is the
sweep `tests/test_corpus.py` already establishes for the codecs, applied to the
one emitter that has no round trip to check it.
"""

import xml.etree.ElementTree as ET

import pytest

import py2tosc
from _corpus import CORPUS, DATA
from py2tosc import ui
from py2tosc.enums import ControlType
from py2tosc.render import PREFIX, to_svg

SVG = "{http://www.w3.org/2000/svg}"


def groups(svg):
    """Every control's node, in document order."""
    root = ET.fromstring(svg)
    return [
        element
        for element in root.iter(f"{SVG}g")
        if f"{PREFIX}-control" in (element.get("class") or "")
    ]


def test_the_output_is_well_formed_xml():
    """Nothing here escapes by hand, so this is the check that it never has to."""
    ET.fromstring(to_svg(py2tosc.load(DATA / "fader_with_label.tosc")))


@pytest.mark.parametrize("path", sorted(CORPUS), ids=lambda p: p.name)
def test_every_layout_in_the_corpus_draws(path):
    """A picture of a layout nobody drew before is where this would break."""
    svg = to_svg(py2tosc.load(path))
    ET.fromstring(svg)


@pytest.mark.parametrize("path", sorted(CORPUS), ids=lambda p: p.name)
def test_every_control_reaches_the_output_as_one_node(path):
    """The property a later runtime rests on, pinned before there is one.

    One node per control, so a script that wants to drive a control has
    somewhere to attach and a test that wants to find one can.
    """
    doc = py2tosc.load(path)
    assert len(groups(to_svg(doc))) == len(list(doc.walk()))


def test_a_frame_in_the_picture_is_the_frame_in_the_document():
    """The one thing here that *does* have an oracle: `ui.resolve` computed it.

    Frames are relative to the parent in this format, so a child's transform is
    its own frame rather than an accumulated offset -- which is the whole
    reason the renderer does no coordinate arithmetic.
    """
    doc = py2tosc.load(DATA / "fader_with_label.tosc")
    fader = doc.root.children[0]
    frame = fader.get("frame")

    found = [
        element
        for element in groups(to_svg(doc))
        if element.get("data-name") == "fader1"
    ]
    assert len(found) == 1
    assert found[0].get("transform") == f"translate({frame.x:g}, {frame.y:g})"


def test_every_control_type_is_drawn_somewhere_in_the_corpus():
    """So a type nobody exercised cannot quietly render as nothing."""
    drawn = set()
    for path in CORPUS:
        for element in groups(to_svg(py2tosc.load(path))):
            for name in (element.get("class") or "").split():
                if name.startswith(f"{PREFIX}-") and name != f"{PREFIX}-control":
                    drawn.add(name)
    for kind in ControlType:
        assert f"{PREFIX}-{kind.value.lower()}" in drawn, kind


#: The mark each type is recognised by, where it has one. BOX, GROUP and GRID
#: are absent on purpose: a box *is* its shape, and the two containers are the
#: controls inside them.
MARKED = {
    ControlType.FADER: f"{PREFIX}-bar",
    ControlType.BUTTON: f"{PREFIX}-cap",
    ControlType.RADIO: f"{PREFIX}-mark",
    ControlType.XY: f"{PREFIX}-cross",
    ControlType.RADAR: f"{PREFIX}-dial",
    ControlType.ENCODER: f"{PREFIX}-dial",
    ControlType.RADIAL: f"{PREFIX}-dial",
    ControlType.LABEL: f"{PREFIX}-text",
    ControlType.TEXT: f"{PREFIX}-text",
}


@pytest.mark.parametrize("kind, mark", sorted(MARKED.items(), key=lambda p: p[0].value))
def test_a_control_is_drawn_as_the_kind_it_is(kind, mark):
    """The half of the promise that costs something.

    Where a control is falls out of the frames; *what it is* has to be drawn,
    and a layout whose controls all carry the same default colour -- which is
    every layout the combinators build -- has nothing else to say it. Without
    this, a fader and a button are two identical rounded rectangles.
    """
    control = py2tosc.Control(kind, name="c", frame=(0, 0, 60, 60))
    if kind in (ControlType.LABEL, ControlType.TEXT):
        control.values[0].default = "hello"
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 60, 60)))
    doc.add(control)

    drawn = [g for g in groups(to_svg(doc)) if g.get("data-name") == "c"][0]
    assert any(mark in (e.get("class") or "") for e in drawn.iter()), (
        f"{kind.value} draws nothing that says it is a {kind.value}"
    )


def test_a_fader_says_where_its_value_is_even_at_zero():
    """A bar scaled to nothing is an empty box, which is the wrong picture.

    TouchOSC draws a handle with real thickness at the value, so a fader at 0
    still shows a band along the bottom. Confirmed against the real thing:
    every fader in `grid-faders.tosc` sits at 0 and every one shows its
    cursor.
    """
    fader = py2tosc.fader(name="f", frame=(0, 0, 40, 200))
    fader.values[0].default = 0.0
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 40, 200)))
    doc.add(fader)

    drawn = [g for g in groups(to_svg(doc)) if g.get("data-name") == "f"][0]
    cursor = [
        e for e in drawn.iter() if f"{PREFIX}-cursor" in (e.get("class") or "")
    ]
    assert cursor, "a fader at zero draws no cursor"
    assert float(cursor[0].get("height")) >= 3
    # The travel is static and the value is not, which is what keeps the rule
    # for where the handle sits in one place.
    assert "--span:" in (drawn.get("style") or "")
    assert "--v: 0" in (drawn.get("style") or "")


def test_a_fader_draws_the_grid_it_declares():
    """`grid` with `gridSteps` is what makes the track readable in TouchOSC."""
    fader = py2tosc.fader(name="f", frame=(0, 0, 40, 200), grid=True, grid_steps=5)
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 40, 200)))
    doc.add(fader)

    drawn = [g for g in groups(to_svg(doc)) if g.get("data-name") == "f"][0]
    rules = [e for e in drawn.iter() if f"{PREFIX}-rule" in (e.get("class") or "")]
    assert len(rules) == 4  # five steps, four lines between them


@pytest.mark.parametrize(
    "orientation, axis",
    [(0, "y"), (1, "x")],
    ids=["north", "east"],
)
def test_a_radio_says_which_step_it_is_on(orientation, axis):
    """Without it, a radio at the first step and one at the last are the same
    drawing -- the defect the fader had at zero, one control along.

    Both axes, because a RADIO defaults to EAST rather than NORTH and reading
    the wrong one is exactly the mistake that would pass unnoticed.
    """
    radio = py2tosc.Control(
        "RADIO", name="r", frame=(0, 0, 200, 200), steps=4, orientation=orientation
    )
    radio.values[0].default = 0.8
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 200, 200)))
    doc.add(radio)

    drawn = [g for g in groups(to_svg(doc)) if g.get("data-name") == "r"][0]
    step = [e for e in drawn.iter() if f"{PREFIX}-step" in (e.get("class") or "")]
    assert step, "a radio draws nothing to say which step it is on"
    assert float(step[0].get(axis)) == 150  # the fourth of four, 200 * 3 / 4


def test_a_value_rides_a_custom_property_rather_than_the_geometry():
    """The decision that makes an interactive version additive rather than a
    rewrite: the rule for where a fader's bar goes exists once, in CSS.
    """
    fader = py2tosc.fader(name="f", frame=(0, 0, 40, 100))
    fader.values[0].default = 0.75
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 40, 100)))
    doc.add(fader)

    svg = to_svg(doc)
    drawn = [g for g in groups(svg) if g.get("data-name") == "f"][0]
    assert "--v: 0.75" in (drawn.get("style") or "")
    # The bar is full height in the markup; CSS scales it. A height computed
    # from the value here is what this exists to avoid.
    bar = [e for e in drawn.iter() if f"{PREFIX}-bar" in (e.get("class") or "")][0]
    assert bar.get("height") == "100"


def test_text_is_escaped():
    """A label saying `<b> & </b>` is a label, not markup."""
    label = py2tosc.label(name="l", frame=(0, 0, 80, 20))
    label.values[0].default = "<b> & </b>"
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 80, 20)))
    doc.add(label)

    svg = to_svg(doc)
    assert "&lt;b&gt; &amp; &lt;/b&gt;" in svg
    found = ET.fromstring(svg).iter(f"{SVG}text")
    assert next(found).text == "<b> & </b>"


def test_an_invisible_control_is_drawn_and_marked():
    """Which is exactly the kind of thing someone renders a layout to find."""
    hidden = py2tosc.box(name="b", frame=(0, 0, 10, 10), visible=False)
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 10, 10)))
    doc.add(hidden)

    drawn = [g for g in groups(to_svg(doc)) if g.get("data-name") == "b"][0]
    assert f"{PREFIX}-hidden" in drawn.get("class")


def test_a_layout_built_by_the_combinators_draws_once_resolved():
    """The case the renderer exists for: seeing what `ui` decided."""
    doc = py2tosc.Document(
        root=ui.row(
            *[py2tosc.fader(name=f"ch{n}") for n in range(1, 5)],
            gap=4,
            frame=(0, 0, 400, 200),
        )
    ).resolve()
    assert len(groups(to_svg(doc))) == len(list(doc.walk()))


# -- clipping, which is a choice rather than a default -----------------------


def overflowing():
    """A control that sticks out of the one holding it.

    The defect a picture is drawn to find, and the thing clipping hides.
    """
    doc = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 100, 100)))
    doc.add(py2tosc.box(name="over", frame=(60, 60, 200, 200)))
    return doc


def test_overflow_is_shown_by_default():
    """A control past its parent's edge is a defect, not a thing to tidy away.

    Which is why the default is off: a clipped picture agrees with a layout
    that is wrong, and the reader learns nothing.
    """
    svg = to_svg(overflowing())
    assert "clipPath" not in svg
    over = [g for g in groups(svg) if g.get("data-name") == "over"][0]
    assert over.get("transform") == "translate(60, 60)"


def test_clipping_cuts_a_control_off_at_its_parent():
    """What the device shows, for when that is the question being asked."""
    svg = to_svg(overflowing(), clip=True)
    root = ET.fromstring(svg)
    clips = list(root.iter(f"{SVG}clipPath"))
    assert len(clips) == 1
    assert clips[0].get("id")
    assert f'clip-path="url(#{clips[0].get("id")})"' in svg


def test_a_pager_is_never_clipped():
    """Its pages are laid out past its own frame on purpose, so clipping to
    that frame would hide every page but the first -- which is the bug the
    fan-out was added to fix."""
    doc = py2tosc.load(DATA / "pagers.tosc")
    clipped = to_svg(doc, clip=True)
    assert len(groups(clipped)) == len(list(doc.walk()))
    # Same drawn extent either way: nothing was cut off the fan-out.
    assert ET.fromstring(clipped).get("viewBox") == ET.fromstring(
        to_svg(doc)
    ).get("viewBox")


def test_the_clip_leaves_every_control_addressable():
    """The wrapper is a group of its own, so it must not cost a node."""
    doc = py2tosc.load(DATA / "fader_with_label.tosc")
    assert len(groups(to_svg(doc, clip=True))) == len(list(doc.walk()))


# -- the page around the picture ---------------------------------------------


def test_the_page_holds_the_same_picture():
    """One renderer with a wrapper, not two renderers.

    The property that keeps anything added later additive: whatever the page
    grows, the picture inside it is the string `to_svg` produced.
    """
    doc = py2tosc.load(DATA / "fader_with_label.tosc")
    assert py2tosc.render.to_svg(doc) in py2tosc.render.to_html(doc)


def test_the_page_is_well_formed_and_says_what_it_holds():
    doc = py2tosc.load(DATA / "fader_with_label.tosc")
    page = py2tosc.render.to_html(doc)

    assert page.startswith("<!doctype html>")
    assert "<title>" in page
    assert f"{len(list(doc.walk()))} controls" in page


def test_the_page_carries_the_clip_through():
    doc = overflowing()
    assert "clipPath" not in py2tosc.render.to_html(doc)
    assert "clipPath" in py2tosc.render.to_html(doc, clip=True)


def test_the_page_reports_what_validate_found():
    """A layout the editor will refuse is worth knowing about while looking at
    the picture rather than afterwards."""
    broken = py2tosc.Document(root=py2tosc.group(name="root", frame=(0, 0, 80, 80)))
    box = py2tosc.box(name="oops", frame=(0, 0, 40, 40))
    box.add(py2tosc.fader(name="inner", frame=(0, 0, 10, 10)))
    broken.add(box)

    page = py2tosc.render.to_html(broken)
    assert "cannot hold children" in page
    assert "issue(s)" in page


def test_a_clean_layout_reports_no_issues():
    page = py2tosc.render.to_html(py2tosc.load(DATA / "mixer.ui.json"))
    assert "issue(s)" not in page
    assert "<ul" not in page


def test_the_page_escapes_what_it_is_told():
    """A layout named `<script>` is a name, not markup."""
    doc = py2tosc.Document(root=py2tosc.group(name="<script>x</script>", frame=(0, 0, 8, 8)))
    page = py2tosc.render.to_html(doc)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
