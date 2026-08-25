"""The optional layout checks.

The governing constraint is that real layouts must come back clean. A validator
that fires on files the TouchOSC editor itself wrote is worse than none, because
it trains you to ignore it -- so the corpus check below is the one that decides
whether a rule is allowed to exist. Two rules were dropped while writing this
for failing it.
"""

from collections import Counter

import pytest

import py2tosc
from _corpus import CORPUS, EDITOR_WRITTEN
from py2tosc import ui
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


#: The editor-written files that warn, and exactly what each is allowed to
#: say. Named rather than tolerated: a rule that starts firing on anything
#: else, or a count that moves, still fails here.
#:
#: `msgs.tosc` holds a dead LOCAL binding. The destination id appears exactly
#: once in the file, inside `dstID`, and its v1 timestamp is later than either
#: control in the layout -- so the destination was deleted, or the message was
#: pasted in from somewhere else. The editor does not garbage collect the
#: binding, which is why the rule fires here without being wrong.
#:
#: The rest hold bindings addressed to a value their control does not have:
#: 104 on labels and 48 on grids, `x` in every case. Each is counted twice
#: because both halves of one message are wrong -- the trigger that would fire
#: it, and the argument it would send -- and they are separate findings, since
#: a binding can have one without the other.
#:
#: These were the reason this rule nearly did not exist. The corpus says the
#: editor writes them deliberately, which by the usual standard here retires a
#: rule; only an experiment could say otherwise, and it did. See
#: `docs/guide/validation.md`.
KNOWN_WARNINGS = {
    "msgs.tosc": {"LocalMessage is addressed to node id": 1},
    "mix_2_mk2.tosc": {"fires on value": 72, "reads value": 72},
    "beatmachine_mk2.tosc": {"fires on value": 36, "reads value": 36},
    "automat5_mk2.tosc": {"fires on value": 22, "reads value": 22},
    "logicpad.tosc": {"fires on value": 10, "reads value": 10},
    "logictouch.tosc": {"fires on value": 4, "reads value": 4},
    "grid-encoders.tosc": {"fires on value": 2, "reads value": 2},
    "grid-faders.tosc": {"fires on value": 2, "reads value": 2},
    "simple_mk2.tosc": {"fires on value": 2, "reads value": 2},
    "controls.tosc": {"fires on value": 1, "reads value": 1},
    "controls.xml": {"fires on value": 1, "reads value": 1},
}


@pytest.mark.parametrize("path", EDITOR_WRITTEN, ids=lambda p: p.name)
def test_editor_written_layouts_are_almost_warning_free(path):
    """The editor's own output must produce no warnings it has not earned.

    This is the standard that keeps the rules honest: a validator that fires on
    a file TouchOSC wrote is usually reporting its own ignorance. It has caught
    real gaps three times -- `centered` on FADER, page styling on GROUP, and
    `gridColor`/`textWrap` when a 1.5.2 sample covering every control type
    joined the corpus.

    Every exception is named rather than tolerated, so a rule that starts
    firing on anything else -- or on one more control than it did -- still
    fails here.
    """
    found = warnings(py2tosc.load(path).validate())
    expected = KNOWN_WARNINGS.get(path.name, {})

    counted: Counter = Counter()
    for issue in found:
        matched = [phrase for phrase in expected if phrase in issue.message]
        assert matched, f"{path.name}: unexpected warning {issue}"
        counted[matched[0]] += 1
    assert counted == Counter(expected), f"{path.name}: {counted} != {expected}"


def test_gamepad_connections_use_the_narrower_field():
    """Gamepads have four slots, not ten; the editor rewrites ten down to four."""
    assert len(py2tosc.GamepadMessage().connections) == 4

    fader = py2tosc.fader()
    fader.messages.append(py2tosc.GamepadMessage(connections="1" * 10))
    found = warnings(fader.validate())
    assert any("connections is 10 characters" in i.message for i in found)


def test_the_whole_corpus_produces_only_known_warnings():
    """Every finding is a real defect in a file, not a gap in the rules."""
    total = [i for p in CORPUS for i in py2tosc.load(p).validate()]
    assert errors(total) == []

    found = warnings(total)
    dead = [i for i in found if "fires on value" in i.message or "reads value" in i.message]

    # 152 bindings addressed to a value their control does not have, each
    # counted twice: the trigger that would fire it, and the argument it
    # would send. Confirmed dead in TouchOSC rather than inferred.
    assert len(dead) == 304
    assert len([i for i in dead if "fires on value" in i.message]) == 152

    messages = sorted(i.message for i in found if i not in dead)
    assert len(messages) == 2

    # A dead LOCAL binding in msgs.tosc, addressed to a control the file does
    # not contain. See KNOWN_WARNINGS above.
    assert "LocalMessage is addressed to node id" in messages[0]

    # o_custom.tosc was written by tosclib 0.3.x's image demo, which gave a BOX
    # a value key of "r". The editor never does that.
    assert "value 'r'" in messages[1]
    assert "BOX" in messages[1]


# -- what a clean layout looks like ------------------------------------------


#: The one type whose defaults do not describe a control that could exist.
#: TouchOSC has no empty GRID -- creating one populates it, and the defaults say
#: 2x2 of gridType 4, which is four faders. `Control` does not invent children
#: for any type, so a bare GRID contradicts its own `gridX`/`gridY` and is
#: reported. Building one through `ui.grid` gives the cells it claims.
INCOMPLETE_BY_DEFAULT = {py2tosc.ControlType.GRID}


def test_a_freshly_built_layout_is_clean():
    doc = py2tosc.Document.new(frame=(0, 0, 800, 600))
    for control_type in py2tosc.ControlType:
        if control_type in INCOMPLETE_BY_DEFAULT:
            continue
        doc.add(py2tosc.Control(control_type, name=control_type.value.lower()))
    assert doc.validate() == []


def test_every_default_control_is_clean():
    """A control built from its own defaults must never fail its own rules."""
    for control_type in py2tosc.ControlType:
        if control_type in INCOMPLETE_BY_DEFAULT:
            continue
        control = py2tosc.Control(control_type)
        assert control.validate() == [], control_type.value


def test_a_bare_grid_is_reported_as_incomplete():
    """The exception above, pinned so it cannot quietly become the rule.

    All 37 grids in the corpus hold exactly `gridX * gridY` children and none
    holds none, so an empty one is not something the editor can produce.
    """
    found = warnings(py2tosc.grid().validate())
    assert len(found) == 1
    assert "should hold 4 controls, but it holds 0" in found[0].message


def test_a_grid_holding_what_it_claims_is_clean():
    filled = py2tosc.grid(
        grid_x=3, grid_y=2, children=[py2tosc.fader() for _ in range(6)]
    )
    assert filled.validate() == []


def test_layout_helpers_produce_clean_output():
    doc = py2tosc.Document.new(frame=(0, 0, 800, 600))
    cells = py2tosc.layout.matrix(doc.root, "BUTTON", columns=3, rows=3)
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


def test_a_local_binding_addressed_nowhere_warns():
    """A stale destination id is invisible otherwise: the message just dies.

    Nothing about the message is malformed, so without this the layout looks
    clean and the binding silently never fires.
    """
    button = py2tosc.button(name="key")
    button.messages.append(py2tosc.LocalMessage(dst_var="text", dst_id="gone"))
    panel = py2tosc.group(name="panel", children=[button])

    found = warnings(panel.validate())
    assert len(found) == 1
    assert "'gone'" in found[0].message


def test_a_local_binding_with_no_destination_yet_is_left_alone():
    """The editor writes half-configured bindings; five are in the corpus.

    An empty `dst_id` is a binding the user has not finished, which is a normal
    intermediate state rather than a defect.
    """
    button = py2tosc.button(name="key")
    button.messages.append(py2tosc.LocalMessage(dst_var="text", dst_id=""))
    assert warnings(button.validate()) == []


def test_a_local_binding_within_the_tree_is_clean():
    readout = py2tosc.label(name="readout")
    button = py2tosc.button(name="key")
    button.messages.append(py2tosc.LocalMessage(dst_var="text", dst_id=readout.id))

    panel = py2tosc.group(name="panel", children=[readout, button])
    assert panel.validate() == []


def test_a_copied_subtree_still_validates():
    """The rule and `Control.copy` have to agree, or duplicating a module warns."""
    readout = py2tosc.label(name="readout")
    button = py2tosc.button(name="key")
    button.messages.append(py2tosc.LocalMessage(dst_var="text", dst_id=readout.id))
    panel = py2tosc.group(name="panel", children=[readout, button])

    doc = py2tosc.Document(root=py2tosc.group(name="root", children=[panel]))
    doc.add(panel.copy())
    assert doc.validate() == []


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


def test_a_local_binding_writing_a_value_the_destination_lacks_warns():
    """The dead-but-valid shape: delivered, then discarded.

    Nothing about the message is malformed, so the layout loads, round-trips
    and validates as well formed while the destination never moves.
    """
    readout = py2tosc.label(name="readout")
    button = py2tosc.button(name="key")
    button.messages.append(
        py2tosc.LocalMessage(dst_type="VALUE", dst_var="x", dst_id=readout.id)
    )
    panel = py2tosc.group(name="panel", children=[readout, button])

    found = warnings(panel.validate())
    assert len(found) == 1
    assert "writes value 'x' on a LABEL" in found[0].message
    assert "text, touch" in found[0].message


def test_a_local_binding_writing_a_property_the_destination_lacks_warns():
    target = py2tosc.button(name="pad")
    button = py2tosc.button(name="key")
    button.messages.append(
        py2tosc.LocalMessage(dst_type="PROPERTY", dst_var="nosuch", dst_id=target.id)
    )
    panel = py2tosc.group(name="panel", children=[target, button])

    found = warnings(panel.validate())
    assert len(found) == 1
    assert "writes property 'nosuch'" in found[0].message


def test_a_local_binding_may_address_one_component_of_a_property():
    """`color.a` is the alpha channel; only the root has to exist.

    The corpus writes two of these, so a check on the whole string would fire
    on a file the editor wrote.
    """
    target = py2tosc.button(name="pad")
    button = py2tosc.button(name="key")
    button.messages.append(
        py2tosc.LocalMessage(dst_type="PROPERTY", dst_var="color.a", dst_id=target.id)
    )
    panel = py2tosc.group(name="panel", children=[target, button])
    assert panel.validate() == []


def test_a_half_configured_local_binding_is_left_alone():
    """The editor writes these while a binding is being set up."""
    target = py2tosc.label(name="readout")
    button = py2tosc.button(name="key")
    button.messages.append(
        py2tosc.LocalMessage(dst_type="VALUE", dst_var="", dst_id=target.id)
    )
    panel = py2tosc.group(name="panel", children=[target, button])
    assert panel.validate() == []


def test_a_container_binding_that_fires_on_a_value_it_lacks_warns():
    """The `labelled` trap: the binding lands on the group, not the button.

    `ui.labelled` returns the group holding the control and its caption, so a
    message put there fires on `x` -- which a group does not have. Nothing
    about the layout is malformed and the binding never fires.
    """
    panel = ui.labelled(py2tosc.button(name="play"), "Play")
    panel.messages.append(ui.osc("/play"))
    ui.resolve(panel, (0, 0, 100, 100))

    found = [i.message for i in warnings(panel.validate())]
    # Both halves of the one binding: what would fire it, and what it sends.
    assert any("fires on value 'x' on a GROUP, which carries touch" in m for m in found)
    assert any("reads value 'x' on a GROUP, which carries touch" in m for m in found)


def test_a_binding_that_addresses_a_value_the_control_has_is_clean():
    """Both halves have to be right, which is the point of reporting them apart.

    Moving the trigger to `touch` and leaving the argument on `x` is the
    half-fix that looks done: nothing fires it now, and if anything did it
    would send a zero.
    """
    panel = py2tosc.group(name="panel", frame=(0, 0, 100, 100))
    panel.messages.append(
        ui.osc("/panel", var="touch", args=[ui.value("touch")])
    )
    assert panel.validate() == []

    half_fixed = py2tosc.group(name="half", frame=(0, 0, 100, 100))
    half_fixed.messages.append(ui.osc("/half", var="touch"))
    assert [i.message for i in warnings(half_fixed.validate())] == [
        "OscMessage reads value 'x' on a GROUP, which carries touch"
    ]


@pytest.mark.parametrize("kind", [py2tosc.label, py2tosc.text])
def test_a_label_firing_on_x_is_the_case_the_experiment_settled(kind):
    """No carve-out, and this is the shape that nearly earned one.

    A label carries `text` and `touch`. The editor writes 104 bindings that
    fire on `x` anyway, which looked like evidence that a control holds values
    the format never writes down -- so the rule was held to containers until a
    layout was built to ask TouchOSC directly. Two labels differing only in
    their trigger, both written to by the same button: only the one firing on
    `text` sent anything, and it sent `FLOAT(0)` for the `x` it was told to
    read. Both halves dead, and now both reported.
    """
    control = kind(name="readout", frame=(0, 0, 10, 10))
    control.messages.append(ui.osc("/thing"))

    found = [i.message for i in warnings(control.validate())]
    assert any("fires on value 'x'" in m for m in found)
    assert any("reads value 'x'" in m for m in found)


def test_a_binding_reading_a_constant_or_a_property_is_left_alone():
    """Neither says anything about the control's values."""
    label = py2tosc.label(name="readout", frame=(0, 0, 10, 10))
    label.messages.append(
        ui.osc("/{name}", var="text", args=[ui.const("hello"), ui.prop("name"), ui.index()])
    )
    assert label.validate() == []


def test_a_local_binding_sending_a_value_its_control_lacks_warns():
    """The mirror of the destination rule, and what a port to JSON found.

    `ui.connect(source="#7")` reads a bare string as a value key, so a caller
    meaning a constant gets a binding that reads a value the button does not
    have. It sends nothing, and nothing else about the layout is wrong.
    """
    readout = py2tosc.label(name="readout")
    button = py2tosc.button(name="key", messages=[ui.connect(readout, source="#7", to="text")])
    panel = py2tosc.group(name="panel", children=[readout, button], frame=(0, 0, 100, 100))

    found = [i for i in warnings(panel.validate()) if "sends value" in i.message]
    assert len(found) == 1
    assert "sends value '#7' from a BUTTON, which carries touch, x" in found[0].message


def test_a_local_binding_sending_a_constant_or_a_property_is_left_alone():
    """Neither says anything about the control's values."""
    readout = py2tosc.label(name="readout")
    button = py2tosc.button(
        name="key",
        messages=[
            ui.connect(readout, source=ui.const("#7"), to="text"),
            ui.connect(readout, source=ui.prop("name"), to="text"),
        ],
    )
    panel = py2tosc.group(name="panel", children=[readout, button], frame=(0, 0, 100, 100))
    assert not [i for i in warnings(panel.validate()) if "sends value" in i.message]


def test_every_local_binding_in_the_corpus_sends_a_value_its_control_has():
    """The standard this rule had to clear before it was allowed to exist."""
    checked = 0
    for path in CORPUS:
        for control in py2tosc.load(path).walk():
            for message in control.messages:
                if isinstance(message, py2tosc.LocalMessage) and message.value:
                    checked += 1
    assert checked > 350, f"only {checked} bindings checked"

    total = [i for p in CORPUS for i in py2tosc.load(p).validate()]
    assert not [i for i in warnings(total) if "sends value" in i.message]


def test_the_dead_binding_rules_fire_only_where_they_are_named():
    """The standard, restated for the one rule the corpus could not settle.

    It is not "fires on nothing the editor wrote" here, because the editor
    wrote 152 of these. It is that every one of them is in a file this suite
    names, with the count it names -- so the rule stays as narrow as the
    evidence, and a new firing anywhere else fails
    `test_editor_written_layouts_are_almost_warning_free`.
    """
    checked = 0
    for path in CORPUS:
        for control in py2tosc.load(path).walk():
            checked += sum(
                len(getattr(m, "triggers", None) or []) for m in control.messages
            )
    assert checked > 4000, f"only {checked} triggers checked"

    loose = [
        (path.name, issue)
        for path in CORPUS
        for issue in warnings(py2tosc.load(path).validate())
        if ("fires on value" in issue.message or "reads value" in issue.message)
        and path.name not in KNOWN_WARNINGS
    ]
    assert not loose, f"unnamed dead bindings: {loose}"


def test_every_resolvable_local_binding_in_the_corpus_addresses_something_real():
    """The standard this rule had to clear before it was allowed to exist."""
    checked = 0
    for path in CORPUS:
        doc = py2tosc.load(path)
        known = {c.id: c for c in doc.walk()}
        for control in doc.walk():
            for message in control.messages:
                if not isinstance(message, py2tosc.LocalMessage):
                    continue
                if message.dst_id in known and message.dst_var:
                    checked += 1
    assert checked > 350, f"only {checked} bindings checked"

    total = [i for p in CORPUS for i in py2tosc.load(p).validate()]
    assert not [i for i in warnings(total) if "writes value" in i.message]
    assert not [i for i in warnings(total) if "writes property" in i.message]


def test_a_custom_property_shadowing_a_value_warns():
    """`label.text = "hi"` writes a custom property, not the label's text.

    Nothing else catches it: inventing a property is what the format lets a
    script do, so it cannot be told from a typo -- except when the name is one
    the control already has a value for, which is never deliberate. No control
    in the corpus has one.
    """
    control = py2tosc.label(name="cap")
    control.text = "hi"
    doc = py2tosc.Document(root=py2tosc.group(frame=(0, 0, 100, 100), children=[control]))

    issues = doc.validate()
    assert len(issues) == 1
    assert "has the same name as this control's 'text' value" in issues[0].message


def test_setting_the_value_itself_is_clean():
    control = py2tosc.label(name="cap")
    control.value("text").default = "hi"
    doc = py2tosc.Document(root=py2tosc.group(frame=(0, 0, 100, 100), children=[control]))
    assert doc.validate() == []


def test_the_shadowing_rule_fires_on_nothing_in_the_corpus():
    """Every rule here is corroborated against layouts the editor wrote."""
    for path in CORPUS:
        if path.suffix != ".tosc":
            continue
        for issue in py2tosc.load(path).validate():
            assert "has the same name as this control's" not in issue.message, path.name
