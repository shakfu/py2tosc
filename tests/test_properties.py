"""Property typing, colour and frame coercion, and name translation."""

import pytest

from py2tosc import Color, Frame, Property, PropertyType, to_color, to_frame
from py2tosc.properties import to_camel, to_snake


@pytest.mark.parametrize(
    "snake, camel",
    [
        ("corner_radius", "cornerRadius"),
        ("text_align_h", "textAlignH"),
        ("grid_steps_x", "gridStepsX"),
        ("name", "name"),
        ("cornerRadius", "cornerRadius"),
    ],
)
def test_snake_to_camel(snake, camel):
    assert to_camel(snake) == camel


@pytest.mark.parametrize(
    "camel, snake",
    [
        ("cornerRadius", "corner_radius"),
        ("textAlignH", "text_align_h"),
        ("gridStepsX", "grid_steps_x"),
        ("name", "name"),
    ],
)
def test_camel_to_snake(camel, snake):
    assert to_snake(camel) == snake


@pytest.mark.parametrize(
    "value, expected",
    [
        ((1.0, 0.0, 0.0, 1.0), Color(1.0, 0.0, 0.0, 1.0)),
        ((255, 0, 0, 255), Color(1.0, 0.0, 0.0, 1.0)),
        ((255, 0, 0), Color(1.0, 0.0, 0.0, 1.0)),
        ("#ff0000", Color(1.0, 0.0, 0.0, 1.0)),
        ("ff0000ff", Color(1.0, 0.0, 0.0, 1.0)),
        ((0, 0, 0, 1), Color(0.0, 0.0, 0.0, 1.0)),
    ],
)
def test_to_color(value, expected):
    assert to_color(value) == pytest.approx(expected)


def test_to_color_rejects_bad_input():
    with pytest.raises(ValueError, match="hex"):
        to_color("#abc")
    with pytest.raises(ValueError, match="3 or 4"):
        to_color((1, 2))


def test_to_frame_preserves_sub_pixel_positions():
    """TouchOSC's own layouts hold frames like x=417.439; rounding moves them."""
    assert to_frame((0.4, 1.6, 100.0, 200)) == Frame(0.4, 1.6, 100.0, 200.0)


def test_an_integral_frame_still_compares_as_ints():
    assert to_frame((0, 0, 640, 860)) == (0, 0, 640, 860)
    assert to_frame((0, 0, 640, 860)).w == 640


def test_to_frame_rejects_bad_length():
    with pytest.raises(ValueError, match="4 values"):
        to_frame((0, 0, 100))


def test_frame_and_color_compare_as_tuples():
    assert Frame(0, 0, 10, 20) == (0, 0, 10, 20)
    assert Color(1.0, 0.0, 0.0, 1.0) == (1.0, 0.0, 0.0, 1.0)


@pytest.mark.parametrize(
    "key, value, expected",
    [
        ("name", "a", PropertyType.STRING),
        ("visible", True, PropertyType.BOOLEAN),
        ("textSize", 14, PropertyType.INTEGER),
        ("cornerRadius", 1, PropertyType.FLOAT),
        ("frame", (0, 0, 1, 1), PropertyType.FRAME),
        ("color", (0, 0, 0, 1), PropertyType.COLOR),
        ("textColor", (1, 1, 1, 1), PropertyType.COLOR),
    ],
)
def test_known_keys_get_their_documented_type(key, value, expected):
    assert Property(key, value).type is expected


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, PropertyType.BOOLEAN),
        (3, PropertyType.INTEGER),
        (3.5, PropertyType.FLOAT),
        ("x", PropertyType.STRING),
    ],
)
def test_custom_keys_infer_from_the_python_type(value, expected):
    assert Property("somethingCustom", value).type is expected


def test_custom_key_with_no_representable_type():
    with pytest.raises(TypeError, match="cannot store"):
        Property("custom", {"a": 1})


def test_value_is_coerced_to_match_the_type():
    assert Property("cornerRadius", 1).value == 1.0
    assert Property("textSize", 14.0).value == 14
    assert Property("visible", 1).value is True
    assert Property("frame", [0, 0, 10, 20]).value == Frame(0, 0, 10, 20)


def test_property_python_name():
    assert Property("corner_radius", 1.0).python_name == "corner_radius"
    assert Property("cornerRadius", 1.0).key == "cornerRadius"


def test_property_equality_and_repr():
    assert Property("name", "a") == Property("name", "a")
    assert Property("name", "a") != Property("name", "b")
    assert repr(Property("name", "a")) == "Property('name', 'a', 's')"
