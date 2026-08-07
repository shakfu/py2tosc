# TODO

Open items first, in the order they are worth doing. Everything below the rule
is done, kept for the reasoning rather than the tick.

## Next

- [ ] **A command line.** `pyproject.toml` declares no `[project.scripts]`, so
  every job the library does -- inspect a layout, validate it, decompile it,
  convert `.tosc` to `.xml` -- needs a Python script written first. That is
  worst for `to_python`, where you have to write a script to get a script.

  Four subcommands over functions that already exist and are tested:

      py2tosc show mixer.tosc            # what is in it
      py2tosc validate mixer.tosc        # non-zero exit on errors
      py2tosc decompile mixer.tosc       # to_python, to stdout
      py2tosc convert mixer.tosc -o mixer.xml

  Smallest change with the widest reach: it makes the library usable by people
  who will not import it, and `decompile` is the feature most likely to bring
  someone in -- they have a `.tosc` and want to see it as code. Worth reusing
  the demos' argparse shape so the two read alike.

  Plus a fifth that generates rather than reads:

      py2tosc build params.json -o surface.tosc     # MIDI and OSC per parameter

  A JSON list of parameters in, a paged control surface out, each control bound
  to a MIDI CC and an OSC address. `tests/demos/control_surface.py` already
  does exactly this, so the work is mostly deciding what belongs in the
  package. Three things it forces:

  - **The logic has to move out of the demo.** `tests/demos/` is not shipped in
    the wheel, so the CLI cannot import it. The surface-building code wants to
    be a module -- somewhere alongside `ui`, or its own -- with the demo
    reduced to a caller, so the two cannot drift.

  - **The input schema becomes a public contract.** A demo can read whatever
    the file in `tests/data/` happens to contain; a subcommand cannot. Decide
    what a parameter is -- at minimum a name, optionally a CC number, a
    channel, an address -- and reject anything else with a message rather than
    a traceback. Keeping the existing `[{"index": n, "name": "..."}]` shape
    working is the cheap default, since that is what a plugin host exports.

  - **The lessons from the demo are requirements, not niceties.** A parameter
    *index* is a host identifier and not a controller number: the sample file's
    run to 182, well past the 127 a CC allows, so the CC comes from position.
    Names repeat and contain spaces, neither of which an OSC address can carry,
    so they need slugging and numbering. Both are already solved in the demo
    and both are already tested.

  Worth an `--osc-only` or `--midi-only` switch, since the reason to reach for
  this is usually one or the other.

- [ ] **Six control types are never authored by anything**: `BOX`, `ENCODER`,
  `RADAR`, `RADIAL`, `RADIO`, `TEXT`. They are read and round-tripped, never
  built. Every defect found in TouchOSC so far has been in construction rather
  than parsing, and both the pager and the grid hid properties that only
  matter when you create the control -- `tabLabel`, `gridType`, `shape`,
  `orientation`.

  The cheap form is to extend the conformance sweep: construct one of each
  type and diff it against the editor-made instances in the corpus, the way
  `test_simple_mk2_behaves_like_the_original` diffs behaviour rather than
  position. That would surface something like a `RADIAL` needing
  `cursorDisplay` without waiting for someone to hit it.

## Deliberately not yet

- **1.0.** `ui` changed shape four times in two days -- the pager alone took
  four rounds -- and it wants a few more real layouts built on it before the
  API is promised. Nothing about the core is unsettled; it is the young layer
  that should decide the timing.

- **A gamepad demo.** `GamepadMessage` is supported, documented and tested but
  appears in no demo. Demonstrating it needs a game controller, and the tests
  already cover the format side. Left alone on purpose.

---

- [x] Create a py2tosc script which creates `tests/examples/simple_mk2.tosc`

  Done as a demo, `tests/demos/simple_mk2.py`: readable and factored rather
  than a transcription of the file's 853 property assignments. Structural
  equivalence is asserted, not bytes -- same types, names, tab labels and
  message counts, with 77 of 134 controls on exactly the original coordinates
  and 111 within a point.

  The coverage-probe framing is closed too: `to_python` emits a rebuild script
  from any loaded document, and all 43 corpus files round-trip through their
  own generated source. That is the construction check this task was really
  asking for, and it covers every file rather than one.

- [x] data-driven ui creation: auto-generate midi/osc interface from midi or
  osc mapping in json. -- `tests/demos/control_surface.py`, from the plugin
  parameter list already in `tests/data/`.

- [x] Corpus conformance sweep. Swept, and it is thinner than it looked: the
  type-level check already exists (`test_defaults_cover_every_property_the_editor_writes`),
  and a role-level sweep over all 43 files finds exactly one rule -- a `PAGER`
  page needing `tabLabel` and four tab colours -- which `ui.pager` now applies.
  The geometric half was worth more: it found the tab bar orientation defect,
  and every pager page in the corpus is now reproduced exactly. Not worth
  building as infrastructure; worth re-running by hand when a container type
  is added.

- [x] `ui` cannot build a `GRID`. Added as `ui.grid`, reproducing 36 of the
  37 grids in the corpus exactly, including both hand-made examples.

- [x] Whether a circular control forces square grid cells. It does not: a 5x2
  of ENCODERs with filled 120x132 cells draws as round, evenly spaced circles
  in TouchOSC, so the control is inscribed in whatever frame it gets. The one
  square-celled grid in the corpus is how that file was authored.

- [x] Nothing catches a layout that is structurally valid and behaviourally
  dead. Partly closed: of the three shapes named below, the one that survived
  contact with the corpus is now a rule -- a local binding writing a value or
  property the destination does not have. The other two did not: a payload
  that can equal what it overwrites needs the script modelled, and a RISE with
  no FALL fires on 106 editor-written bindings. Lua behaviour still has no
  oracle but TouchOSC.

  Original note: All three numpad defects found in TouchOSC -- leading zeros, a DEL that
  did nothing, a key that could not fire twice -- passed `validate()`,
  round-tripped byte-exactly and satisfied the demo tests. TouchOSC is the only
  real oracle, but the shapes are recognisable: a message whose payload can
  equal the value it overwrites, a trigger with no path back to its start, a
  control wired to a value nothing reads. Simulating a demo's Lua state machine
  in its test is the cheap half of this, and is what caught all three.
