# High-level helpers and combinators

**Status:** Tier 1 implemented in `py2tosc.ui`. Tiers 2 and 3 are still a design sketch, and the API is unstable below 1.0.

The problem statement below is kept in its original present tense and describes the state before Tier 1 landed; the sections after it record what was built and what the corpus forced to change along the way.

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

Tier 1 was the exception worth arguing about, since it only builds structures the format already defines and adds no vocabulary of its own, and could reasonably have lived in `messages`. It goes in `ui` anyway; see the resolved questions below.

## Tier 1: message combinators

Pure functions returning the existing dataclasses. No new concepts, no architecture change, and by the evidence above the largest reduction in caller code. This tier is worth doing whether or not the rest happens.

### A shared vocabulary for sources

Four constructors, used by both OSC arguments and local messages:

```python
def value(key: str = "x", *, conversion="FLOAT", scale=(0.0, 1.0)) -> Partial
def const(text: str, *, conversion="STRING") -> Partial
def prop(key: str, *, conversion="STRING") -> Partial
def index(*, conversion="INTEGER", scale=(1.0, 2.0)) -> Partial
```

`scale` unpacks into the `scale_min` and `scale_max` fields, which is the one place the current dataclasses read as two arguments for one idea.

`index` was not in the first draft, which had three constructors and no way to reach the fourth `PartialType`. It is worth having: `INDEX` accounts for 147 partials in the corpus, and its defaults are not guessable from the other three -- every one of them converts to `INTEGER` over a 1-2 range, not `STRING` over 0-1.

### Addresses

An address mini-syntax where braces mark a property lookup, mirroring f-strings:

```python
osc("/synth/{name}")
```

expands to two partials: `CONSTANT "/synth/"`, `PROPERTY "name"`. The guide's example becomes `osc("/{parent.name}/{name}")`.

**Adjacent constant text coalesces into one partial.** An earlier draft of this section split on every `/`, which would have produced four partials for the example above. The corpus says otherwise -- TouchOSC stores a constant run exactly as it was typed, and does not segment it:

```
1093x  CONSTANT "/"               PROPERTY "parent.name"  CONSTANT "/"  PROPERTY "name"
 180x  CONSTANT "/channel/track/" PROPERTY "parent.parent.name"  ...
  23x  CONSTANT "/action/str"
```

Coalescing is also the rule that makes `osc()` agree with the library's own default: `osc("/{name}")` reproduces `_default_path` partial for partial.

Two consequences to document at the API:

- **There is no canonical segmentation.** `CONSTANT "/"` + `CONSTANT "track/select"` and a single `CONSTANT "/track/select"` describe the same address, and both occur in real files. `osc()` is a constructor, not a normaliser: feeding a loaded message's address back through it will not reproduce the original partials byte for byte, and it should not claim to.

- **Braces need escaping.** `{{` and `}}` for a literal brace, as in f-strings. An unmatched brace is an error at the call rather than a silently malformed address.

`{#}` marks the control's index, since a path is where `INDEX` partials actually occur and `#` cannot be confused with a property key. That keeps the expansion total: every path shape in the corpus is reachable from the syntax.

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
def midi_cc(controller: int | Partial, *, channel=0, scale=(0, 127), source="x", **flags) -> MidiMessage
def midi_note(note: int | Partial, *, channel=0, scale=(0, 127), source="x", **flags) -> MidiMessage
```

These cover the two bindings that account for nearly all MIDI use. Anything else keeps constructing `MidiMessage` directly.

The sketch called the value key `var`, which collides with the trigger `var` every other combinator takes. It is `source` here, matching `connect`, so `on` and `var` mean the trigger and nothing else across the whole module. `**flags` is spelled out in the implementation rather than left as `**kwargs`, because `mypy --strict` cannot check what it cannot see.

What the three MIDI slots mean had to come from the corpus rather than from the field names. They supply the channel, the first data byte and the second, in that order; the channel slot stays scaled 0-15 whatever channel the message is on, because the channel itself lives in the command. A fixed first data byte is written twice, as `data1` and as an `INDEX` slot scaled `(n, n + 1)` -- attested at n=13 and n=29 -- which is the mechanism that lets a row of controls number itself from its position. `midi_cc(0)` therefore reproduces `MidiMessage()` exactly.

**Every byte takes the same partial vocabulary, not just a number.** The first version of these took `int` for the note and the channel, which covers the dominant shapes and locks out three more that the corpus contains:

```
24x  NOTE_ON       CONSTANT ""  0-15   PROPERTY "name"  VALUE "x" 0-127
24x  NOTE_ON       PROPERTY "tag"      PROPERTY "name"  VALUE "x" 0-127
10x  CONTROLCHANGE CONSTANT ""  0-15   INDEX ""   5-6   CONSTANT "" 0-127
```

The first is a keyboard whose buttons name their own notes rather than being numbered one at a time, which is the reason to want this at all. So `note`, `controller` and `channel` each accept a number or a partial: a number goes in the command and numbers the slot from itself, a partial leaves the command at zero and lets the slot decide.

Two consequences. `const` and `prop` grew a `scale`, since a MIDI slot takes its fixed byte from the range rather than from the key, and a vocabulary with a hole in exactly the place it is needed is not one. And range checking now applies only to the number form, because there is nothing to check on a partial.

`MidiValue` turns out to be a `Partial` minus the conversion -- a MIDI byte is a number whatever it was drawn from -- so one small adapter covers all three slots.

### Local wiring

```python
def connect(
    dst: Control | str,
    *,
    source: Partial | str = "x",   # bare str means value(str)
    to: Partial | str = "x",       # bare str means a VALUE target
    on: str = "ANY",
    var: str = "x",
) -> LocalMessage
```

Reusing `value`, `const` and `prop` for both ends means one vocabulary covers OSC arguments and local wiring. The numpad's four wiring sites become:

```python
connect(readout, source=prop("name"), to="text", on="RISE")
connect(readout, source=const("0"),   to=prop("sum"), on="RISE")
connect(readout, source=const(""),    to="text", on="FALL")
```

`dst` accepts a `Control` and reads its `id`, or a raw id string.

`to` decides `dst_type` as well as `dst_var`: a bare string or a `value()` partial targets a `VALUE`, a `prop()` partial targets a `PROPERTY`. That is what the corpus contains -- `dstType` holds `VALUE` (six occurrences) or `PROPERTY` (one), never anything else.

**The messages guide is wrong about this and must be fixed first.** `docs/guide/messages.md` teaches `dst_type="FLOAT"`, which is a `Conversion` value in a `PartialType` field; `tests/test_messages.py` copies the same mistake, harmlessly, since it only asserts tag ordering. Writing `connect()` against the guide as it stands would cement the error into the API. Nothing catches it today: `dst_type` is annotated as a bare `str`, and `validate` has no rule for it.

### Loaded messages are not what the dataclasses declare

The "one tree" constraint has a counterpart in the message layer that the rest of this document assumed away.

`codec._read_message` never coerces to enums, so a round-tripped `Partial.type` is a plain `str`, not a `PartialType`. Combinators must compare against string values, never enum identity, or they will behave differently on a built layout and a loaded one.

Read-side defaults also diverge from the dataclass defaults, so a loaded message can hold combinations no constructor would produce:

- `connections` reads as `""` when the element is missing, not `ALL_CONNECTIONS`.
- `MidiValue.scale_max` reads as `0`, against a dataclass default of `15`.
- `path` and `arguments` read as `[]` when absent, not the default partials.

Separately, `ALL_CONNECTIONS` and `ALL_GAMEPADS` live in `messages` but are in neither its `__all__` nor the package's, so any public signature defaulting to one of them needs the export added.

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

There is already a precedent for the whole pattern: `_has_includes` is set by `object.__setattr__` in `Control.__init__`, read by the codec with `getattr(control, "_has_includes", False)`, and written back by `codec._read_control`. `_layout` should follow it exactly.

One asymmetry to know about: `Control.__delattr__` has no underscore branch, so `del control._layout` routes into `delete()`, looks for a property named `_Layout`, misses, and raises. Clearing the attribute requires `object.__delattr__`.

### Naming

`ui.row(*children)` and `layout.row(parent)` have inverted semantics under one name: one consumes children, the other creates them. Calling the new layer additive is true but does not settle this.

Requiring `ui` to be imported as a module, the way `layout` already is, makes the two read as distinct at every call site (`ui.row` against `layout.row`) and is the cheapest resolution. It is also an independent argument for the module namespace, since `value`, `const`, `prop` and `osc` are too generic to sit in the flat package namespace -- `py2tosc.grid` against `layout.grid` already shows what that costs. The alternative, if the collision still reads badly in use, is distinct names such as `hbox` and `vbox`.

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

- **Rounding invariant.** `_spans` currently guarantees that each slot ends exactly where the next begins, so rounding can never open a gap or an overlap and the last slot always reaches the end. `gap` breaks that statement by construction, so it has to be restated rather than preserved: slot *i* ends exactly `gap` before slot *i+1* begins, the first slot begins at `pad`, and the last ends at `length - pad`. That needs a test of its own; `test_rounding_never_loses_or_gains_pixels` covers the existing wording and should stay as it is.

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

## Resolved questions

**Does Tier 1 belong in `messages` rather than `ui`?** In `ui`, imported as a module. The argument for `messages` was that Tier 1 adds no vocabulary the format lacks, which is true and not decisive. `value`, `const`, `prop`, `osc` and `connect` are too generic to go into a flat namespace that already has to explain `py2tosc.grid` against `layout.grid`, and keeping both tiers on one import path is worth more than the purity of the split.

**Should `connect` accept a destination name?** Not in Tier 1. It would make Tier 1 depend on a resolution pass that does not exist yet, and Tier 1 is meant to stand alone. Revisit with Tier 2, where a tree-walking pass already exists to hang it on.

**Should `save` resolve automatically?** No. Writing a file must not mutate the tree -- that is the round-tripping claim applied to the object model rather than the bytes. `Document.resolve()` stays explicit.

**Does `validate` need a rule for an unresolved `_layout`?** Yes, as a warning, shipped with Tier 2. `Control.frame` returns `Frame(0, 0, 0, 0)` for an unset frame rather than raising, so an unresolved layout otherwise fails silently and produces a file full of zero-sized controls.

**Should `Control.copy` accept layout overrides?** Defer. No demand until Tier 2 has been used for something.

## Staging

1. Tier 1, message combinators in `py2tosc.ui`, with `numpad.py` rewritten against them.

2. Tier 2, in the same module, with the restated rounding invariant tested first.

3. Tier 3, only once the first two have been used for something real.

Step 1 is worth doing on its own merits and does not commit us to steps 2 or 3.

### Proving the rewrite changes nothing

Rewriting `numpad.py` measures the reduction in caller code. It should also prove the combinators are pure sugar, which is a stronger claim and a cheaper test than it looks.

Freeze the current script's output, then require the rewritten script to produce a structurally identical document. Raw bytes will never match, because `Control.__init__` mints a `uuid4` per control and `LocalMessage.dst_id` carries one, so the comparison has to remap ids to their walk order first. Everything else -- properties, values, message fields, tree shape -- must match exactly.

Without it, an `osc()` or `connect()` that quietly emits different partials still passes: `tests/test_demos.py` checks control counts and the set of wired keys, not the contents of the messages.

**Result.** The rewrite produced an identical document, and took `numpad.py` from 173 lines to 141. All four wiring sites collapsed to one line each; `sends_name_to`, the helper that existed only to wrap the pattern, is now a single call and could be dropped entirely. The whole 32-line reduction came out of the four `LocalMessage` blocks, which is where the original reading of the demo said the cost was.

The check itself was run once rather than committed. Freezing the demo's output would pin a demo, which is meant to change; the equivalent protection lives in `tests/test_ui.py`, where each combinator is pinned against the dataclass it must produce -- `osc() == OscMessage()` and `midi_cc(0) == MidiMessage()` do most of that work on their own.
