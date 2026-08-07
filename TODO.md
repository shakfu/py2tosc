# TODO

- [ ] Create a py2tosc script which creates `tests/examples/simple_mk2.tosc`

  140 controls, 5 levels deep, 240 messages, a 4-page PAGER, a 64-cell GRID and
  853 property assignments that differ from `defaults_for()`. Decide what it is
  for first: a *demo* must be readable and so will abstract away from the file,
  while a *coverage probe* should be generated rather than written -- a
  `to_python()` emitting a rebuild script would subsume this task and give
  users a `.tosc` decompiler. Either way assert structural equivalence, not
  bytes: the file already round-trips byte-exactly, so what is untested is
  construction, and every remaining property difference is a finding.

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

- [ ] Nothing catches a layout that is structurally valid and behaviourally
  dead. All three numpad defects found in TouchOSC -- leading zeros, a DEL that
  did nothing, a key that could not fire twice -- passed `validate()`,
  round-tripped byte-exactly and satisfied the demo tests. TouchOSC is the only
  real oracle, but the shapes are recognisable: a message whose payload can
  equal the value it overwrites, a trigger with no path back to its start, a
  control wired to a value nothing reads. Simulating a demo's Lua state machine
  in its test is the cheap half of this, and is what caught all three.
