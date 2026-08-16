"""The `py2tosc` command.

The subcommands are thin over functions tested elsewhere, so what matters here
is the wiring: that each one reaches the right function, writes where it says
it will, and turns a bad file into a message rather than a traceback.
"""

import json

import pytest

import py2tosc
from _corpus import DATA, EXAMPLES
from py2tosc.cli import CANNOT_RUN, INVALID, OK, main


def run(capsys, *argv):
    """Run the command and hand back its exit code and output."""
    code = main([str(a) for a in argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# -- show --------------------------------------------------------------------


def test_show_summarises_and_draws_the_tree(capsys):
    code, out, _ = run(capsys, "show", DATA / "fader_with_label.tosc")
    assert code == 0
    assert "lexml 6" in out
    assert "3 controls" in out and "FADER 1" in out
    assert "2 messages" in out
    assert "fader1" in out and "label1" in out


def test_show_stops_at_the_given_depth(capsys):
    deep = run(capsys, "show", EXAMPLES / "simple_mk2.tosc", "--depth", "1")[1]
    everything = run(capsys, "show", EXAMPLES / "simple_mk2.tosc", "--depth", "0")[1]
    assert len(deep.splitlines()) < len(everything.splitlines())
    assert "multitoggle" in everything and "multitoggle" not in deep


def test_show_reports_scripts(capsys):
    out = run(capsys, "show", DATA / "Numpad_basic.tosc")[1]
    assert "scripts" in out


# -- validate ----------------------------------------------------------------


def test_validate_is_quiet_and_zero_on_a_clean_layout(capsys):
    code, out, _ = run(capsys, "validate", EXAMPLES / "simple_mk2.tosc")
    assert code == 0
    assert "clean" in out


def test_validate_exits_non_zero_on_an_error(capsys, tmp_path):
    broken = py2tosc.Document(root=py2tosc.group(name="root"))
    box = py2tosc.box(name="oops")
    box.add(py2tosc.fader())
    broken.add(box)
    broken.save(tmp_path / "broken.tosc")

    code, out, _ = run(capsys, "validate", tmp_path / "broken.tosc")
    assert code == 1
    assert "cannot hold children" in out


def test_a_warning_alone_does_not_fail(capsys):
    """`msgs.tosc` holds one dead binding and nothing TouchOSC would reject."""
    code, out, _ = run(capsys, "validate", DATA / "msgs.tosc")
    assert code == 0
    assert "warning" in out


# -- decompile ---------------------------------------------------------------


def test_decompile_writes_runnable_python_to_stdout(capsys):
    code, out, _ = run(capsys, "decompile", DATA / "fader_with_label.tosc")
    assert code == 0

    scope: dict = {}
    exec(compile(out, "<generated>", "exec"), scope)  # noqa: S102
    assert len(scope["doc"].find_all()) == 2


def test_decompile_can_write_to_a_file(capsys, tmp_path):
    out = tmp_path / "nested" / "layout.py"
    code, printed, _ = run(
        capsys, "decompile", DATA / "fader_with_label.tosc", "-o", out
    )
    assert code == 0
    assert printed == "", "the script went to the file, not to stdout"
    assert "py2tosc.fader(" in out.read_text()


# -- convert -----------------------------------------------------------------


def test_convert_picks_the_format_from_the_extension(capsys, tmp_path):
    out = tmp_path / "layout.xml"
    assert run(capsys, "convert", DATA / "fader_with_label.tosc", "-o", out)[0] == 0
    assert out.read_text().startswith("<?xml")
    assert len(py2tosc.load(out).find_all()) == 2


def test_convert_needs_somewhere_to_put_it():
    with pytest.raises(SystemExit) as raised:
        main(["convert", str(DATA / "fader_with_label.tosc")])
    assert raised.value.code == CANNOT_RUN


# -- build -------------------------------------------------------------------


def test_build_generates_a_surface(capsys, tmp_path):
    out = tmp_path / "surface.tosc"
    code, printed, _ = run(capsys, "build", DATA / "pro_c_2_fabfilter.json", "-o", out)
    assert code == 0
    assert "54 parameters -> 5 pages" in printed

    doc = py2tosc.load(out)
    assert len(doc.find_all(type="FADER")) == 54
    assert doc.validate() == []


def test_build_defaults_its_output_to_the_build_directory(
    capsys, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "knobs.json").write_text(json.dumps(["Cutoff", "Resonance"]))

    assert run(capsys, "build", tmp_path / "knobs.json")[0] == 0
    assert (tmp_path / "build" / "knobs.tosc").exists()


def test_build_takes_the_namespace_from_the_file_or_the_flag(capsys, tmp_path):
    def prefix_of(*extra):
        out = tmp_path / "s.tosc"
        run(capsys, "build", DATA / "pro_c_2_fabfilter.json", "-o", out, *extra)
        doc = py2tosc.load(out)
        osc = next(
            m
            for m in doc.find_all(type="FADER")[0].messages
            if isinstance(m, py2tosc.OscMessage)
        )
        return osc.path[0].value

    assert prefix_of() == "/proC2Fabfilter/"
    assert prefix_of("--prefix", "Synth/Bank 1") == "/synth/bank1/"


@pytest.mark.parametrize(
    ("flag", "absent"),
    [("--midi-only", py2tosc.OscMessage), ("--osc-only", py2tosc.MidiMessage)],
)
def test_build_can_leave_out_either_binding(capsys, tmp_path, flag, absent):
    out = tmp_path / "s.tosc"
    run(capsys, "build", DATA / "pro_c_2_fabfilter.json", "-o", out, flag)
    doc = py2tosc.load(out)
    assert not [m for c in doc.walk() for m in c.messages if isinstance(m, absent)]


def test_build_cannot_be_asked_for_neither():
    with pytest.raises(SystemExit) as raised:
        main(["build", "x.json", "--midi-only", "--osc-only"])
    assert raised.value.code == CANNOT_RUN


# -- failures read as messages -----------------------------------------------


def test_a_missing_file_is_a_message(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["show", "no-such-file.tosc"])
    assert raised.value.code == CANNOT_RUN
    assert "no such file" in capsys.readouterr().err


def test_a_layout_passed_to_build_is_a_message(capsys):
    """`build` takes JSON. Handing it a `.tosc` is an easy mistake to make."""
    with pytest.raises(SystemExit) as raised:
        main(["build", str(DATA / "fader_with_label.tosc")])
    assert raised.value.code == CANNOT_RUN
    assert "not text" in capsys.readouterr().err


def test_malformed_json_is_a_message(capsys, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{oh no")
    with pytest.raises(SystemExit) as raised:
        main(["build", str(bad)])
    assert raised.value.code == CANNOT_RUN
    assert "not valid JSON" in capsys.readouterr().err


def test_json_of_the_wrong_shape_is_a_message(capsys, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "a list"}')
    with pytest.raises(SystemExit) as raised:
        main(["build", str(bad)])
    assert raised.value.code == CANNOT_RUN
    assert "expected a list" in capsys.readouterr().err


def test_no_command_is_a_usage_error():
    with pytest.raises(SystemExit) as raised:
        main([])
    assert raised.value.code == CANNOT_RUN


def test_the_exit_codes_are_three_distinct_numbers():
    """The codes are a documented contract, so nothing may quietly collide.

    The values match what `grep`, `diff` and `mypy` use: 1 for "what you asked
    about is bad", 2 for "I could not look". A bad command line and an
    unreadable file share 2 deliberately -- no caller acts on the difference,
    and argparse picks 2 for the first of them without being asked.
    """
    assert (OK, INVALID, CANNOT_RUN) == (0, 1, 2)
    assert len({OK, INVALID, CANNOT_RUN}) == 3


def test_a_broken_layout_and_a_missing_file_do_not_share_a_code(capsys, tmp_path):
    """The reason the codes were split.

    Both used to exit 1, so a CI step running `py2tosc validate` could not tell
    a layout it should reject from a path someone typed wrong -- the first is a
    result, the second is the check never having run.
    """
    broken = tmp_path / "broken.tosc"
    doc = py2tosc.Document(root=py2tosc.group(name="root"))
    box = py2tosc.box(name="oops")
    box.add(py2tosc.fader())  # a BOX cannot hold children; TouchOSC refuses it
    doc.add(box)
    doc.save(broken)

    invalid, _, _ = run(capsys, "validate", broken)

    with pytest.raises(SystemExit) as raised:
        main(["validate", str(tmp_path / "absent.tosc")])

    assert invalid == INVALID
    assert raised.value.code == CANNOT_RUN
    assert invalid != raised.value.code


def test_an_unreadable_file_does_not_report_invalid(capsys, tmp_path):
    """A file that is not a layout says nothing about any layout's contents."""
    junk = tmp_path / "junk.tosc"
    junk.write_text("this is not a layout")
    with pytest.raises(SystemExit) as raised:
        main(["validate", str(junk)])
    assert raised.value.code == CANNOT_RUN
    assert "not a readable layout" in capsys.readouterr().err


def test_size_sets_the_canvas(capsys, tmp_path):
    out = tmp_path / "s.tosc"
    names = tmp_path / "p.json"
    names.write_text(json.dumps(["a", "b"]))
    run(capsys, "build", names, "-o", out, "--size", "800x480")
    frame = py2tosc.load(out).root.frame
    assert (int(frame.w), int(frame.h)) == (800, 480)


def test_size_defaults_to_the_shipped_template_size(capsys, tmp_path):
    out = tmp_path / "s.tosc"
    names = tmp_path / "p.json"
    names.write_text(json.dumps(["a"]))
    run(capsys, "build", names, "-o", out)
    frame = py2tosc.load(out).root.frame
    assert (int(frame.w), int(frame.h)) == (568, 320)


@pytest.mark.parametrize("text", ["800", "800x", "wide", "800x0", "-1x40"])
def test_a_bad_size_is_a_usage_error(text, tmp_path, capsys):
    names = tmp_path / "p.json"
    names.write_text(json.dumps(["a"]))
    with pytest.raises(SystemExit) as raised:
        main(["build", str(names), "--size", text])
    assert raised.value.code == CANNOT_RUN
