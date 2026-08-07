"""The layout combinators in `py2tosc.ui`.

These describe an arrangement and assign frames later, which is what lets a
layout be written from the inside out. The rounding invariant is tested first,
because everything else is only correct if the arithmetic is.
"""

import pytest

import py2tosc
from py2tosc import ui
from _corpus import CORPUS, DATA, EXAMPLES
from py2tosc._geometry import ratios, slots


def frames(control):
    return [tuple(int(v) for v in c.frame) for c in control.children]


# -- the arithmetic ----------------------------------------------------------


@pytest.mark.parametrize("length", [1, 7, 100, 333, 1024, 1080.5])
@pytest.mark.parametrize("count", [1, 2, 3, 5, 8])
@pytest.mark.parametrize("gap", [0, 1, 4])
@pytest.mark.parametrize("pad", [0, 3, 11])
def test_slots_never_lose_or_gain_a_pixel(length, count, gap, pad):
    """The restated invariant, in full.

    `spans` guarantees each slot ends exactly where the next begins. Separating
    slots breaks that wording, so it becomes: slot i ends exactly `gap` before
    slot i+1 begins, the first begins at `pad`, and the last ends at the
    content edge, `round(length - pad)`.

    The edge is rounded before the division rather than after, which is what
    keeps a fractional frame from pushing the last slot past its parent.
    """
    if round(length - pad) - pad - gap * (count - 1) < 0:
        pytest.skip("does not fit; covered by test_a_layout_that_cannot_fit_raises")

    placed = slots(length, ratios(count), pad, pad, gap, "width")

    assert placed[0][0] == pad
    assert placed[-1][0] + placed[-1][1] == round(length - pad)
    assert placed[-1][0] + placed[-1][1] <= length
    for (offset, size), (next_offset, _) in zip(placed, placed[1:]):
        assert next_offset - (offset + size) == gap
    assert all(size >= 0 for _, size in placed)


def test_slots_with_no_padding_or_gap_still_tile_exactly():
    """The original invariant is the gap=0, pad=0 case of the new one."""
    placed = slots(1000, ratios((1, 2, 3, 5)), 0, 0, 0, "width")
    assert placed[0][0] == 0
    assert placed[-1][0] + placed[-1][1] == 1000
    for (offset, size), (next_offset, _) in zip(placed, placed[1:]):
        assert next_offset == offset + size


# -- composition, which is the point -----------------------------------------


def test_a_layout_returns_a_control_so_layouts_nest():
    """`row(column(a, b), c)` is the case the eager functions cannot express.

    They return a list of children, so their output is not their input, and
    nesting drops to manual frame arithmetic.
    """
    inner = ui.column(py2tosc.label(name="m"), py2tosc.label(name="n"))
    outer = ui.row(inner, py2tosc.fader(name="f"), sizes=(1, 3))
    ui.resolve(outer, (0, 0, 400, 200))

    assert isinstance(outer, py2tosc.Control)
    assert outer.control_type is py2tosc.ControlType.GROUP
    assert frames(outer) == [(0, 0, 100, 200), (100, 0, 300, 200)]
    assert frames(inner) == [(0, 0, 100, 100), (0, 100, 100, 100)]


def test_a_row_can_hold_more_than_one_control_type():
    """The eager functions apply one type to every slot; these take controls."""
    strip = ui.row(py2tosc.fader(name="f"), py2tosc.label(name="l"))
    ui.resolve(strip, (0, 0, 200, 50))
    assert [c.control_type.value for c in strip] == ["FADER", "LABEL"]
    assert frames(strip) == [(0, 0, 100, 50), (100, 0, 100, 50)]


# -- each arrangement --------------------------------------------------------


def test_row_divides_the_width():
    strip = ui.row(*[py2tosc.fader() for _ in range(4)])
    ui.resolve(strip, (0, 0, 400, 100))
    assert frames(strip) == [(0, 0, 100, 100) for _ in range(4)][:1] + [
        (100, 0, 100, 100),
        (200, 0, 100, 100),
        (300, 0, 100, 100),
    ]


def test_column_divides_the_height_by_weight():
    stack = ui.column(py2tosc.fader(), py2tosc.fader(), sizes=(1, 3))
    ui.resolve(stack, (0, 0, 100, 400))
    assert frames(stack) == [(0, 0, 100, 100), (0, 100, 100, 300)]


def test_grid_takes_just_enough_rows_for_its_children():
    cells = ui.tiles(*[py2tosc.button() for _ in range(6)], columns=3)
    ui.resolve(cells, (0, 0, 300, 200))
    assert frames(cells) == [
        (0, 0, 100, 100),
        (100, 0, 100, 100),
        (200, 0, 100, 100),
        (0, 100, 100, 100),
        (100, 100, 100, 100),
        (200, 100, 100, 100),
    ]


def test_grid_rows_can_be_given_explicitly():
    cells = ui.tiles(py2tosc.button(), columns=2, rows=2)
    ui.resolve(cells, (0, 0, 200, 200))
    assert frames(cells) == [(0, 0, 100, 100)]


def test_stack_gives_every_child_the_whole_group():
    """A label on a button: the commonest TouchOSC idiom, and the one the
    eager functions cannot express, since they divide rather than share."""
    key = ui.stack(py2tosc.button(name="b"), py2tosc.label(name="l"))
    ui.resolve(key, (0, 0, 80, 40))
    assert frames(key) == [(0, 0, 80, 40), (0, 0, 80, 40)]


def test_stack_insets_every_child_alike():
    key = ui.stack(py2tosc.button(), py2tosc.label(), pad=5)
    ui.resolve(key, (0, 0, 80, 40))
    assert frames(key) == [(5, 5, 70, 30), (5, 5, 70, 30)]


# -- gap and pad -------------------------------------------------------------


def test_gap_sits_between_children_and_pad_around_them():
    strip = ui.row(py2tosc.fader(), py2tosc.fader(), gap=10, pad=20)
    ui.resolve(strip, (0, 0, 200, 100))
    assert frames(strip) == [(20, 20, 75, 60), (105, 20, 75, 60)]


@pytest.mark.parametrize(
    ("pad", "expected"),
    [
        (4, (4, 4, 4, 4)),
        ((2, 6), (2, 6, 2, 6)),
        ((1, 2, 3, 4), (1, 2, 3, 4)),
    ],
)
def test_pad_accepts_one_two_or_four_numbers(pad, expected):
    left, top, right, bottom = expected
    key = ui.stack(py2tosc.button(), pad=pad)
    ui.resolve(key, (0, 0, 100, 100))
    assert frames(key) == [(left, top, 100 - left - right, 100 - top - bottom)]


def test_gap_accepts_a_pair_for_the_two_axes():
    """A gap has no four-sided form: it sits between slots, not around them."""
    cells = ui.tiles(*[py2tosc.button() for _ in range(4)], columns=2, gap=(10, 20))
    ui.resolve(cells, (0, 0, 210, 220))
    assert frames(cells) == [
        (0, 0, 100, 100),
        (110, 0, 100, 100),
        (0, 120, 100, 100),
        (110, 120, 100, 100),
    ]


@pytest.mark.parametrize("gap", [(1, 2, 3), (1, 2, 3, 4)])
def test_a_four_sided_gap_is_rejected(gap):
    with pytest.raises(ValueError, match="gap takes"):
        ui.row(py2tosc.fader(), gap=gap)


def test_a_three_sided_pad_is_rejected():
    with pytest.raises(ValueError, match="pad takes"):
        ui.row(py2tosc.fader(), pad=(1, 2, 3))


# -- failures ----------------------------------------------------------------


def test_a_layout_that_cannot_fit_raises():
    strip = ui.row(py2tosc.fader(), py2tosc.fader(), gap=100, pad=50)
    with pytest.raises(ValueError, match="cannot hold"):
        ui.resolve(strip, (0, 0, 100, 100))


def test_sizes_must_match_the_children():
    strip = ui.row(py2tosc.fader(), py2tosc.fader(), sizes=(1, 2, 3))
    with pytest.raises(ValueError, match="3 sizes for 2 children"):
        ui.resolve(strip, (0, 0, 300, 100))


def test_padding_larger_than_the_frame_raises():
    key = ui.stack(py2tosc.button(), pad=80)
    with pytest.raises(ValueError, match="does not fit"):
        ui.resolve(key, (0, 0, 100, 100))


def test_an_empty_layout_resolves_without_complaint():
    empty = ui.row(name="nothing")
    ui.resolve(empty, (0, 0, 100, 100))
    assert empty.validate() == []


# -- how resolution walks ----------------------------------------------------


def test_a_parent_overrides_a_childs_own_frame():
    """Placement is top down, so a layout decides its children outright."""
    fader = py2tosc.fader(frame=(999, 999, 999, 999))
    ui.resolve(ui.row(fader), (0, 0, 100, 50))
    assert tuple(int(v) for v in fader.frame) == (0, 0, 100, 50)


def test_a_layout_nested_in_a_hand_built_group_still_resolves():
    """Resolution walks the whole tree, not only controls carrying a layout."""
    strip = ui.row(py2tosc.fader(), py2tosc.fader(), frame=(0, 0, 200, 100))
    panel = py2tosc.group(frame=(0, 0, 400, 400), children=[strip])
    ui.resolve(panel)
    assert frames(strip) == [(0, 0, 100, 100), (100, 0, 100, 100)]


def test_a_hand_placed_control_keeps_its_frame():
    """Only a layout places its children; a plain group leaves them alone."""
    fader = py2tosc.fader(frame=(10, 20, 30, 40))
    ui.resolve(py2tosc.group(frame=(0, 0, 400, 400), children=[fader]))
    assert tuple(int(v) for v in fader.frame) == (10, 20, 30, 40)


def test_resolve_returns_the_control_it_placed():
    strip = ui.row(py2tosc.fader())
    assert ui.resolve(strip, (0, 0, 10, 10)) is strip


def test_document_resolve_hands_the_root_frame_down_and_chains():
    doc = py2tosc.Document(
        root=ui.row(py2tosc.fader(), py2tosc.fader(), frame=(0, 0, 800, 600))
    )
    assert doc.resolve() is doc
    assert frames(doc.root) == [(0, 0, 400, 600), (400, 0, 400, 600)]


# -- the layout must not reach the file --------------------------------------


def test_a_layout_is_not_written_to_the_file():
    """`_layout` rides on a private attribute, which the codec cannot see.

    `_write_control` serializes properties, values, messages and children and
    nothing else, so the spec has no route into a `.tosc`.
    """
    doc = py2tosc.Document(
        root=ui.row(py2tosc.fader(name="a"), frame=(0, 0, 100, 100), name="strip")
    )
    doc.resolve()
    text = doc.dumps()

    assert "_layout" not in text
    assert "row" not in text
    assert py2tosc.loads(text).find("a") is not None


def test_a_layout_survives_a_round_trip_as_plain_frames():
    doc = py2tosc.Document(
        root=ui.column(
            py2tosc.fader(name="a"), py2tosc.fader(name="b"), frame=(0, 0, 100, 400)
        )
    )
    doc.resolve()
    reloaded = py2tosc.loads(doc.dumps())
    assert frames(reloaded.root) == [(0, 0, 100, 200), (0, 200, 100, 200)]


def test_copy_carries_the_layout():
    """A copied layout is still a layout, and resolves on its own terms."""
    strip = ui.row(py2tosc.fader(), py2tosc.fader(), gap=10)
    clone = strip.copy()
    ui.resolve(clone, (0, 0, 210, 100))
    assert frames(clone) == [(0, 0, 100, 100), (110, 0, 100, 100)]


# -- validation --------------------------------------------------------------


def test_an_unresolved_layout_warns():
    """Otherwise it fails silently: an unset frame reads back as all zeroes."""
    doc = py2tosc.Document(root=ui.row(py2tosc.fader(), frame=(0, 0, 100, 100)))
    found = doc.validate()
    assert len(found) == 1
    assert "never resolved" in found[0].message


def test_a_resolved_layout_is_clean():
    doc = py2tosc.Document(root=ui.row(py2tosc.fader(), frame=(0, 0, 100, 100)))
    assert doc.resolve().validate() == []


def test_saving_does_not_resolve():
    """Writing a file must not change the tree; that is the round-trip claim."""
    doc = py2tosc.Document(root=ui.row(py2tosc.fader(), frame=(0, 0, 100, 100)))
    doc.dumps()
    assert len(doc.validate()) == 1


# -- idioms ------------------------------------------------------------------


def test_inset_shrinks_a_control_within_the_frame_it_is_given():
    """An inset is a fraction, because a deferred layout has no pixels yet.

    `pad` cannot say this: the size to take a fraction of is not known until
    the frame comes down from above.
    """
    fader = ui.inset(py2tosc.fader(), 0.1)
    ui.resolve(ui.row(fader), (0, 0, 200, 100))
    assert tuple(int(v) for v in fader.frame) == (20, 10, 160, 80)


def test_inset_applies_to_one_child_and_not_its_siblings():
    """The thing `stack(pad=...)` cannot express, and a key caption needs."""
    button = py2tosc.button()
    caption = ui.inset(py2tosc.label(), 0.25)
    ui.resolve(ui.stack(button, caption), (0, 0, 80, 40))
    assert tuple(int(v) for v in button.frame) == (0, 0, 80, 40)
    assert tuple(int(v) for v in caption.frame) == (20, 10, 40, 20)


def test_inset_leaves_margins_equal():
    """The numpad hand-rolled this as int(w * inset) and int(w * (1 - 2 * inset)),
    which puts 16 pixels on the left of a 167-wide cell and 18 on the right."""
    caption = ui.inset(py2tosc.label(), 0.1)
    ui.resolve(ui.row(caption), (0, 0, 167, 100))
    x, _, w, _ = (int(v) for v in caption.frame)
    assert x == 167 - x - w


def test_resolving_twice_does_not_shrink_an_inset_control_twice():
    """The inset applies to the frame a parent computed, not to the current one."""
    fader = ui.inset(py2tosc.fader(), 0.1)
    strip = ui.row(fader)
    ui.resolve(strip, (0, 0, 200, 100))
    once = tuple(fader.frame)
    ui.resolve(strip, (0, 0, 200, 100))
    assert tuple(fader.frame) == once


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (0.1, (10, 10, 80, 80)),
        ((0.1, 0.2), (10, 20, 80, 60)),
        ((0, 0, 0.5, 0), (0, 0, 50, 100)),
    ],
)
def test_inset_accepts_one_two_or_four_fractions(amount, expected):
    control = ui.inset(py2tosc.fader(), amount)
    ui.resolve(ui.row(control), (0, 0, 100, 100))
    assert tuple(int(v) for v in control.frame) == expected


def test_an_inset_larger_than_the_frame_raises():
    control = ui.inset(py2tosc.fader(), 0.6)
    with pytest.raises(ValueError, match="does not fit"):
        ui.resolve(ui.row(control), (0, 0, 100, 100))


def test_labelled_lays_a_caption_over_a_control():
    button = py2tosc.button(name="key", color="#264653")
    cell = ui.labelled(button, "7")
    ui.resolve(cell, (0, 0, 80, 40))

    assert [c.control_type.value for c in cell] == ["BUTTON", "LABEL"]
    caption = cell[1]
    assert caption.name == "7"
    assert caption.interactive is False
    assert caption.background is False
    assert caption.color == button.color
    assert [v.default for v in caption.values if v.key == "text"] == ["7"]


def test_labelled_insets_only_the_caption():
    button = py2tosc.button()
    cell = ui.labelled(button, "7", inset=0.25)
    ui.resolve(cell, (0, 0, 80, 40))
    assert tuple(int(v) for v in cell[0].frame) == (0, 0, 80, 40)
    assert tuple(int(v) for v in cell[1].frame) == (20, 10, 40, 20)


def test_labelled_costs_no_extra_control_when_inset():
    """An inset rides on the control, so padding a caption adds no group.

    Expressing it as a nested stack would cost one group per key, which on the
    numpad's nine digits is a fifth of the layout.
    """
    plain = ui.labelled(py2tosc.button(), "7")
    padded = ui.labelled(py2tosc.button(), "7", inset=0.1)
    assert len(list(plain.walk())) == len(list(padded.walk())) == 3


# -- pagers ------------------------------------------------------------------


def test_pager_gives_every_page_the_whole_pager():
    """A pager shows one page at a time, so pages share rather than divide."""
    pages = ui.pager(
        ui.row(py2tosc.fader(), py2tosc.fader(), name="1"),
        ui.tiles(py2tosc.button(), columns=2, name="2"),
    )
    ui.resolve(pages, (0, 0, 800, 600))

    assert pages.control_type is py2tosc.ControlType.PAGER
    assert frames(pages) == [(0, 40, 800, 560), (0, 40, 800, 560)]


def test_a_page_lays_its_own_contents_out():
    """The gap this closes: a PAGER carries no layout of its own, so before
    `pager` existed its pages kept whatever frame they were built with -- a
    100x100 default inside an 800x600 pager, which validated clean."""
    page = ui.row(py2tosc.fader(), py2tosc.fader(), name="1")
    ui.resolve(ui.pager(page), (0, 0, 800, 600))
    assert frames(page) == [(0, 0, 400, 560), (400, 0, 400, 560)]


def in_document(pager):
    """A pager the way TouchOSC needs it: inside a group, not as the root."""
    return py2tosc.Document(
        root=ui.stack(pager, name="root", frame=(0, 0, 800, 600))
    ).resolve()


def test_a_pager_of_groups_validates_cleanly():
    assert in_document(ui.pager(ui.row(py2tosc.fader(), name="1"))).validate() == []


def test_a_pager_as_the_root_is_reported():
    """The root is the canvas, and TouchOSC gives it none of its type's
    behaviour: a PAGER there draws its tab bar and then stacks every page
    instead of paging. All 35 corpus layouts root at a GROUP."""
    pages = ui.pager(ui.row(py2tosc.fader(), name="1"), frame=(0, 0, 800, 600))
    found = py2tosc.Document(root=pages).resolve().validate()
    assert len(found) == 1
    assert "the root is a PAGER" in found[0].message


def test_validating_a_subtree_says_nothing_about_the_root():
    """A bare pager is a fine subtree; only a document has a root to be wrong."""
    pages = ui.pager(ui.row(py2tosc.fader(), name="1"), frame=(0, 0, 800, 600))
    ui.resolve(pages)
    assert pages.validate() == []


def test_a_page_that_is_not_a_group_is_reported_not_rejected():
    """TouchOSC tolerates it, so `validate` warns rather than `pager` raising.

    The one warning is about the page itself: the tab properties are
    deliberately not defaulted onto a control that cannot be a page, since that
    would add warnings about properties the type has no use for.
    """
    loose = py2tosc.fader(name="loose")
    found = in_document(ui.pager(loose)).validate()
    assert len(found) == 1
    assert "PAGER pages should be GROUP" in found[0].message
    assert not loose.has("tabLabel")


def test_a_pager_survives_a_round_trip_as_a_pager():
    doc = py2tosc.Document(
        root=ui.pager(ui.row(py2tosc.fader(name="f"), name="1"), frame=(0, 0, 80, 100))
    )
    doc.resolve()
    reloaded = py2tosc.loads(doc.dumps())
    assert reloaded.root.control_type is py2tosc.ControlType.PAGER
    assert frames(reloaded.root) == [(0, 40, 80, 60)]


def test_pages_sit_below_the_tab_bar():
    """A pager draws its tabs across the top and pages get what is left.

    Sizing a page to the whole pager puts it under the tabs. Confirmed against
    `simple_mk2.tosc`, where a 320x480 pager with a 40-point tab bar holds
    pages at (0, 40, 320, 440).
    """
    pages = ui.pager(ui.row(py2tosc.fader(), name="1"), name="p")
    ui.resolve(pages, (0, 0, 320, 480))

    assert pages.get("tabbar") is True and pages.get("tabbarSize") == 40
    assert frames(pages) == [(0, 40, 320, 440)]


def test_a_pager_without_a_tab_bar_gives_pages_everything():
    pages = ui.pager(ui.row(py2tosc.fader(), name="1"), tabbar=False)
    ui.resolve(pages, (0, 0, 320, 480))
    assert frames(pages) == [(0, 0, 320, 480)]


def test_a_taller_tab_bar_leaves_pages_less_room():
    pages = ui.pager(ui.row(py2tosc.fader(), name="1"), tabbar_size=80)
    ui.resolve(pages, (0, 0, 320, 480))
    assert frames(pages) == [(0, 80, 320, 400)]


def test_pad_applies_on_top_of_the_tab_bar():
    pages = ui.pager(ui.row(py2tosc.fader(), name="1"), pad=10)
    ui.resolve(pages, (0, 0, 320, 480))
    assert frames(pages) == [(10, 50, 300, 420)]


def test_a_page_tab_shows_its_name_by_default():
    """`tabLabel` is a different property from `name`, and blank tabs are
    unusable -- which is exactly what the first version of this produced."""
    page = ui.row(py2tosc.fader(), name="1-12")
    ui.pager(page)
    assert page.get("tabLabel") == "1-12"


def test_an_explicit_tab_label_is_left_alone():
    page = ui.row(py2tosc.fader(), name="1", tab_label="FADERS")
    ui.pager(page)
    assert page.get("tabLabel") == "FADERS"


def test_an_unnamed_page_gets_no_tab_label():
    page = ui.row(py2tosc.fader())
    ui.pager(page)
    assert not page.has("tabLabel")


def test_a_page_styles_its_own_tab():
    """Without these the tab bar comes out blank, label and all.

    They belong to the page rather than the pager, so no control type declares
    them as defaults, and a page left without them draws its label in no colour
    at all. The values are the ones roughly a thousand corpus pages agree on.
    """
    page = ui.row(py2tosc.fader(), name="1")
    ui.pager(page)

    assert page.get("tabColorOff") == py2tosc.to_color((0.25, 0.25, 0.25, 1.0))
    assert page.get("tabColorOn") == py2tosc.to_color((0.5, 0.5, 0.5, 1.0))
    assert page.get("textColorOff") == py2tosc.to_color((1.0, 1.0, 1.0, 1.0))
    assert page.get("textColorOn") == py2tosc.to_color((1.0, 1.0, 1.0, 1.0))


def test_explicit_tab_styling_is_left_alone():
    page = ui.row(py2tosc.fader(), name="1", text_color_on="#ff0000")
    ui.pager(page)
    assert page.get("textColorOn") == py2tosc.to_color("#ff0000")
    assert page.get("textColorOff") == py2tosc.to_color((1.0, 1.0, 1.0, 1.0))


def test_a_page_carries_everything_the_editor_writes():
    """The gap that made the first two pagers render wrong: parity is the test.

    Both defects -- pages under the tab bar, and blank tabs -- were structural
    differences from what the editor produces, invisible to `validate` and to a
    round trip. Comparing against a real pager is what finds that class.
    """
    reference = py2tosc.load(EXAMPLES / "simple_mk2.tosc").find(type="PAGER")
    built = ui.pager(
        ui.row(py2tosc.fader(), name="1"), name="pager1", frame=(0, 0, 320, 480)
    )
    ui.resolve(built)

    assert not set(reference[0].properties) - set(built[0].properties)
    assert not set(reference.properties) - set(built.properties)
    # and the geometry the reference uses, not merely the same property names
    assert tuple(built[0].frame) == tuple(reference[0].frame)


def test_a_built_pager_matches_one_the_editor_made():
    """Parity against a minimal pager built by hand in TouchOSC.

    `simple_mk2.tosc` is a large layout whose pager is styled; this one exists
    only to be a working pager, so anything it carries is something a pager
    needs rather than something its author chose. Three defects hid in exactly
    that gap -- pages under the tab bar, blank tabs, and a pager at the root.
    """
    reference = py2tosc.load(DATA / "pager_example.tosc")
    ref_pager = reference.find(type="PAGER")

    built = ui.pager(
        ui.stack(py2tosc.fader(name="fader1"), name="1"),
        ui.stack(py2tosc.radial(name="radial1"), name="2"),
        ui.stack(py2tosc.encoder(name="encoder1"), name="3"),
        name="pager1",
        frame=tuple(ref_pager.frame),
    )
    ui.resolve(py2tosc.group(frame=tuple(reference.root.frame), children=[built]))

    # the same properties, on the pager and on a page
    assert set(built.properties) == set(ref_pager.properties)
    assert set(built[0].properties) == set(ref_pager[0].properties)
    # and the same page geometry, which is where the tab bar shows up
    assert [tuple(p.frame) for p in built] == [tuple(p.frame) for p in ref_pager]
    assert [p.get("tabLabel") for p in built] == ["1", "2", "3"]


def test_the_editor_made_pager_still_validates():
    """It works in TouchOSC, so no rule of ours may object to it."""
    assert py2tosc.load(DATA / "pager_example.tosc").validate() == []


@pytest.mark.parametrize(
    ("orientation", "expected"),
    [
        (0, (0, 40, 320, 440)),  # top, 122 pagers in the corpus
        (1, (0, 0, 280, 480)),  # right, inferred: the only edge left over
        (2, (0, 0, 320, 440)),  # bottom, one pager
        (3, (40, 0, 280, 480)),  # left, two pagers
    ],
)
def test_the_tab_bar_can_sit_on_any_edge(orientation, expected):
    """`orientation` moves the bar, and the page keeps what is left.

    Only the top was implemented at first, which is right for 999 of the 1005
    pages in the corpus and wrong for the other six.
    """
    pages = ui.pager(ui.row(py2tosc.fader(), name="1"), orientation=orientation)
    ui.resolve(pages, (0, 0, 320, 480))
    assert frames(pages) == [expected]


def test_every_pager_page_in_the_corpus_is_reproduced_exactly():
    """The whole rule, checked against every real pager rather than a sample.

    Covers the bar being off (906 pages fill their pager), on at the top (93),
    and on another edge (6) -- the three cases that took four tries to get
    right, all in one assertion.
    """
    from py2tosc._geometry import PAGES, Layout, child_frames

    checked = 0
    for path in CORPUS:
        for control in py2tosc.load(path).walk():
            if control.control_type is not py2tosc.ControlType.PAGER:
                continue
            if not control.children:
                continue
            computed = child_frames(Layout(PAGES), control, len(control.children))
            actual = [tuple(p.frame) for p in control.children]
            assert [tuple(f) for f in computed] == actual, path.name
            checked += len(actual)

    assert checked > 1000, f"only {checked} pages checked"


# -- GRID controls -----------------------------------------------------------


@pytest.mark.parametrize(
    ("sample", "kind"), [("grid-faders", "FADER"), ("grid-encoders", "ENCODER")]
)
def test_a_built_grid_matches_one_the_editor_made(sample, kind):
    """Parity against minimal grids built by hand in TouchOSC.

    A `GRID` writes its cell frames out rather than deriving them, so nothing
    about the file says how they were arrived at -- which makes an editor-made
    example the only way to know.
    """
    reference = py2tosc.load(EXAMPLES / f"{sample}.tosc").find(type="GRID")
    built = ui.grid(kind, columns=2, rows=2, name="grid1")
    ui.resolve(built, tuple(reference.frame))

    assert [tuple(c.frame) for c in built] == [tuple(c.frame) for c in reference]
    assert [c.get("name") for c in built] == [c.get("name") for c in reference]
    assert not set(reference.properties) - set(built.properties)
    assert built.get("gridType") == reference.get("gridType")


def test_grid_cells_are_tiled_not_divided():
    """A GRID leaves a margin all round and gives every cell the same size.

    A layout divides its frame and lets the last slot reach the edge; a GRID
    does not, so the leftover sits at the far edge instead of being shared out.
    """
    built = ui.grid("BUTTON", columns=2, rows=2)
    ui.resolve(built, (0, 0, 240, 240))
    assert frames(built) == [
        (3, 3, 116, 116),
        (122, 3, 116, 116),
        (3, 122, 116, 116),
        (122, 122, 116, 116),
    ]


def test_every_grid_in_the_corpus_is_reproduced():
    """One exception, named rather than tolerated.

    `script_demo.tosc` holds a 5x2 of RADARs whose cells are square rather than
    filling the frame's height. That is how the file was authored, not a rule:
    a 5x2 of ENCODERs generated with filled cells of 120x132 draws as round,
    evenly spaced circles in TouchOSC, so a circular control is inscribed in
    whatever frame it is given. Filling is what the other 36 grids do and what
    this model produces.
    """
    from py2tosc._geometry import CELLS, Layout, child_frames

    squared = {"script_demo.tosc"}
    checked = exceptions = 0
    for path in CORPUS:
        for g in py2tosc.load(path).walk():
            if g.control_type is not py2tosc.ControlType.GRID or not g.children:
                continue
            nx = int(g.get("gridX") or 1)
            ny = int(g.get("gridY") or 1)
            spec = Layout(CELLS, columns=nx, rows=ny)
            ours = {tuple(f) for f in child_frames(spec, g, nx * ny)}
            theirs = {tuple(c.frame) for c in g.children}
            if ours == theirs:
                checked += 1
            else:
                assert path.name in squared, f"{path.name}: {nx}x{ny}"
                exceptions += 1

    assert checked >= 36 and exceptions == 1


def test_grid_type_names_the_control_the_cells_are():
    """The corpus numbers it by the type's position in the format's own order."""
    assert ui.grid("BUTTON", columns=1, rows=1).get("gridType") == 1
    assert ui.grid("LABEL", columns=1, rows=1).get("gridType") == 2
    assert ui.grid("FADER", columns=1, rows=1).get("gridType") == 4
    assert ui.grid("ENCODER", columns=1, rows=1).get("gridType") == 7
    assert ui.grid("RADAR", columns=1, rows=1).get("gridType") == 8


def test_a_grid_fills_itself_with_one_control_type():
    pads = ui.grid("BUTTON", columns=8, rows=8, name="multitoggle")
    assert pads.control_type is py2tosc.ControlType.GRID
    assert len(pads.children) == 64
    assert {c.control_type.value for c in pads} == {"BUTTON"}
    assert [c.get("name") for c in pads][:3] == ["1", "2", "3"]
    assert (pads.get("gridX"), pads.get("gridY")) == (8, 8)


@pytest.mark.parametrize(("columns", "rows"), [(0, 2), (2, 0), (-1, 1)])
def test_a_grid_needs_at_least_one_cell(columns, rows):
    with pytest.raises(ValueError, match="at least one cell"):
        ui.grid("BUTTON", columns=columns, rows=rows)


def test_a_grid_that_cannot_fit_its_cells_raises():
    built = ui.grid("BUTTON", columns=20, rows=20)
    with pytest.raises(ValueError, match="does not fit"):
        ui.resolve(built, (0, 0, 20, 20))


def test_a_grid_survives_a_round_trip():
    doc = py2tosc.Document(
        root=ui.stack(
            ui.grid("BUTTON", columns=4, rows=2, name="pads"),
            frame=(0, 0, 400, 200),
        )
    ).resolve()
    assert doc.validate() == []

    reloaded = py2tosc.loads(doc.dumps()).find(type="GRID")
    assert len(reloaded.children) == 8
    assert reloaded.get("gridType") == 1
