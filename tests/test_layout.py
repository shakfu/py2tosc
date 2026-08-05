"""Layout helpers: frames, gradients and the numpy-free arithmetic."""

import pytest

import py2tosc
from py2tosc import Color, layout


def test_column_fills_the_parent_height():
    parent = py2tosc.group(frame=(0, 0, 400, 900))
    cells = layout.column(parent, sizes=3)

    assert [c.frame for c in cells] == [
        (0, 0, 400, 300),
        (0, 300, 400, 300),
        (0, 600, 400, 300),
    ]
    assert parent.children == cells


def test_column_honours_size_ratios():
    parent = py2tosc.group(frame=(0, 0, 100, 400))
    cells = layout.column(parent, sizes=(1, 2, 1))

    assert [c.frame.h for c in cells] == [100, 200, 100]
    assert sum(c.frame.h for c in cells) == 400


def test_row_fills_the_parent_width():
    parent = py2tosc.group(frame=(0, 0, 900, 200))
    cells = layout.row(parent, sizes=3)

    assert [c.frame for c in cells] == [
        (0, 0, 300, 200),
        (300, 0, 300, 200),
        (600, 0, 300, 200),
    ]


def test_rounding_never_loses_or_gains_pixels():
    parent = py2tosc.group(frame=(0, 0, 100, 1000))
    cells = layout.row(parent, sizes=3)

    assert sum(c.frame.w for c in cells) == 100
    # slots stay adjacent, no gaps or overlaps
    edges = [(c.frame.x, c.frame.x + c.frame.w) for c in cells]
    assert all(a[1] == b[0] for a, b in zip(edges, edges[1:]))


def test_grid_tiles_in_row_major_order():
    parent = py2tosc.group(frame=(0, 0, 400, 300))
    cells = layout.grid(parent, columns=4, rows=3)

    assert len(cells) == 12
    assert cells[0].frame == (0, 0, 100, 100)
    assert cells[3].frame == (300, 0, 100, 100)
    assert cells[4].frame == (0, 100, 100, 100)
    assert cells[-1].frame == (300, 200, 100, 100)


def test_grid_creates_the_requested_control_type():
    parent = py2tosc.group(frame=(0, 0, 200, 200))
    cells = layout.grid(parent, "BUTTON", columns=2, rows=2)
    assert all(c.control_type is py2tosc.ControlType.BUTTON for c in cells)


def test_gradient_endpoints_are_exact():
    colors = layout.gradient("#000000", "#ffffff", 5)
    assert colors[0] == Color(0.0, 0.0, 0.0, 1.0)
    assert colors[-1] == Color(1.0, 1.0, 1.0, 1.0)
    assert colors[2] == pytest.approx((0.5, 0.5, 0.5, 1.0))


def test_gradient_of_one():
    assert layout.gradient("#ff0000", "#00ff00", 1) == [Color(1.0, 0.0, 0.0, 1.0)]


def test_gradient_rejects_zero():
    with pytest.raises(ValueError, match="at least 1"):
        layout.gradient("#000000", "#ffffff", 0)


@pytest.mark.parametrize("direction", ["horizontal", "vertical", "sequential"])
def test_grid_gradient_directions_cover_every_cell(direction):
    parent = py2tosc.group(frame=(0, 0, 300, 300))
    cells = layout.grid(parent, columns=3, rows=3, colors=("#000000", "#ffffff"), direction=direction)

    assert len(cells) == 9
    assert all(isinstance(c.color, Color) for c in cells)
    assert cells[0].color == Color(0.0, 0.0, 0.0, 1.0)


def test_horizontal_gradient_repeats_per_row():
    parent = py2tosc.group(frame=(0, 0, 300, 200))
    cells = layout.grid(parent, columns=3, rows=2, colors=("#000000", "#ffffff"))
    assert cells[0].color == cells[3].color
    assert cells[2].color == cells[5].color


def test_vertical_gradient_is_constant_along_a_row():
    parent = py2tosc.group(frame=(0, 0, 300, 200))
    cells = layout.grid(parent, columns=3, rows=2, colors=("#000000", "#ffffff"), direction="vertical")
    assert cells[0].color == cells[1].color == cells[2].color
    assert cells[0].color != cells[3].color


def test_grid_rejects_an_unknown_direction():
    parent = py2tosc.group(frame=(0, 0, 100, 100))
    with pytest.raises(ValueError, match="gradient direction"):
        layout.grid(parent, direction="diagonal")


def test_sizes_must_be_positive():
    parent = py2tosc.group(frame=(0, 0, 100, 100))
    with pytest.raises(ValueError, match="at least one slot"):
        layout.row(parent, sizes=())
    with pytest.raises(ValueError, match="positive"):
        layout.row(parent, sizes=(0, 0))


def test_nested_layouts_round_trip():
    doc = py2tosc.Document.new(frame=(0, 0, 1600, 1600))
    cells = layout.grid(doc.root, columns=3, rows=3, colors=("#CE6A85", "#5C374C"))
    layout.column(cells[4], "BUTTON", sizes=4, colors=("#CE6A85", "#5C374C"))
    layout.row(cells[6], "FADER", sizes=2, colors=("#CE6A85", "#5C374C"))

    reloaded = py2tosc.loads(doc.dumps())
    assert len(reloaded.find_all()) == 9 + 4 + 2
    assert reloaded.dumps() == doc.dumps()


def test_layout_does_not_import_numpy():
    import sys

    assert "numpy" not in sys.modules or "numpy" not in repr(layout.__dict__)
