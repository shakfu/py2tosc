# TODO

Open items only, in the order they are worth doing. Completed work is recorded in `CHANGELOG.md` rather than kept here as ticks.

## Next

Nothing open. The last of it is in `CHANGELOG.md` under Unreleased.

## Deliberately not yet

- **A JSON Schema for the layout description.** Moved here from `Next` once the evidence came in against it. Its remaining value over `scripts/check_json.py` is editor completion while typing, for a hand-author; the dialect's first real consumer generates descriptions programmatically and validates them with the vendored checker, so that person has not shown up yet. The reasoning below still holds and the work is still worth doing if one does.

  The dialect is meant to be written by things that are not Python -- a config file someone has to review, a web tool, a generator -- and all three want completion in an editor and a check before the file reaches the reader. Publishing `schema/ui-json.schema.json`, and admitting the `$schema` key that is refused today, is what serves them. It should be generated rather than written, from the tables the reader already uses -- `_TAGS`, `_OPTIONS`, `_PRODUCES`, `_MESSAGES`, `_PARTIALS`, `_REPEAT_KEYS`, `_CHOICE_KEYS` and `allowed_properties` -- with a test asserting the published file still matches them, which is the drift guard `scripts/check_enums.py` already establishes for the enums.

  Two things make it harder than it looks. The tag-in-key form has no discriminator, so per-tag branches can only be a `oneOf`, and what a validator then says about a bad node is "matched none of 19 schemas" where the reader says `unknown key 'gpa'; did you mean 'pad' or 'gap'?` -- an optional `{"type": "row"}` spelling would fix that, and is the half of this worth deciding first. And a schema cannot check what the reader checks: that a `connect` names exactly one control, that `sizes` matches the child count, that every `$name` is bound by an enclosing repeat, that a `case` selects a branch some `when` holds, that a property value will coerce. So it is completion and shape-checking rather than validation, and saying so in the guide is part of the work. The cost of both rose at 0.5.0, the release that ships the dialect: neither is foreclosed, since `ui_json` keeps `ui`'s carve-out from the stability policy, but a change to how a node may be spelled now costs someone else a rewrite rather than costing nothing.

- **A gamepad demo.** `GamepadMessage` is read, round-tripped and validated, but nothing in the library ever authors one -- structurally the gap that `controls.py` closed for the six unauthored control types, one layer up. What holds it back is not a game controller: `gamepad.tosc` carries 43 editor-written bindings to model on, and building a layout and confirming it loads needs no hardware at all. It is that only hardware can confirm the last step, that the input actually drives the control, and a demo here exists to be opened rather than to be asserted about. The defect class that made the control sweep pay off is already foreclosed: those six types had no editor-written reference, where a from-scratch `GamepadMessage()` matches the editor's own instance on every field.

- **A validator/oracle for Lua behaviour.** Of the three shapes of behaviourally dead layout, only one became a rule: a local binding writing a value or property the destination does not have. The other two resisted. A payload that can equal the value it overwrites needs the script modelled, and a RISE with no FALL fires on 106 editor-written bindings, so neither is decidable from the document alone. TouchOSC remains the only oracle. Simulating a demo's Lua state machine in its own test is the cheap half, and is what caught all three numpad defects.
