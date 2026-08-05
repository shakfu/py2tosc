"""The optional layout checks.

The governing constraint is that real layouts must come back clean. A validator
that fires on files the TouchOSC editor itself wrote is worse than none, because
it trains you to ignore it -- so the corpus check below is the one that decides
whether a rule is allowed to exist. Two rules were dropped while writing this
for failing it.
"""

import pytest

import py2tosc
from _corpus import CORPUS, EDITOR_WRITTEN
from py2tosc.validate import ERROR, WARNING


def errors(issues):
    return [i for i in issues if i.level == ERROR]


def warnings(issues):
    return [i for i in issues if i.level == WARNING]


# -- the corpus must come back clean ----------------------------------------


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: p.name)
def test_no_real_layout_produces_an_error(path):
    """Every layout in the corpus, editor-written or not, must be error-free.

    An error means "TouchOSC cannot load this", and all of these demonstrably
    load, so any error here is a bug in the rules rather than in the file.
    """
    found = errors(py2tosc.load(path).validate())
    assert not found, f"{path.name}: {[str(i) for i in found]}"


@pytest.mark.parametrize("path", EDITOR_WRITTEN, ids=lambda p: p.name)
def test_editor_written_layouts_are_almost_warning_free(path):
    """The editor's own output must produce no warnings at all.

    This is the standard that keeps the rules honest: a validator that fires on
    a file TouchOSC wrote is reporting its own ignorance. It has caught real
    gaps three times -- `centered` on FADER, page styling on GROUP, and
    `gridColor`/`textWrap` when a 1.5.2 sample covering every control type
    joined the corpus.
    """
    assert len(warnings(py2tosc.load(path).validate())) == 0


def test_gamepad_connections_use_the_narrower_field():
    """Gamepads have four slots, not ten; the editor rewrites ten down to four."""
    assert len(py2tosc.GamepadMessage().connections) == 4

    fader = py2tosc.fader()
    fader.messages.append(py2tosc.GamepadMessage(connections="1" * 10))
    found = warnings(fader.validate())
    assert any("connections is 10 characters" in i.message for i in found)


def test_the_whole_corpus_produces_one_known_warning():
    total = [i for p in CORPUS for i in py2tosc.load(p).validate()]
    assert errors(total) == []

    found = warnings(total)
    assert len(found) == 1
    # o_custom.tosc was written by tosclib 0.3.x's image demo, which gave a BOX
    # a value key of "r". The editor never does that.
    assert "value 'r'" in found[0].message
    assert "BOX" in found[0].message


# -- what a clean layout looks like ------------------------------------------


def test_a_freshly_built_layout_is_clean():
    doc = py2tosc.Document.new(frame=(0, 0, 800, 600))
    for control_type in py2tosc.ControlType:
        doc.add(py2tosc.Control(control_type, name=control_type.value.lower()))
    assert doc.validate() == []


def test_every_default_control_is_clean():
    """A control built from its own defaults must never fail its own rules."""
    for control_type in py2tosc.ControlType:
        control = py2tosc.Control(control_type)
        assert control.validate() == [], control_type.value


def test_layout_helpers_produce_clean_output():
    doc = py2tosc.Document.new(frame=(0, 0, 800, 600))
    cells = py2tosc.layout.grid(doc.root, "BUTTON", columns=3, rows=3)
    py2tosc.layout.row(doc.root, "FADER", sizes=4)
    assert cells
    assert doc.validate() == []


# -- each rule, one at a time ------------------------------------------------


def test_a_format_property_on_the_wrong_control_type_warns():
    box = py2tosc.box()
    box.text_size = 99
    box.grid_steps = 5

    found = warnings(box.validate())
    assert {i.message.split("'")[1] for i in found} == {"textSize", "gridSteps"}
    assert errors(box.validate()) == []


def test_a_custom_property_is_left_alone():
    """Custom properties are a supported feature, not a mistake."""
    group = py2tosc.group()
    group.set("myThreshold", 0.5)
    group.set("CustomProperty", "1007")
    assert group.validate() == []


def test_a_property_stored_under_the_wrong_type_is_an_error():
    control = py2tosc.fader()
    control.set("textSize", 14, type="s")  # the format says integer

    found = errors(control.validate())
    assert len(found) == 1
    assert "textSize" in found[0].message and "'i'" in found[0].message


def test_ambiguous_keys_are_not_flagged():
    """`gridX` is a count on a GRID and a switch on an XY; neither is wrong."""
    assert errors(py2tosc.grid(grid_x=4).validate()) == []
    assert errors(py2tosc.xy(grid_x=True).validate()) == []


def test_children_on_a_non_container_is_an_error():
    box = py2tosc.box()
    box.add(py2tosc.fader())

    found = errors(box.validate())
    assert len(found) == 1
    assert "cannot hold children" in found[0].message


@pytest.mark.parametrize("container", ["GROUP", "GRID", "PAGER"])
def test_containers_may_hold_children(container):
    parent = py2tosc.Control(container)
    parent.add(py2tosc.group(name="page"))
    assert errors(parent.validate()) == []


def test_a_pager_page_that_is_not_a_group_warns():
    pager = py2tosc.pager()
    pager.add(py2tosc.fader(name="oops"))

    found = warnings(pager.validate())
    assert any("PAGER pages should be GROUP" in i.message for i in found)


def test_an_unexpected_value_key_warns():
    fader = py2tosc.fader()
    fader.values.append(py2tosc.Value(key="text", default="nope"))

    found = warnings(fader.validate())
    assert any("value 'text'" in i.message for i in found)


def test_duplicate_node_ids_are_an_error():
    doc = py2tosc.Document.new()
    original = py2tosc.fader(name="a")
    doc.add(original, original.copy(new_ids=False, name="b"))

    found = errors(doc.validate())
    assert len(found) == 1
    assert "node id" in found[0].message and "2 controls" in found[0].message


def test_copy_avoids_the_duplicate_id_error():
    doc = py2tosc.Document.new()
    original = py2tosc.fader(name="a")
    doc.add(original, original.copy(name="b"))
    assert doc.validate() == []


def test_an_odd_connections_width_warns():
    fader = py2tosc.fader()
    fader.messages.append(py2tosc.OscMessage(connections="111"))

    found = warnings(fader.validate())
    assert any("connections is 3 characters" in i.message for i in found)
    assert any("5 or 10" in i.message for i in found)


@pytest.mark.parametrize("width", [5, 10])
def test_both_real_connection_widths_are_accepted(width):
    fader = py2tosc.fader()
    fader.messages.append(py2tosc.OscMessage(connections="1" * width))
    assert fader.validate() == []


def test_a_gamepad_binding_with_no_target_warns():
    fader = py2tosc.fader()
    fader.messages.append(py2tosc.GamepadMessage(target_var=""))

    found = warnings(fader.validate())
    assert any("target_var" in i.message for i in found)


# -- shape of the result -----------------------------------------------------


def test_issues_name_the_control_by_path():
    doc = py2tosc.Document.new(name="root")
    panel = py2tosc.group(name="panel")
    box = py2tosc.box(name="broken")
    box.text_size = 10
    doc.add(panel)
    panel.add(box)

    found = doc.validate()
    assert found[0].path == "root/panel/broken"


def test_an_unnamed_control_still_gets_a_usable_path():
    doc = py2tosc.Document.new()
    box = py2tosc.box()
    box.text_size = 10
    doc.add(box)
    assert doc.validate()[0].path == "<root>/<BOX>"


def test_errors_sort_before_warnings():
    box = py2tosc.box()
    box.text_size = 10  # warning
    box.add(py2tosc.fader())  # error

    levels = [i.level for i in box.validate()]
    assert levels == sorted(levels, key=lambda level: level != ERROR)
    assert levels[0] == ERROR


def test_issue_is_readable_and_hashable():
    issue = py2tosc.Issue(ERROR, "root/a", "something is wrong")
    assert str(issue) == "error: root/a: something is wrong"
    assert {issue, issue} == {issue}


def test_validate_is_reachable_three_ways():
    doc = py2tosc.Document.new()
    assert doc.validate() == doc.root.validate() == py2tosc.validate(doc) == []


def test_validate_never_raises_on_a_damaged_layout():
    """It reports; it does not become another failure mode."""
    doc = py2tosc.loads(
        "<lexml version='6'><node ID='a' type='BOX'><children>"
        "<node ID='a' type='FADER'/></children></node></lexml>"
    )
    issues = doc.validate()
    assert len(errors(issues)) == 2  # children on a BOX, and a duplicated id


# -- refusing to write a broken layout ---------------------------------------


def test_save_with_validate_refuses_and_writes_nothing(tmp_path):
    doc = py2tosc.Document.new()
    broken = py2tosc.box(name="oops")
    broken.add(py2tosc.fader())
    doc.add(broken)

    out = tmp_path / "broken.tosc"
    with pytest.raises(py2tosc.ValidationError) as caught:
        doc.save(out, validate=True)

    assert not out.exists(), "nothing may be written when validation fails"
    assert "cannot hold children" in str(caught.value)
    assert len(caught.value.issues) == 1


def test_save_without_validate_still_writes(tmp_path):
    """The default stays permissive: a wrong rule must not block a save."""
    doc = py2tosc.Document.new()
    broken = py2tosc.box(name="oops")
    broken.add(py2tosc.fader())
    doc.add(broken)

    out = tmp_path / "broken.tosc"
    doc.save(out)
    assert out.exists()


def test_validate_on_save_passes_a_clean_layout(tmp_path):
    doc = py2tosc.Document.new()
    doc.add(py2tosc.fader(name="a"))

    out = tmp_path / "clean.tosc"
    doc.save(out, validate=True)
    assert py2tosc.load(out).find("a") is not None


def test_warnings_alone_do_not_block_a_save(tmp_path):
    """Only errors stop a write; warnings are advice."""
    doc = py2tosc.Document.new()
    odd = py2tosc.box(name="odd")
    odd.text_size = 12  # a warning, not an error
    doc.add(odd)

    out = tmp_path / "warned.tosc"
    doc.save(out, validate=True)
    assert out.exists()
    assert warnings(doc.validate())


def test_dumps_can_validate_too():
    doc = py2tosc.Document.new()
    broken = py2tosc.box()
    broken.add(py2tosc.fader())
    doc.add(broken)

    with pytest.raises(py2tosc.ValidationError):
        doc.dumps(validate=True)
    assert doc.dumps()  # unchecked still works


def test_validation_error_carries_warnings_as_well():
    doc = py2tosc.Document.new()
    broken = py2tosc.box(name="oops")
    broken.text_size = 12  # warning
    broken.add(py2tosc.fader())  # error
    doc.add(broken)

    with pytest.raises(py2tosc.ValidationError) as caught:
        doc.dumps(validate=True)

    levels = {i.level for i in caught.value.issues}
    assert levels == {ERROR, WARNING}
