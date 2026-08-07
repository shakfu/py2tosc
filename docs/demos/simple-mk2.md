# Rebuilding a TouchOSC template

`simple_mk2.tosc` is one of the layouts that ships with TouchOSC 1.5: four pages behind a pager, 140 controls, and every binding type the format has. This rebuilds it from nothing, which makes it the widest thing in the repository that py2tosc *authors* rather than edits.

```python
--8<-- "tests/demos/simple_mk2.py"
```

```console
$ python tests/demos/simple_mk2.py
4 pages, 176 controls -> build/simple_mk2.tosc
```

## How close it gets

Same control types, same names, same tab labels, and the same bindings to the message: 105 MIDI, 105 OSC, 30 local. Of the 134 controls that can be compared by position, 77 land on exactly the original coordinates and 111 within a point. Every property deciding what a control *does* matches exactly. `tests/test_demos.py` asserts all of that, so it cannot quietly drift.

That last check exists because the first version of this demo failed it completely. The layout and the wiring were right, and nothing on it moved: the readouts were left interactive, so each one took the touch meant for the control beneath. Three more of the same kind followed -- a fader stays vertical however wide its frame unless `orientation` says otherwise, a button is momentary until `button_type` says it latches, and a caption with no text reads as a missing control rather than an empty one. None of that is visible to validation, to a round trip, or to comparing positions.

Two things differ, on purpose.

**The tree carries more groups** -- 39 against 5 -- because the arrangement is described rather than hand-placed. A fader and its readout are a [`stack`](../api/ui.md); a row of four is a `row`. Each of those is a group the original does not have, and the controls still land in the same places.

**The readouts fill the control they caption**, rather than being small boxes positioned by eye. That is the whole of the remaining 23 differences. A label with no background draws its text in the middle of whatever frame it gets, so it reads the same; matching exactly would mean going back to coordinates, which is the thing the combinators exist to avoid.

## What it exercises

Everything the layout API has: [`pager`](../api/ui.md) for the four pages, [`grid`](../api/ui.md) for the 64-cell matrix, `row`, `column`, `tiles` and `stack` for the rest, and [`resolve`](../api/ui.md) to size it all once the root frame is known. On the message side, `midi_cc`, `midi_note`, `osc` and `connect` cover every binding in the file.

It is also the only demo where controls wire to each other in both directions: the two lock buttons release one another, so both are built before either is wired -- the one place the file forces an ordering.
