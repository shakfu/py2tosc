# Layout sizes

Every layout has a size -- the frame on its root control -- and it is the one
decision you cannot defer, because everything inside is positioned within it.

The twenty layouts in `tests/examples/` are the examples TouchOSC ships under
**Help > Examples**, so this page is mostly a reading of what the format's own
designers chose, twenty times over.

## What the size actually is

A layout's frame is a coordinate space, not a pixel count. TouchOSC scales a
layout to the screen that opens it, so a 320x480 layout is not a small layout;
it is one whose coordinates happen to run to 320 and 480.

Two things follow, and they pull in opposite directions.

**The aspect ratio is what carries over to the device.** A 4:3 layout on a
16:9 phone has to lose something -- bars down the sides, or a crop. Matching
the shape of the screen you actually use matters more than matching its
resolution.

**The numbers still matter, because some things do not scale with them.** Font
sizes, margins, corner radii and the 3-point gaps inside a `GRID` are absolute
within the coordinate space. Text at 14pt is a third of the height of a 40pt
label and a twentieth of an 800pt one. Doubling the canvas without doubling
the text sizes makes the text half as large relative to everything around it.

So the canvas is not free, but what it buys is resolution of detail rather
than physical size.

!!! note "Not verified against TouchOSC"

    That a mismatched aspect ratio letterboxes rather than stretches or crops
    is inference from how the examples are built, not something tested on a
    device. Everything else on this page is measured from the files.

## What the official examples do

Three things stand out across all twenty, and the first is the one worth
internalising.

### Size follows purpose, not device

There is no house size. The examples group cleanly by what they are for, and
the shape of each group is the shape of its content rather than the shape of
any screen:

| Kind | Size | Examples |
|------|------|----------|
| General-purpose control surface | 320x480, 480x320, 568x320 | `simple_mk2`, `mix_2_mk2`, `logictouch`, `beatmachine_mk2`, `automat5_mk2` |
| DAW controller | 960x720, 1024x768 | `jog_on_2`, `logicpad` |
| Instrument, where width is the point | 740x345, 980x510 | `hexkeys`, `touchkeys` |
| Monitor strip, meant to sit beside something | 640x305 | `midi_monitor`, `osc_monitor` |
| Single-purpose utility | 500x320 to 640x680 | `radial_hv`, `sensors`, `time_battery`, `multi_xy`, `gamepad`, `pone_for_ong` |
| Scripting demonstration | 720x480 to 850x820 | `script_cracktro`, `script_demo`, `script_keyboard` |

A keyboard is wide because keyboards are wide. A monitor is a strip because it
is meant to sit alongside something else. Start from what the layout is, and
the ratio usually follows without much deliberation.

### The ceiling is 1024x768

Nothing official goes above it. `logicpad` is a 767-control DAW controller and
it stops there; the widest, `touchkeys`, is 980 across. Nothing is 1920x1080.

That is a useful bound: if a design is heading past 1024x768, it is worth a
moment's suspicion, because no example needed to.

### The general-purpose surfaces are all phone-sized, and all paged

The five layouts that do what most people want -- a general control surface --
are the smallest of the lot, and every one pages:

| | Size | Controls | Pages |
|-|------|----------|-------|
| `beatmachine_mk2` | 480x320 | 231 | 4 |
| `logictouch` | 320x480 | 191 | 3 |
| `automat5_mk2` | 568x320 | 153 | 3 |
| `simple_mk2` | 320x480 | 140 | 4 |
| `mix_2_mk2` | 320x480 | 129 | 3 |

A drum machine with 231 controls fits 480x320. So for this kind of layout the
control count is close to irrelevant to the canvas -- what matters is how many
are on screen at once, which is a `PAGER` decision.

It is a tendency rather than a law, and the exceptions say why: `hexkeys` puts
240 controls on 740x345 with no pages at all, because a keyboard has to be
seen at once. Page when the controls fall into groups a user visits one at a
time; do not page an instrument.

## Choosing

1. **Start from what the layout is**, and take the ratio from the table above.
   A screen it has to fit exactly is a second constraint, not the first one.
2. **If it is a general control surface, start at 320x480 or 568x320** and
   reach for pages rather than pixels when it fills up.
3. **Check the smallest text.** Below about 8pt in the coordinate space a
   label stops being readable however the layout scales. The fix is usually
   fewer controls per page; a larger canvas only helps if the extra room goes
   to the text rather than to more controls.
4. **Treat 1024x768 as the ceiling** unless you have a reason no official
   example had.

On step 3, the corpus is a usable measure: across its 2867 labels, text sits
at a median **0.54** of the height of the box holding it, with the middle half
between 0.50 and 0.65. Over the twenty official examples alone it is 0.52.
`simple_mk2` uses 14pt in a 25pt box.

## Setting it

From the command line, on `build`:

```console
$ py2tosc build params.json --size 320x480 --columns 2 --rows 4
$ py2tosc build params.json --size 1024x768 --columns 6 --rows 4
```

From Python, wherever a container takes a frame -- the size belongs to the
root control, and `resolve` hands it down:

```python
doc = py2tosc.Document(root=ui.column(
    *controls, pad=8, gap=8, frame=(0, 0, 320, 480), name="mixer",
))
doc.resolve()
```

On a layout that already exists, it is the root's frame:

```python
doc = py2tosc.load("mixer.tosc")
doc.root.set("frame", (0, 0, 568, 320))
doc.resolve()
```

Resizing this way moves the root but does not re-flow children placed at fixed
coordinates. It re-flows only what `ui` laid out, because only those controls
carry the layout spec that `resolve` reads. For a layout drawn in the editor,
scaling the children is the separate job.

## Checking one

`py2tosc show` prints the root frame first, which is the quickest way to see
what a layout was designed for:

```console
$ py2tosc show tests/examples/simple_mk2.tosc --depth 1
tests/examples/simple_mk2.tosc  lexml 6
  140 controls: BUTTON 100, LABEL 27, GROUP 5, FADER 5, PAGER 1, XY 1, GRID 1
  240 messages: Midi 105, Osc 105, Local 30
  1 scripts

GROUP   'group'  (0, 0, 320, 480)  1 children
  PAGER   'pager1'  (0, 0, 320, 480)  4 children
```

## Every official example

All twenty, widest ratio first. Ratios are the nearest simple fraction, so
`39/22` is 568x320 sitting just off 16:9. Pages counts the outermost `PAGER`
only -- `jog_on_2` nests 113 of them ten levels deep, and its three top-level
pages are the number that means anything.

| Example | Size | Ratio | Controls | Pages |
|---------|------|-------|----------|-------|
| `hexkeys` | 740x345 | 15/7 | 240 | - |
| `midi_monitor` | 640x305 | 21/10 | 24 | - |
| `osc_monitor` | 640x305 | 21/10 | 21 | - |
| `touchkeys` | 980x510 | 25/13 | 48 | - |
| `automat5_mk2` | 568x320 | 39/22 | 153 | 3 |
| `radial_hv` | 500x320 | 25/16 | 9 | - |
| `sensors` | 500x320 | 25/16 | 11 | - |
| `script_cracktro` | 720x480 | 3/2 | 275 | - |
| `beatmachine_mk2` | 480x320 | 3/2 | 231 | 4 |
| `script_demo` | 760x520 | 19/13 | 100 | 2 |
| `logicpad` | 1024x768 | 4/3 | 767 | 5 |
| `jog_on_2` | 960x720 | 4/3 | 3989 | 3 |
| `time_battery` | 500x400 | 5/4 | 9 | - |
| `script_keyboard` | 850x820 | 26/25 | 202 | 2 |
| `pone_for_ong` | 640x640 | 1 | 13 | - |
| `multi_xy` | 500x500 | 1 | 7 | - |
| `gamepad` | 640x680 | 16/17 | 76 | - |
| `logictouch` | 320x480 | 2/3 | 191 | 3 |
| `mix_2_mk2` | 320x480 | 2/3 | 129 | 3 |
| `simple_mk2` | 320x480 | 2/3 | 140 | 4 |

The files in `tests/data/` are a different thing -- fixtures inherited from
tosclib, plus layouts written to exercise one corner of the format. The eight
at 640x860 are fixtures, and none of those sizes is a design decision.
