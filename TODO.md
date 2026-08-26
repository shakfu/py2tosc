# TODO

Open items only, in the order they are worth doing. Completed work is recorded in `CHANGELOG.md` rather than kept here as ticks.

## Next

- **A JSON Schema for the layout description.** The dialect is meant to be written by things that are not Python -- a config file someone has to review, a web tool, a generator -- and all three want completion in an editor and a check before the file reaches the reader. Publishing `schema/ui-json.schema.json`, and admitting the `$schema` key that is refused today, is what serves them. It should be generated rather than written, from the tables the reader already uses -- `_TAGS`, `_OPTIONS`, `_PRODUCES`, `_MESSAGES`, `_PARTIALS`, `_REPEAT_KEYS`, `_CHOICE_KEYS` and `allowed_properties` -- with a test asserting the published file still matches them, which is the drift guard `scripts/check_enums.py` already establishes for the enums.

  Two things make it harder than it looks. The tag-in-key form has no discriminator, so per-tag branches can only be a `oneOf`, and what a validator then says about a bad node is "matched none of 19 schemas" where the reader says `unknown key 'gpa'; did you mean 'pad' or 'gap'?` -- an optional `{"type": "row"}` spelling would fix that, and is the half of this worth deciding first. And a schema cannot check what the reader checks: that a `connect` names exactly one control, that `sizes` matches the child count, that every `$name` is bound by an enclosing repeat, that a `case` selects a branch some `when` holds, that a property value will coerce. So it is completion and shape-checking rather than validation, and saying so in the guide is part of the work. The cost of both rose at 0.5.0, the release that ships the dialect: neither is foreclosed, since `ui_json` keeps `ui`'s carve-out from the stability policy, but a change to how a node may be spelled now costs someone else a rewrite rather than costing nothing.

- **Make the stamp checkable by the people who write it, and guard the table that decides.** `required_schema` gives a producer the number to stamp and `py2tosc validate` warns when a description understates it, but both rest on `_needs` in `ui_json.py` -- a hand-written record of which schema each spelling arrived in. It is the one table here that cannot be generated from what the reader already knows, because nothing in the reader records *when* a spelling was introduced. A schema bump that forgets to extend it under-reports silently, and a silent under-report reads as a clean bill of health, which is worse than having no check. Two halves, and the second is the one with teeth.

  The documentation half is a recipe for generators, in the guide beside `required_schema`: a program emitting descriptions should assert in its own tests that the file it wrote stamps what it needs.

  ```python
  data = json.loads(generated.read_text())
  assert data["schema"] == py2tosc.ui_json.required_schema(data)
  ```

  That is what turns the convention into something a producer's CI enforces, and it belongs on the producer's side because that is where the file is written. minihost's planned `touch` command is the first caller with a reason to run it -- filed there rather than here, since py2tosc cannot test a file it does not generate.

  The guard half is ours and is the harder one. What is wanted is a test that fails when `SCHEMA` rises without `_needs` gaining a branch, and there is no honest way to derive the answer -- so the cheapest real check is a corpus of descriptions per schema, each declaring the lowest number that builds it, with a test asserting `required_schema` agrees and that every schema in `SCHEMAS` above the floor has at least one description exercising what it added. That makes forgetting an entry a failing test rather than a quiet wrong answer, at the cost of one small file per bump. Worth deciding before the next bump rather than after, since the first bump to get it wrong is the one that discredits the check.

  The limit holds whatever this does: `required_schema` detects spellings, never meanings. A schema that changed what an existing spelling *does* leaves a description textually identical, so no walk over the JSON can see it and the guard above would not either. That class belongs to golden output, and the guide says so.

## Deliberately not yet

- **A gamepad demo.** `GamepadMessage` is read, round-tripped and validated, but nothing in the library ever authors one -- structurally the gap that `controls.py` closed for the six unauthored control types, one layer up. What holds it back is not a game controller: `gamepad.tosc` carries 43 editor-written bindings to model on, and building a layout and confirming it loads needs no hardware at all. It is that only hardware can confirm the last step, that the input actually drives the control, and a demo here exists to be opened rather than to be asserted about. The defect class that made the control sweep pay off is already foreclosed: those six types had no editor-written reference, where a from-scratch `GamepadMessage()` matches the editor's own instance on every field.

- **A validator/oracle for Lua behaviour.** Of the three shapes of behaviourally dead layout, only one became a rule: a local binding writing a value or property the destination does not have. The other two resisted. A payload that can equal the value it overwrites needs the script modelled, and a RISE with no FALL fires on 106 editor-written bindings, so neither is decidable from the document alone. TouchOSC remains the only oracle. Simulating a demo's Lua state machine in its own test is the cheap half, and is what caught all three numpad defects.
