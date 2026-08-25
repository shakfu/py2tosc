"""Document creation, traversal and file output."""

import re
import zlib

import pytest

import py2tosc
from _corpus import PROJECT_ROOT


def test_new_document_is_an_empty_group():
    doc = py2tosc.Document.new(frame=(0, 0, 640, 480))
    assert doc.root.control_type is py2tosc.ControlType.GROUP
    assert doc.root.frame == (0, 0, 640, 480)
    assert doc.root.children == []
    assert doc.version == "6"


def test_new_document_declares_the_current_format_version():
    assert "<lexml version='6'>" in py2tosc.Document.new().dumps()


def test_new_document_writes_the_includes_element():
    assert "<includes></includes>" in py2tosc.Document.new().dumps()


def test_a_version_3_layout_keeps_its_version_and_omits_includes():
    doc = py2tosc.loads(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<lexml version='3'><node ID='a' type='GROUP'><properties/></node></lexml>"
    )
    assert doc.version == "3"

    out = doc.dumps()
    assert "<lexml version='3'>" in out
    assert "<includes>" not in out


def test_upgrading_a_layout_adds_includes():
    doc = py2tosc.loads(
        "<?xml version='1.0' encoding='UTF-8'?>"
        "<lexml version='3'><node ID='a' type='GROUP'><properties/></node></lexml>"
    )
    doc.version = "6"
    assert "<includes></includes>" in doc.dumps()


def test_add_and_find():
    doc = py2tosc.Document.new()
    doc.add(py2tosc.fader(name="a"), py2tosc.label(name="b"))

    assert [c.get("name") for c in doc] == ["a", "b"]
    assert doc.find("a").control_type is py2tosc.ControlType.FADER
    assert len(doc.find_all()) == 2
    assert len(list(doc.walk())) == 3  # root included


def test_round_trip_through_tosc(tmp_path):
    doc = py2tosc.Document.new(frame=(0, 0, 800, 600))
    doc.add(py2tosc.fader(name="cutoff", frame=(0, 0, 50, 200), color="#e76f51"))

    path = tmp_path / "layout.tosc"
    doc.save(path)
    reloaded = py2tosc.load(path)

    assert reloaded.dumps() == doc.dumps()
    assert reloaded.find("cutoff").frame == (0, 0, 50, 200)


def test_saved_tosc_is_compressed(tmp_path):
    doc = py2tosc.Document.new()
    path = tmp_path / "layout.tosc"
    doc.save(path)

    raw = path.read_bytes()
    assert raw[0] == 0x78
    assert zlib.decompress(raw).decode().startswith("<?xml")


def test_saved_xml_is_plain_text(tmp_path):
    doc = py2tosc.Document.new()
    path = tmp_path / "layout.xml"
    doc.save(path)

    assert path.read_text().startswith("<?xml")
    assert path.read_text().count("\n") > 1


def test_pretty_overrides_the_extension(tmp_path):
    doc = py2tosc.Document.new()
    path = tmp_path / "layout.xml"
    doc.save(path, pretty=False)
    assert path.read_text().count("\n") == 0


def test_module_level_dumps_and_save(tmp_path):
    doc = py2tosc.Document.new()
    path = tmp_path / "layout.tosc"
    py2tosc.save(doc, path)

    assert py2tosc.dumps(doc) == doc.dumps()
    assert py2tosc.load(path).dumps() == doc.dumps()


def test_deeply_nested_layout_round_trips():
    doc = py2tosc.Document.new()
    node = doc.root
    for depth in range(6):
        child = py2tosc.group(name=f"level{depth}")
        node.add(child)
        node = child
    node.add(py2tosc.button(name="deep"))

    reloaded = py2tosc.loads(doc.dumps())
    assert reloaded.find("deep") is not None
    assert reloaded.dumps() == doc.dumps()


def test_no_foreign_modules_leak_into_the_namespace():
    import types

    public = [n for n in dir(py2tosc) if not n.startswith("_")]
    modules = [n for n in public if isinstance(getattr(py2tosc, n), types.ModuleType)]

    # Submodules of the package are attributes once imported and that is fine.
    # What must not appear is anything py2tosc merely uses: zlib, re, uuid,
    # xml.etree, numpy. 0.3.x exposed all of those.
    assert all(getattr(py2tosc, n).__name__.startswith("py2tosc") for n in modules)


def test_all_is_accurate():
    for name in py2tosc.__all__:
        assert hasattr(py2tosc, name), f"__all__ names {name}, which does not exist"
    assert py2tosc.__version__


def test_version_is_declared_once():
    """`__version__` and pyproject.toml must agree.

    `uv_build` requires a static `version` in pyproject.toml and does not accept
    `dynamic = ["version"]`, so the string necessarily exists in two places.
    This is what stops them drifting.
    """
    pyproject = PROJECT_ROOT / "pyproject.toml"
    if not pyproject.is_file():
        pytest.skip("running against an installed package, not a source tree")

    # Read only the [project] table, so [tool.*] versions cannot be picked up.
    project_table = pyproject.read_text().split("[project]", 1)[1].split("\n[", 1)[0]
    declared = re.search(r'^version = "([^"]+)"', project_table, re.MULTILINE)

    assert declared, "pyproject.toml [project] declares no version"
    assert declared.group(1) == py2tosc.__version__


def test_every_control_type_can_be_created_and_written():
    doc = py2tosc.Document.new()
    for control_type in py2tosc.ControlType:
        doc.add(py2tosc.Control(control_type, name=control_type.value.lower()))

    reloaded = py2tosc.loads(doc.dumps())
    assert len(reloaded.find_all()) == len(py2tosc.ControlType)
    assert reloaded.dumps() == doc.dumps()


def test_unicode_survives_a_round_trip():
    doc = py2tosc.Document.new()
    doc.add(py2tosc.label(name="ünïcodé", tag="a & b < c"))

    reloaded = py2tosc.loads(doc.dumps())
    assert reloaded.find("ünïcodé").tag == "a & b < c"


@pytest.mark.parametrize("text", ["<script>", "a & b", "quote'd"])
def test_special_characters_are_escaped(text):
    doc = py2tosc.Document.new()
    doc.add(py2tosc.group(tag=text))
    assert py2tosc.loads(doc.dumps()).find_all()[0].tag == text


def _one_fader(tmp_path, name="layout.tosc"):
    """A saved layout with a single named fader, for the `edit` tests."""
    doc = py2tosc.Document.new(frame=(0, 0, 640, 480))
    doc.add(py2tosc.fader(name="ch1"))
    path = tmp_path / name
    doc.save(path)
    return path


def test_edit_writes_the_change_back_to_the_same_file(tmp_path):
    path = _one_fader(tmp_path)

    with py2tosc.edit(path) as doc:
        doc.find("ch1").set("name", "kick")

    assert py2tosc.load(path).find("kick") is not None


def test_edit_writes_nothing_when_the_block_raises(tmp_path):
    path = _one_fader(tmp_path)
    before = path.read_bytes()

    with pytest.raises(RuntimeError, match="boom"):
        with py2tosc.edit(path) as doc:
            doc.find("ch1").set("name", "kick")
            raise RuntimeError("boom")

    assert path.read_bytes() == before


def test_edit_round_trips_a_file_it_does_not_change(tmp_path):
    path = _one_fader(tmp_path)
    before = path.read_bytes()

    with py2tosc.edit(path):
        pass

    assert path.read_bytes() == before


def test_edit_save_as_leaves_the_source_alone(tmp_path):
    path = _one_fader(tmp_path)
    before = path.read_bytes()
    other = tmp_path / "copy.xml"

    with py2tosc.edit(path, save_as=other) as doc:
        doc.find("ch1").set("name", "kick")

    assert path.read_bytes() == before
    assert py2tosc.load(other).find("kick") is not None
    # The extension chooses the format on the way out, as `save` does.
    assert other.read_bytes().startswith(b"<?xml")


def test_edit_validate_refuses_to_write_a_broken_layout(tmp_path):
    from py2tosc.validate import ValidationError

    path = _one_fader(tmp_path)
    before = path.read_bytes()

    with pytest.raises(ValidationError):
        with py2tosc.edit(path, validate=True) as doc:
            # A FADER cannot hold children, which `validate` reports as an error.
            doc.find("ch1").add(py2tosc.label(name="nope"))

    assert path.read_bytes() == before


def test_edit_places_a_layout_described_inside_the_block(tmp_path):
    from py2tosc import ui

    path = _one_fader(tmp_path)

    with py2tosc.edit(path) as doc:
        doc.add(
            ui.row(
                py2tosc.button(name="a"),
                py2tosc.button(name="b"),
                frame=(0, 0, 200, 50),
                name="pads",
            )
        )

    # `save` resolves what nobody resolved, so the buttons are not both at the
    # origin -- the same guarantee `Document.save` already makes.
    reloaded = py2tosc.load(path)
    assert reloaded.find("a").frame == (0, 0, 100, 50)
    assert reloaded.find("b").frame == (100, 0, 100, 50)


def test_edit_reports_a_file_it_cannot_read(tmp_path):
    path = tmp_path / "broken.tosc"
    path.write_bytes(b"not a layout")

    with pytest.raises(py2tosc.FormatError):
        with py2tosc.edit(path):
            pytest.fail("the block must not run when the file cannot be read")
