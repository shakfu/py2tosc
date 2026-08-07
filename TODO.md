# TODO

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
