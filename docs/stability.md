# Stability

What this library promises not to break, and what it reserves the right to
change. If you are pinning a version or deciding whether to depend on
something, this page is the contract.

## The short version

```text
Covered by the guarantee          Not covered
--------------------------------  ----------------------------------------
py2tosc.<name> for every name     py2tosc.ui.*  -- provisional, see below
  in __all__                      Anything whose name starts with _
py2tosc.layout, .properties,      Anything not in __all__ and not in the
  .surface                          API reference
The API reference, docs/api/      The wording of CLI output
CLI names, flags and exit codes   The wording of validation messages
Byte-exact round trips            Which layouts validate warns about
```

## Versioning

The project follows [semantic versioning](https://semver.org/spec/v2.0.0.html).
Once 1.0 is out, a breaking change to anything in the covered column requires a
major bump. Until then, and this is the current state at 0.3.x, a minor bump
may break the API -- which is what the number below 1 is for.

Depending on py2tosc is therefore `py2tosc>=1,<2` after 1.0, and pinning more
tightly than that before it.

## What counts as the public API

Exactly two things, and they are required to agree:

- every name in `py2tosc.__all__`
- every object the [API reference](api/document.md) documents

This is not a convention that relies on care. `tests/test_api.py` asserts that
everything exported is documented, that everything documented is reachable by
attribute access from a bare `import py2tosc`, and that the reference never
points at a private module. The three used to disagree -- `__all__` listed 48
names against 72 documented objects, and `py2tosc.surface` was documented while
raising `AttributeError` -- which is what the tests now prevent.

Anything else in the package is internal, whether or not its name begins with
an underscore. `py2tosc._geometry` is importable and always will be, because
nothing in Python stops you; that is not the same as it being supported.

## The `py2tosc.ui` carve-out

`py2tosc.ui` is **provisional**. It may change in a minor release, including in
ways that break callers, and it is not covered by the guarantee above.

This is deliberate and the reason is in the layering. `control`, `codec` and
`messages` bind to a file format Hexler defines; they age at the speed of
TouchOSC and there is an external authority to be correct against. `ui` encodes
opinions about how interfaces should be composed -- that a row is a function
returning a group, that layout is described first and sized later -- and
opinions age faster than a format does. Freezing them three releases after they
were written would be a promise made on thin evidence.

The carve-out is cheap to state because the separation already exists in the
code rather than only in this document. The top-level `py2tosc.grid`,
`py2tosc.pager`, `py2tosc.group`, `py2tosc.fader` and `py2tosc.label` are the
`py2tosc.control` constructors, not their same-named counterparts in `ui`.
Nothing unstable leaks into the top-level API by accident, so the rule you have
to remember is the whole of it: **if you reached it through `py2tosc.ui`, it is
provisional.**

Everything `ui` builds is an ordinary `Control`, `OscMessage` or `MidiMessage`.
Nothing it produces can reach a file that hand-written code could not. If a
change to `ui` is ever inconvenient, the documents it built remain valid and
the escape route is to write the dataclasses directly.

## Behavioural guarantees

An API that keeps its signatures and changes what it writes has broken you just
as thoroughly, so three behaviours are covered as well.

**Round trips are byte-exact.** A file written by the TouchOSC editor, loaded
and saved without modification, is reproduced byte for byte. This is the
guarantee the project exists to make and it is checked against every
editor-written layout in the corpus.

There are two deliberate exceptions, both cases of the file holding a number
that should not be preserved: a frame coordinate of `-0`, which survives as the
integer `0`, and a colour component of `-nan(ind)`, which a Windows build of
TouchOSC wrote and which is repaired to `0`. Reproducing either exactly would
mean carrying damage forward. These will not grow without a major bump.

**Loading never rejects a layout TouchOSC accepts.** The format permits
properties nobody has heard of -- that is what makes custom properties useful
-- so unknown properties are read and written back rather than refused.
`validate` is advisory and never raises on its own.

**Correcting a default to match the editor is a fix, not a break.** The point
of the defaults is fidelity to what TouchOSC creates, so a default that
disagrees with the editor is wrong, and changing it is a bug fix even though it
changes what a freshly built control looks like. 0.3.2 corrected four this way.
Such changes are always called out in the changelog with the evidence, and they
never affect loading: a control read from a file keeps what the file said.

## Deprecation

Nothing covered is removed without warning. The sequence is:

1. The replacement ships, and the old name keeps working.
2. The changelog records the deprecation, what replaces it, and the release the
   removal is scheduled for.
3. Where the call site can be reached at runtime, calling the deprecated name
   raises a `DeprecationWarning` naming its replacement.
4. Removal, in a major release and no sooner than one minor release after the
   warning appears.

The test suite runs with `-W error::DeprecationWarning`, so a deprecation the
library itself still depends on internally fails the build rather than being
emitted quietly. That is the intended pressure.

## The command line

`py2tosc` is installed as a console script, which makes it something people put
in shell pipelines. Covered: the subcommand names, their flags, and their exit
codes.

```text
0  did what was asked
1  the layout was read and validate found an error in it
2  the command could not run: bad command line, or unreadable input
```

The distinction between `1` and `2` is part of the guarantee, not an accident
of how the failures happen to be written. `1` is a statement about a layout;
`2` is a statement about never having got as far as one. A caller that cannot
tell those apart cannot tell a layout it should fix from a path it should fix.

The numbers are the ones `grep`, `diff` and `mypy` use for the same two ideas,
which is the point: an exit code nobody expects is worth no more than no exit
code at all.

Not covered: the wording and layout of what is printed. If you are parsing the
human-readable output, expect it to move. `py2tosc validate` exiting zero on
warnings and non-zero on errors is covered; the text of any particular warning
is not.

## Python and TouchOSC versions

Supported Python versions are the ones in the `pyproject.toml` classifiers, and
every one of them runs in CI on each change. Dropping a Python version happens
only in a minor or major release, never a patch, and only after that version
has reached end of life upstream.

The format is verified against TouchOSC 1.5.2.262, which writes `lexml`
version 6. Version 3 files written by older releases are read, and their
version is preserved on save so that editing an old layout does not silently
convert it. Support for reading version 3 is covered by the guarantee.

## What is not promised

Being explicit about the edges, since a guarantee is only as clear as its
boundary:

- **`validate` rules will change.** New rules are added as the corpus teaches
  us more, and a layout clean today may report a warning later. Rules are
  advisory by design; only `save(validate=True)` turns errors into a refusal.
- **Message wording will change.** Both validation messages and error strings.
  Match on the exception type, never on the text.
- **Generated Python will change.** `to_python` aims for readable output, not
  stable output. Regenerating with a new release may produce a different -- and
  hopefully better -- script from the same document.
- **Internal module layout will change.** Where a function lives inside the
  package is not part of the contract; how you reach it through `py2tosc` is.
