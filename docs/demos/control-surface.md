# Control surface from parameter data

Generate a whole interface from a plugin's parameter list: a fader per parameter, chunked into pages, each bound to both an OSC address and a MIDI CC. Nothing is placed by hand -- the data decides how many pages there are and what is on them.

```python
--8<-- "tests/demos/control_surface.py"
```

```console
$ python tests/demos/control_surface.py tests/data/pro_c_2_fabfilter.json
54 parameters -> 5 pages, 168 controls -> build/control_surface.tosc

$ python tests/demos/control_surface.py params.json synth/bank1 -o surface.tosc
```

The optional third argument is the OSC namespace every address hangs off, and it may be more than one segment deep. It defaults to the file's name, which is convenient and fragile: renaming the data silently moves every address, so anything that has to stay put should say so.

This is the larger sibling of [Faders from JSON](from-json.md), which is the same idea at its smallest: one row, OSC only, using the eager [`layout`](../guide/layouts.md) functions. Here the arrangement is described with the combinators in [`py2tosc.ui`](../api/ui.md) instead, so the pages nest inside the pager as ordinary composition and nothing is sized until `resolve` runs.

## What real data forces

Two details account for most of the code, and both come from the parameter list rather than from TouchOSC.

**Names are for people, addresses are not.** Parameter names contain spaces, and OSC addresses cannot -- the specification also reserves `#`, `*`, `,`, `?`, `[`, `]`, `{` and `}`. Real lists repeat, too: this one has three parameters called `Bypass` and two called `Internal`, which would collide into one address. So each control takes a slug for its `name`, which is what the address is built from, and keeps the original text on its caption.

**A parameter index is not a controller number.** It identifies the parameter to the host, and this file's indices run to 182 -- past the 127 a MIDI CC allows. The CC comes from the parameter's position in the list instead. A plugin exposing more than 128 parameters still gets an OSC binding on every fader; the ones past the end simply go out over OSC alone.
