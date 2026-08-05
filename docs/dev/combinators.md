# High-level helpers and combinators

**Status:** design sketch, nothing implemented. This is a working document for discussion, not a commitment to an API.

## The problem

`tests/demos/numpad.py` builds a nine-key numpad in 173 lines. It is the demo that most exercises the library, and reading it shows where the current API makes the caller do work the library could do.

### Messages carry most of the cost

There is no public helper anywhere in the package that turns an OSC address into the partials the format stores. `_default_path` in `messages.py` is private and hardcodes `/<name>`. Anything else is assembled by hand, which is what the messages guide currently teaches:

```python
path=[
    Partial("CONSTANT", "STRING", "/"),
    Partial("PROPERTY", "STRING", "parent.name"),
    Partial("CONSTANT", "STRING", "/"),
    Partial("PROPERTY", "STRING", "name"),
]
```

Four objects and twelve positional arguments to say `/{parent.name}/{name}`.

`LocalMessage` is worse, because it needs seven keyword arguments and a destination id to express one idea. The numpad wraps the pattern once and then repeats it inline three more times:

```python
LocalMessage(
    triggers=[Trigger("x", "RISE")],
    type="PROPERTY", conversion="STRING", value="name",
    dst_type="VALUE", dst_var="text", dst_id=readout.id,
)
```

The `dst_id` requirement also leaks the data model into user code: the destination control must be constructed before anything that talks to it, so the build order is dictated by the wiring rather than by the layout.

### The layout functions do not compose

The changelog describes the layout functions as composable -- "layouts are functions, not decorators ... so nesting is ordinary function composition". They are functions, but they do not compose, because the output type is not an accepted input type:

```
row : (Control, ControlType) -> list[Control]
```

Composition needs `row(column(a, b), c)` to typecheck, which means returning what it accepts. Three consequences follow, all of them visible in the demo:

- **One control type per call.** `_build` in `layout.py` applies a single `control_type` to every slot, so a row holding a fader and a label drops to manual frame arithmetic.

- **The parent must already exist and already have a frame.** Layout is a side effect applied to a tree, not a description of one, which forces outside-in construction.

- **The parent is discarded.** The caller gets the children back and re-derives the structure it just described.

### Two idioms are missing entirely

Padding and insets are hand-rolled:

```python
pad = (int(w * inset), int(h * inset),
       int(w * (1 - 2 * inset)), int(h * (1 - 2 * inset)))
```

So is overlaying, even though a label sitting on a button is the most common control idiom in TouchOSC. The numpad's `key()` helper exists only to place two controls at the same `(0, 0, w, h)`.

## Constraints

Any design has to hold to four things.

**One tree.** Half of what this library is for is editing layouts that already exist, and `load()` returns `Control`s. Helpers that only work on freshly built objects would not apply to loaded ones, which is a bad split.

**Nothing new in the file.** The library's claim is byte-exact round-tripping. Helpers must not write vocabulary into `.tosc` files that TouchOSC has no concept of.

**Additive.** `layout.row`, `layout.column` and `layout.grid` keep working unchanged. Nothing here deprecates them.

**No dependencies.** The package has none, and the arithmetic stays plain Python.

## Where it lives

Proposed: a new `py2tosc.ui` module, exported but documented as unstable while the version is below 1.0.

The reason for keeping it out of the core namespace is that the two layers have different lifespans. `control`, `codec` and `messages` are a binding to a file format someone else defines; they are right or wrong, and they age at the speed of TouchOSC. A combinator layer encodes opinions about how interfaces should be composed, and opinions age faster. Isolating them means the opinionated layer can churn without dragging the core's version with it.

Tier 1 below is the exception worth arguing about, since it only builds structures the format already defines and adds no vocabulary of its own. It could reasonably live in `messages`.

## Tier 1: message combinators

Pure functions returning the existing dataclasses. No new concepts, no architecture change, and by the evidence above the largest reduction in caller code. This tier is worth doing whether or not the rest happens.

### A shared vocabulary for sources

Three constructors, used by both OSC arguments and local messages:

```python
def value(key: str = "x", *, conversion="FLOAT", scale=(0.0, 1.0)) -> Partial
def const(text: str, *, conversion="STRING") -> Partial
def prop(key: str, *, conversion="STRING") -> Partial
```

`scale` unpacks into the `scale_min` and `scale_max` fields, which is the one place the current dataclasses read as two arguments for one idea.

### Addresses

An address mini-syntax where braces mark a property lookup, mirroring f-strings:

```python
osc("/synth/{name}")
```

expands to the four partials the format wants: `CONSTANT "/"`, `CONSTANT "synth"`, `CONSTANT "/"`, `PROPERTY "name"`. The guide's example becomes `osc("/{parent.name}/{name}")`.

```python
def osc(
    address: str = "/{name}",
    *,
    args: Sequence[Partial] | None = None,   # defaults to [value("x")]
    on: str = "ANY",                         # trigger condition
    var: str = "x",                          # watched value
    triggers: list[Trigger] | None = None,   # escape hatch, overrides on/var
    send: bool = True,
    receive: bool = True,
    feedback: bool = False,
    no_duplicates: bool = False,
    connections: str = ALL_CONNECTIONS,
) -> OscMessage
```

`args` defaults to `None` rather than to a literal, because `Partial` is a mutable dataclass and a shared default would be aliased across every message.

### MIDI

```python
def midi_cc(controller: int, *, channel=0, scale=(0, 127), var="x", **flags) -> MidiMessage
def midi_note(note: int, *, channel=0, scale=(0, 127), var="x", **flags) -> MidiMessage
```

These cover the two bindings that account for nearly all MIDI use. Anything else keeps constructing `MidiMessage` directly.

### Local wiring

```python
def connect(
    dst: Control | str,
    *,
    send: Partial | str = "x",     # bare str means value(str)
    to: Partial | str = "x",       # bare str means a VALUE target
    on: str = "ANY",
    var: str = "x",
) -> LocalMessage
```

Reusing `value`, `const` and `prop` for both ends means one vocabulary covers OSC arguments and local wiring. The numpad's four wiring sites become:

```python
connect(readout, send=prop("name"), to="text", on="RISE")
connect(readout, send=const("0"),   to=prop("sum"), on="RISE")
connect(readout, send=const(""),    to="text", on="FALL")
```

`dst` accepts a `Control` and reads its `id`, or a raw id string.

## Tier 2: layout by deferred resolution

The tension to resolve is that eager sizing and inside-out composition are incompatible. `row(a, b)` cannot assign frames unless it knows its own frame, which it only learns from a parent that does not exist yet.

The fix is to separate description from placement. The combinators build an ordinary `Control` tree and record the intent; a single pass assigns frames afterwards, top-down, once the root frame is known.

### Constructors

```python
def row(*children: Control, sizes=None, gap=0, pad=0, **props) -> Control
def column(*children: Control, sizes=None, gap=0, pad=0, **props) -> Control
def grid(*children: Control, columns=4, rows=None, gap=0, pad=0, **props) -> Control
def stack(*children: Control, pad=0, **props) -> Control
```

Each returns a `GROUP` holding the children, so the result is immediately usable anywhere a `Control` is. `**props` sets ordinary properties on that group, so `row(..., name="strip", color="#264653")` works without a second statement.

`stack` is the overlay case: every child is sized to fill the group. That alone replaces the numpad's `key()` helper.

### Carrying the intent without touching the file

The group stores its layout on a private attribute, `control._layout`. Two existing mechanisms make this clean, and neither needs changing:

- `Control.__setattr__` routes underscore-prefixed names to `object.__setattr__` instead of into the property table, so `_layout` never becomes a `Property`.

- `codec` serializes only `properties`, `values`, `messages` and `children`, so an attribute outside those four cannot reach the file.

`deepcopy` in `Control.copy` carries it along, which is the behaviour we want. Reading it back needs `getattr(control, "_layout", None)`, because `Control.__getattr__` raises `AttributeError` for underscore names rather than returning `None`.

### The resolution pass

```python
def resolve(control: Control, frame=None) -> Control
```

Assigns `frame` to the control if given, then walks down: any control carrying a `_layout` computes frames for its direct children from its own frame and the recorded spec, and recurses. Controls without a `_layout` are leaves and are left alone.

`Document.resolve()` calls it against `root.frame`.

Semantics that need deciding and then documenting:

- **A parent overrides a child's explicit frame.** Simple and predictable. Manual placement is still available by not wrapping the control in a layout group, or by using `stack` with explicit frames.

- **`sizes` matches positional children**, as it does today. Omitted, every child gets an equal share.

- **`gap` is the space between slots; `pad` is the inset before the first and after the last.** Both accept an int, a `(horizontal, vertical)` pair, or a four-tuple.

- **Rounding invariant.** `_spans` currently guarantees that each slot ends exactly where the next begins, so rounding can never open a gap or an overlap and the last slot always reaches the end. Adding `gap` and `pad` must preserve this, and it should keep a test of its own.

### Reuse

`_ratios` and `_spans` in `layout.py` already do the arithmetic. The resolution pass should call them rather than growing a second implementation, which probably means promoting them to a shared internal module.

## Tier 3: idioms

Thin wrappers over the two tiers above, worth adding only once they are settled.

```python
def labelled(control: Control, text: str, *, size=48, inset=0.0) -> Control
def inset(control: Control, amount: float) -> Control
```

`labelled` is `stack` plus a non-interactive `LABEL`, which is the whole of the numpad's `key()`.

## Rejected alternatives

**A parallel lazy `Node` tree.** Pure, and testable without a `Document`, but it means two tree types, and the combinators would not apply to loaded layouts because `load()` yields `Control`s. Given that editing existing files is half the point of the library, that asymmetry is disqualifying.

**Storing the layout spec as real properties.** TouchOSC tolerates custom properties and `validate` leaves them alone, so this would work. It is rejected because it writes this library's private vocabulary into the user's file, which contradicts the round-tripping claim.

**Eager sizing with one tree.** Keeps `Control` as the only type, but still forces outside-in construction, which is what already exists. No real gain.

**Decorators.** The tosclib approach, already deliberately dropped.

## Open questions

- Does Tier 1 belong in `messages` rather than `ui`? It adds no vocabulary the format lacks, which is the argument for the core; consistency of the import path is the argument against.

- Should `connect` accept a destination *name* and resolve it during the same pass as layout? That would remove the build-order constraint entirely, at the cost of an error that surfaces late rather than at the call.

- Should `save` resolve automatically when anything in the tree carries a `_layout`? Convenient, but it makes writing a file mutate the tree.

- Does `validate` need a rule for a `_layout` that was never resolved, so a layout of zero-sized controls is caught before it is written?

- Should `Control.copy` accept layout overrides the way it accepts property overrides?

## Staging

1. Tier 1, message combinators, with `numpad.py` rewritten against them to measure the actual reduction rather than assume it.

2. Tier 2, behind `py2tosc.ui`, with the rounding invariant tested first.

3. Tier 3, only once the first two have been used for something real.

Step 1 is worth doing on its own merits and does not commit us to steps 2 or 3.
