# Demos

Working programs, each in `tests/demos/` in the repository. They take their paths on the command line so you can point them at your own layouts, and each writes to `build/<demo>.tosc` unless you pass `-o`.

| Demo | What it shows |
|------|---------------|
| [Custom property](custom-property.md) | Storing configuration TouchOSC will keep and expose to Lua |
| [Copy scripts](copy-scripts.md) | Pushing one Lua script onto many controls |
| [Faders from JSON](from-json.md) | Building a layout from external data, with OSC addresses |
| [Control surface](control-surface.md) | The same idea in full: paged, labelled, MIDI and OSC |
| [Image converter](image-converter.md) | Generating thousands of controls programmatically |
| [Numpad](numpad.md) | Nested layouts, Lua scripts and LOCAL message wiring |
| [Rebuilding a template](simple-mk2.md) | Authoring a layout TouchOSC ships, from scratch |
| [Reaper to TouchOSC](reaper.md) | Driving the whole thing from a DAW |

The scripts live in `tests/demos/` and the layouts they read are in `tests/data/`, so the test suite runs each one on every commit -- if a demo stops working, CI fails.

!!! note

    These were rewritten for py2tosc. If you are following a tutorial written for tosclib,
    see [Migrating from 0.3](../migrating.md).
