"""The Control API: property access, traversal and copying."""

import pytest

import py2tosc
from _corpus import DATA
from py2tosc import ControlType


def test_factories_apply_type_defaults():
    f = py2tosc.fader()
    assert f.control_type is ControlType.FADER
    assert f.grid_steps == 13  # what the editor creates a FADER with
    assert f.response_factor == 100
    assert f.bar is True


def test_properties_are_reachable_in_snake_case():
    f = py2tosc.fader()
    f.corner_radius = 2.0
    f.grid_steps = 7

    assert f.corner_radius == 2.0
    # ...and stored under the camelCase key the file format uses
    assert "cornerRadius" in f.properties
    assert "gridSteps" in f.properties
    assert "corner_radius" not in f.properties


def test_camel_case_keys_also_work():
    f = py2tosc.fader()
    f.set("gridSteps", 7)
    assert f.grid_steps == 7
    assert f.get("grid_steps") == 7


def test_keyword_arguments_set_properties():
    f = py2tosc.fader(name="cutoff", frame=(0, 0, 50, 200), corner_radius=1.5)
    assert f.name == "cutoff"
    assert f.frame == (0, 0, 50, 200)
    assert f.corner_radius == 1.5


def test_unknown_property_raises_rather_than_returning_none():
    f = py2tosc.fader()
    with pytest.raises(AttributeError, match="no property 'nonsense'"):
        f.nonsense
    assert f.get("nonsense") is None
    assert f.get("nonsense", 5) == 5


def test_custom_properties_are_allowed():
    g = py2tosc.group()
    g.set("myConfigValue", "1007")
    assert g.my_config_value == "1007"
    assert g.properties["myConfigValue"].type.value == "s"


def test_setting_a_property_twice_replaces_it():
    f = py2tosc.fader()
    f.frame = (0, -200, 40, 200)
    f.frame = (0, 0, 69, 420)
    assert f.frame == (0, 0, 69, 420)
    assert len([p for p in f.properties if p == "frame"]) == 1


def test_delete_property():
    f = py2tosc.fader(name="x")
    assert f.delete("name") is True
    assert f.delete("name") is False
    assert f.has("name") is False


def test_children_and_traversal():
    root = py2tosc.group(name="root")
    inner = py2tosc.group(name="inner")
    leaf = py2tosc.button(name="leaf")

    root.add(inner)
    inner.add(leaf)

    assert len(root) == 1
    assert list(root) == [inner]
    assert [c.get("name") for c in root.walk()] == ["root", "inner", "leaf"]
    assert root.find("leaf") is leaf
    assert root.find("missing") is None


def test_find_all_by_type():
    root = py2tosc.group()
    root.add(py2tosc.fader(name="a"), py2tosc.button(name="b"), py2tosc.fader(name="c"))

    faders = root.find_all(type=ControlType.FADER)
    assert [f.name for f in faders] == ["a", "c"]
    assert root.find_all(type="BUTTON")[0].name == "b"
    assert root.find("a", type="BUTTON") is None


def test_find_excludes_the_control_itself():
    root = py2tosc.group(name="root")
    assert root.find("root") is None
    assert root.find_all() == []


def test_remove_child():
    root = py2tosc.group()
    child = py2tosc.fader()
    root.add(child)
    root.remove(child)
    assert root.children == []
    with pytest.raises(ValueError):
        root.remove(child)


def test_copy_gives_fresh_ids():
    original = py2tosc.group(name="panel")
    original.add(py2tosc.fader(name="a"))

    clone = original.copy()

    assert clone.name == "panel"
    assert clone.id != original.id
    assert clone.children[0].id != original.children[0].id
    assert clone.children[0].name == "a"

    clone.children[0].name = "b"
    assert original.children[0].name == "a"


def test_copy_can_keep_ids_and_override_properties():
    original = py2tosc.fader(name="a")
    clone = original.copy(new_ids=False, name="b")
    assert clone.id == original.id
    assert clone.name == "b"


def _wired_panel():
    """A readout and a button wired to it, the shape a copied module has."""
    readout = py2tosc.label(name="readout")
    button = py2tosc.button(name="key")
    button.messages.append(py2tosc.LocalMessage(dst_var="text", dst_id=readout.id))
    return py2tosc.group(name="panel", children=[readout, button])


def test_copy_repoints_local_messages_at_the_copy():
    """Reminting ids without this leaves the clone driving the original.

    The id it kept still resolves, so nothing looks wrong: the duplicated
    module simply writes into the module it was copied from.
    """
    panel = _wired_panel()
    clone = panel.copy()
    new_readout, new_button = clone.children

    assert new_button.messages[0].dst_id == new_readout.id
    assert new_button.messages[0].dst_id != panel.children[0].id


def test_copy_leaves_the_original_wiring_alone():
    panel = _wired_panel()
    readout, button = panel.children
    panel.copy()
    assert button.messages[0].dst_id == readout.id


def test_copy_preserves_a_destination_outside_the_subtree():
    """An outward binding is a deliberate reference, not a stale id."""
    outside = py2tosc.label(name="outside")
    button = py2tosc.button(name="key")
    button.messages.append(py2tosc.LocalMessage(dst_var="text", dst_id=outside.id))

    clone = py2tosc.group(name="panel", children=[button]).copy()
    assert clone.children[0].messages[0].dst_id == outside.id


def test_copy_without_new_ids_changes_no_wiring():
    panel = _wired_panel()
    clone = panel.copy(new_ids=False)
    assert clone.children[1].messages[0].dst_id == panel.children[0].id


def test_default_values_match_the_control_type():
    assert [v.key for v in py2tosc.fader().values] == ["x", "touch"]
    assert [v.key for v in py2tosc.label().values] == ["text", "touch"]
    assert [v.key for v in py2tosc.group().values] == ["touch"]
    assert py2tosc.fader().value("x").default == 0.0
    assert py2tosc.fader().value("nope") is None


def test_repr_is_useful():
    root = py2tosc.group(name="panel")
    root.add(py2tosc.fader())
    assert repr(root) == "<GROUP 'panel', 1 children>"


# -- defaults against the editor's own one-of-each file -----------------------


def test_defaults_match_a_freshly_made_control_of_each_type():
    """`controls.tosc` holds one of every control type, made in the editor and
    left alone -- `outline` and `background` are still on, so nothing has been
    styled. That makes it the closest thing to a statement of what TouchOSC
    creates each control with.

    Checked for the properties that decide how a control behaves or is drawn,
    not the ones a designer picks: `cornerRadius`, `outline` and `background`
    vary by taste across the corpus and agree with the defaults in this file.
    """
    reference = py2tosc.load(DATA / "controls.tosc")
    behavioural = ("shape", "interactive", "orientation", "textAlignV")

    checked = 0
    for control in reference.walk():
        built = getattr(py2tosc, control.control_type.value.lower())()
        for key in behavioural:
            if not control.has(key) or not built.has(key):
                continue
            # A BOX is the one disagreement, and the corpus sides with the
            # default: 909 of the 910 editor-written boxes are orientation 0,
            # this file holding the only 1.
            if control.control_type is ControlType.BOX and key == "orientation":
                continue
            assert built.get(key) == control.get(key), (
                f"{control.control_type.value}.{key}: built {built.get(key)!r}, "
                f"editor {control.get(key)!r}"
            )
            checked += 1
    assert checked > 40, f"only {checked} comparisons made"


def test_the_circular_controls_are_round():
    """All 171 RADIAL, ENCODER and RADAR controls the editor wrote are shape 2,
    while every rectangular type is 1. A square radial is the same class of
    defect as a pager page with no tab label: valid, and visibly wrong."""
    for kind in ("radial", "encoder", "radar"):
        assert getattr(py2tosc, kind)().get("shape") == 2


def test_decoration_and_containers_do_not_take_touches():
    """A BOX, LABEL, TEXT or GROUP left interactive swallows the press meant
    for what sits beneath it -- the defect that made the simple_mk2 readouts
    eat their own faders' touches."""
    for kind in ("box", "label", "text", "group"):
        assert getattr(py2tosc, kind)().get("interactive") is False
    for kind in ("button", "fader", "radial", "radio"):
        assert getattr(py2tosc, kind)().get("interactive") is True
