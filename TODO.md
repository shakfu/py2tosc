# TODO

Open items only, in the order they are worth doing. Completed work is recorded in `CHANGELOG.md` rather than kept here as ticks.

## Next

- [ ] implement a higher-level .json variant which maps to py2tosc combinators for easier ui definitions.

## Deliberately not yet

- **A gamepad demo.** `GamepadMessage` is read, round-tripped and validated, but nothing in the library ever authors one -- structurally the gap that `controls.py` closed for the six unauthored control types, one layer up. What holds it back is not a game controller: `gamepad.tosc` carries 43 editor-written bindings to model on, and building a layout and confirming it loads needs no hardware at all. It is that only hardware can confirm the last step, that the input actually drives the control, and a demo here exists to be opened rather than to be asserted about. The defect class that made the control sweep pay off is already foreclosed: those six types had no editor-written reference, where a from-scratch `GamepadMessage()` matches the editor's own instance on every field.

- **An validator/oracle for Lua behaviour.** Of the three shapes of behaviourally dead layout, only one became a rule: a local binding writing a value or property the destination does not have. The other two resisted. A payload that can equal the value it overwrites needs the script modelled, and a RISE with no FALL fires on 106 editor-written bindings, so neither is decidable from the document alone. TouchOSC remains the only oracle. Simulating a demo's Lua state machine in its own test is the cheap half, and is what caught all three numpad defects.
