# TODO

Open items first, in the order they are worth doing. Everything below the rule
is done, kept for the reasoning rather than the tick.

## Next

- [x] **A command line.** Done: `py2tosc show|validate|decompile|convert|build`,
  registered as a console script. The surface-building logic moved out of the
  demo into `py2tosc.surface` so the subcommand could reach it, and its JSON
  input is now a defined contract with messages rather than tracebacks for
  anything else.

- [x] **Six control types are never authored by anything.** Done, and the
  sweep earned its keep: constructing one of each and diffing it against the
  editor's own instances found four wrong defaults, in the same class as
  `tabLabel` and `gridType` -- properties that only matter when you create the
  control.

  A `RADIAL`, `ENCODER` and `RADAR` are drawn round: all 171 in the corpus are
  `shape` 2 while every rectangular type is 1. A `BOX`, `LABEL`, `TEXT` or
  `GROUP` does not take touches, unanimously across 5134 instances -- the
  defect that made the `simple_mk2` readouts eat their own faders' presses,
  now prevented rather than rediscovered. A `RADIO` runs horizontally or
  vertically and never at `orientation` 0. And `gridSteps` is per type: the
  editor creates a `FADER` with 13 and a `RADIAL` or `ENCODER` with 20, where
  one shared default said 10 for all three.

  The method that worked was not the sweep by itself -- a corpus-wide majority
  confuses a wrong default with a popular style. It was `controls.tosc`: one
  of every control type, made in the editor and left unstyled, which settles
  in one file what a frequency count only suggests. That file is now the
  reference the defaults are tested against.

  The six types are now authored, too: `tests/demos/controls.py` builds one of
  every type on a sheet meant to be opened, which is how the fixes were
  confirmed. It found one more defect on the way -- `label(text="...")` sets a
  custom property rather than the label's `text` value, so every caption on
  the sheet was blank. `validate` now reports that shape.

  Two things the sweep flagged and this deliberately did not change: `outline`
  and `background` disagree with the defaults on ten of thirteen types, but
  `controls.tosc` has both on, so the disagreement is designers turning them
  off rather than a wrong default. `cornerRadius` is the same.

## Deliberately not yet

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
  from any loaded document, and all 45 corpus files round-trip through their
  own generated source. That is the construction check this task was really
  asking for, and it covers every file rather than one.

- [x] data-driven ui creation: auto-generate midi/osc interface from midi or
  osc mapping in json. -- `tests/demos/control_surface.py`, from the plugin
  parameter list already in `tests/data/`.

- [x] Corpus conformance sweep. Swept, and it is thinner than it looked: the
  type-level check already exists (`test_defaults_cover_every_property_the_editor_writes`),
  and a role-level sweep over all 45 files finds exactly one rule -- a `PAGER`
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
