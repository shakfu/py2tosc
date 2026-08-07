# Validation

`validate` checks a layout for things TouchOSC will reject or quietly ignore. It
is advisory and never raises, because the format is deliberately permissive --
TouchOSC accepts properties it does not recognise, which is what makes [custom
properties](custom-properties.md) useful.

```python
doc = py2tosc.load("mixer.tosc")

for issue in doc.validate():
    print(issue)
#> error: root/panel/readout: BOX controls cannot hold children; this one has 2
#> warning: root/panel/pad: property 'textSize' belongs to the format but not to BOX controls
```

Each [`Issue`][py2tosc.Issue] carries a `level`, a `path` naming the control, and
a `message`. Errors sort first.

## What it checks

**Errors** -- things TouchOSC cannot load:

- children on a control type that cannot hold them (only `GROUP`, `GRID` and
  `PAGER` can)
- a property stored under a type the format does not use for that key
- a node id used by more than one control

**Warnings** -- tolerated, but probably not intended:

- a property that belongs to the format but not to this control type, which is
  the `text_size`-on-a-`BOX` case
- a value key the control type does not carry
- a `connections` string that is not 5 or 10 characters wide
- a `PAGER` page that is not a `GROUP`
- a gamepad binding with no target
- a local binding addressed to a node id no control in the layout has
- a root node that is not a `GROUP`
- a `GRID` holding a different number of controls than its `grid_x` and `grid_y` claim
- a local binding writing a value or property the destination does not have
- a layout the combinators described that nobody has resolved
- a custom property named after one of the control's own values

The last six are worth knowing about, because each describes a layout that
loads, round-trips and looks entirely well formed while not working.

The value-shadowing warning catches one specific slip: `label.text = "hi"`
writes a custom property called `text`, but what a label *says* is its `text`
**value**, so the property is stored, ignored by TouchOSC, and drawn as
nothing. Nothing else can catch it -- inventing a property is what the format
lets a script do, so a typo cannot be told from a feature -- except when the
name collides with a value the control already has, which is never deliberate.

The unresolved-layout warning is the odd one out, since it is not about the
file: `save` places whatever is still unplaced, so a layout that draws this
warning will still be written correctly. It reports the tree *in hand*, where
an unset frame reads back as `(0, 0, 0, 0)` rather than raising -- so anything
consulting frames before saving, this checker included, is reading coordinates
that mean nothing yet. Call `resolve` when you want them to mean something.

A stale local destination fails invisibly: nothing about the message is
malformed, so the binding simply never fires. A binding whose destination is
still blank is left alone -- that is one the editor writes while you are part
way through setting it up.

The root node is the canvas, and TouchOSC gives it none of the behaviour its
type would otherwise have. A `PAGER` at the root draws its tab bar and then
stacks every page on top of one another instead of paging between them. Put the
pager inside a `GROUP` and it behaves; every layout in the corpus is built that
way.

A local binding whose `dst_var` names nothing on the destination is delivered
and then discarded, so the control it targets simply never moves. All 358
resolvable local bindings in the corpus address something real. A blank
`dst_var` is left alone, like a blank `dst_id`.

A `GRID` is never empty in TouchOSC -- creating one populates it, and `grid_x`
and `grid_y` say how many controls it holds rather than describing space to be
filled later. A bare [`grid`][py2tosc.grid] says 2x2 of faders in its defaults
and creates none of them, so it is reported;
[`ui.grid`](../api/ui.md) builds one with the cells it claims.

A **custom** property -- a key the format does not define at all -- is never
flagged. That is the distinction the check turns on: `textSize` on a `BOX` is a
real TouchOSC property in the wrong place, while `myThreshold` is a deliberate
extension.

## What it does not check

An empty result is not a promise the layout opens. Validation knows the format,
not the editor: it cannot tell you a frame is off-canvas, a script has a syntax
error, or an OSC address collides with another.

## Where the rules come from

Every rule is corroborated against layouts the TouchOSC editor itself wrote. The
test suite requires all 45 layouts in the corpus to validate without errors, and
the editor-written ones to produce no warnings at all -- a validator that fires
on real files trains you to ignore it.

Two candidate rules were dropped for failing that bar. One flagged OSC bindings
with no triggers as dead; the editor writes 40 of those, send-enabled, so
whatever it means it is not a mistake.

## Refusing to write a broken layout

`save` can check first and write nothing if there are errors, which is the
checkpoint worth using: the mistake is caught before the file exists, rather
than when TouchOSC refuses to open it.

```python
doc.save("out.tosc", validate=True)
#> py2tosc.ValidationError: 1 error(s) in the layout:
#>   error: root/panel/oops: BOX controls cannot hold children; this one has 1
```

Nothing is written when it raises. The
[`ValidationError`][py2tosc.ValidationError] carries every finding on `.issues`,
warnings included, so a caller can report them all.

Warnings alone never block a save. `dumps(validate=True)` does the same for the
string form.

It is off by default, deliberately. A rule in the checker being wrong should not
stop you writing a file -- and these rules have been wrong before, 108 times on
their first run.

Individual controls can be checked on their own, which is useful for a helper
that builds one subtree:

```python
panel.validate()
```
