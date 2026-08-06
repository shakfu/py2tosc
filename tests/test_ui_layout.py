"""The layout combinators in `py2tosc.ui`.

These describe an arrangement and assign frames later, which is what lets a
layout be written from the inside out. The rounding invariant is tested first,
because everything else is only correct if the arithmetic is.
"""

import pytest

import py2tosc
from py2tosc import ui
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
    cells = ui.grid(*[py2tosc.button() for _ in range(6)], columns=3)
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
    cells = ui.grid(py2tosc.button(), columns=2, rows=2)
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
    cells = ui.grid(*[py2tosc.button() for _ in range(4)], columns=2, gap=(10, 20))
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
