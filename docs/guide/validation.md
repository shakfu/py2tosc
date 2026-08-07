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

The last two are worth knowing about, because both describe a layout that loads,
round-trips and looks entirely well formed while not working.

A stale local destination fails invisibly: nothing about the message is
malformed, so the binding simply never fires. A binding whose destination is
still blank is left alone -- that is one the editor writes while you are part
way through setting it up.

The root node is the canvas, and TouchOSC gives it none of the behaviour its
type would otherwise have. A `PAGER` at the root draws its tab bar and then
stacks every page on top of one another instead of paging between them. Put the
pager inside a `GROUP` and it behaves; every layout in the corpus is built that
way.

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
test suite requires all 23 layouts in the corpus to validate without errors, and
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
