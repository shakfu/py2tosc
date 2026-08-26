# Rendering a layout to SVG

Status: scope, nothing implemented. Written before the code so the decisions
are arguable here rather than discovered halfway through, which is the shape
minihost's `docs/dev/osc_and_touch.md` uses for the same reason.

Goal: turn a resolved `Document` into a picture, with the seam for driving it
from live values decided now and built later.


## 1. The case, narrowly

Not a replacement for `.tosc`. A `.tosc` opened in TouchOSC is a better
control surface than anything a renderer here produces, and the case for this
collapses the moment it is framed as competing with one.

What it competes with is *not being able to see a layout at all*:

- **Layout defects are visual and the suite cannot see them.** A `sizes` that
  divides wrongly, a `gap` that eats a row, a `labelled` that mis-splits its
  caption -- all of these are assertable today only as numbers, one frame at a
  time. `tests/test_ui_layout.py` is a list of coordinates nobody can picture.
- **The guide illustrates layouts with screenshots.** Updating one means
  opening the editor, which is why `docs/images/` lags the code.
- **Reviewing a generated description means reading JSON.** The whole argument
  for `ui_json` is that a description is reviewable; a reviewer who cannot see
  the result is reviewing arithmetic.
- **A generator's CI has no way to look at its output.** minihost's planned
  `touch` command will emit descriptions no human sees before a user does.

None of that needs TouchOSC, a browser API, a server, or a device. All of it
needs one pure function.


## 2. What a resolved document already gives

Established by reading, not assumed, because it decides how much work this is.

**Frames are relative to the parent.** In `simple_mk2.tosc` a FADER inside a
GROUP at `y=40` carries `y=95`, not `y=135`. So the control tree maps onto
nested `<g transform="translate(x,y)">` one node for one node, and the
renderer does no coordinate arithmetic at all. This is the single fact that
makes the job small: `ui.resolve` has already done the part that is hard.

**Colours are RGBA floats 0..1**, which is `rgb()` with an alpha away from
being a CSS colour.

**GRID and PAGER carry their children explicitly.** A 2x2 GRID holds four
controls; a PAGER holds one GROUP per page plus `tabbarSize` and `tabLabels`.
Nothing has to be synthesised or replicated -- the renderer walks what is
there.

**The corpus uses 69 distinct properties**, and none of them carries an image,
a texture or embedded binary data. Everything visible is a colour, a number,
an enumeration or a string.

**Text metrics are not our problem.** SVG `<text>` defers measurement to
whatever draws it, so no font engine is needed, which is the reason this is an
SVG target and not a raster one.

What is *not* free: 146 controls in `tests/examples/` carry Lua scripts, and a
script can change any property at runtime. A static render shows the document,
which is the state before anything runs. Section 6 makes that a stated limit
rather than a defect.


## 3. Decision: SVG is the primitive, HTML is a wrapper

Two functions, not two renderers:

```python
py2tosc.to_svg(doc)   -> str   # the picture
py2tosc.to_html(doc)  -> str   # a page with that picture in it
```

`to_html` embeds what `to_svg` produced. The interactive version later is
*the same SVG plus a script tag*, not a second code path -- which is the whole
reason to nest them this way rather than write an HTML renderer beside an SVG
one.

Why SVG carries the geometry:

| | SVG | HTML/CSS |
|---|---|---|
| Relative frames | `<g transform>` nests exactly as the tree does | `position:absolute` inside `position:relative`, same thing, more markup |
| The six `Shape` values | `<polygon>`, `<circle>` -- what the format is drawn in | `clip-path`, fussy and harder to read in a diff |
| Scaling | one `viewBox`, free at any size | media queries or a transform |
| Golden files | text, and a diff shows what moved | text, but attribute-order churn is worse |
| Embedding in docs | `![](layout.svg)` in Markdown | an `<iframe>` or a screenshot |
| Text wrapping | none; see below | native |

### Classes and an embedded stylesheet, not presentation attributes

`to_svg` emits `class="p2t-fader-bar"` and one `<style>` block, rather than
`fill=` and `stroke-width=` on every element.

Embedded rather than linked, so the file still travels alone and still draws
through an `<img src>`. Every class prefixed `p2t-`, because an SVG used
inline in a page shares that page's cascade and a bare `.bar` would reach into
someone else's markup.

Three things pay for it, and the first is the one that matters:

- **It is where the value channel lives.** Section 4 requires that a control's
  value not be resolved away into coordinates, and a custom property read by a
  rule is what makes that a channel rather than a convention.
- **Tabs stop needing script.** A pager is a radio input per page and a
  `:checked ~` rule, which is only expressible if there are rules.
- **Goldens shrink and stay readable.** A diff over presentation attributes is
  mostly colour repetition; a diff over classes shows what actually moved.

The cost is that a consumer stripping the `<style>` gets an unstyled picture.
Nothing in the pipeline does that, and the alternative -- repeating every
colour on every element -- makes theming impossible rather than merely
inconvenient.

The one place SVG loses is the one place it loses badly: it has no automatic
line wrapping, and TEXT is a multi-line control with `textWrap`. Two ways out,
and this is worth deciding before the first line rather than after:
`<foreignObject>` with an HTML block inside, which wraps properly and is
widely supported but does not render in some SVG consumers; or single-line
with `textClip` honoured, which always draws and is sometimes wrong. Start
with the second and treat the first as an upgrade, since a TEXT control that
is a box with the first line in it still shows a reviewer where it is and how
big it is, which is what section 1 asked for.


## 4. The constraint to adopt now, because it is free now

**A control's value must not be baked into the coordinates the renderer
emits.**

This is the whole of "usable interactively later", and it costs nothing today.
A fader's fill is a function of its `x` value. Emitting

```xml
<rect x="0" y="120" width="50" height="80"/>
```

computes that function once, at render time, in Python -- and an interactive
version then has to compute the same function again in JavaScript, which means
the geometry rules exist twice and drift. Emitting the fill so that the value
enters through one named channel per control instead

```xml
<g class="p2t-fader" data-key="x" style="--v: 0.4"> ... </g>
```

makes the later runtime a script that sets `--v` and nothing else. Same
picture, same file size, one decision.

Which mechanism actually carries the value is the part to validate in a
browser before committing: SVG 2 makes `x`, `y`, `width` and `height`
presentation attributes on `<rect>`, so `height: calc(var(--v) * 80px)` may
work directly, but `transform: scaleY(var(--v))` with an explicit
`transform-origin` is the conservative spelling and is universally supported.
This scope does not choose between them; it insists only that the value is
addressable rather than resolved away.

Two smaller consequences of the same rule, also free:

- **Every control gets one stable addressable node**, carrying its `id` and
  its type. A runtime, a test and a person hunting a control in a diff all
  want the same thing.
- **The bindings are emitted as data rather than dropped.** A control's
  messages are the description of what it sends; a static render has no use
  for them, and an interactive one has nothing without them. Writing them into
  a single embedded JSON block keeps the renderer static and makes the runtime
  additive.

This mirrors the constraint minihost's plan adopted for the same reason at
`osc_and_touch.md` section 7 -- key on a normalized float and an identity
rather than on the wire format -- and for the same payoff: a later back end is
an adapter rather than a refactor.


## 5. Scope of the first version

In:

- All 13 control types, drawn as their frame, `shape`, `color`, `background`,
  `outline`/`outlineStyle` and `cornerRadius` say.
- The type-specific marks that make a control recognisable rather than a
  rectangle: a FADER's bar and cursor with `orientation` honoured, a BUTTON's
  fill, a RADIO's `steps` divisions, an XY's crosshair, a LABEL's and TEXT's
  string with `textSize`, `textColor` and `textAlignH`/`textAlignV`.
- GROUP, GRID and PAGER as nesting containers, with a PAGER drawing its tab
  bar at `tabbarSize` -- but showing a different thing in each wrapper, which
  is a decision rather than an inconsistency. `to_svg` lays every page out
  side by side, captioned, because a page a reviewer cannot see is a page
  nobody reviews and that is what section 1 asked for. `to_html` shows one at
  a time behind working tabs, because the CSS-only spelling in section 7 makes
  that free there and a page with tabs is what anyone opening an HTML file
  expects. Neither needs an option; the two wrappers want different answers
  and each gets the one it wants.
- `visible: false` drawn, but marked -- an invisible control is exactly the
  kind of thing someone renders a layout to find.
- Values from the document, so a fader with a default of 0.7 is drawn at 0.7
  through the channel section 4 requires.

Out, and each for a reason rather than for time:

- **Lua.** 146 corpus controls carry a script and a script can set any
  property. Rendering the document is rendering the state before anything ran,
  and the page should say so where a script exists rather than pretend.
- **Pixel fidelity to TouchOSC.** See section 6.
- **Interactivity.** Section 7.
- **Editing, or reading SVG back.** One way, always. Which is also why this is
  not a `convert` target: `py2tosc convert x.tosc -o x.json` implies the
  reverse works, and `convert x.svg -o x.tosc` never will. It gets its own
  verb.

```console
$ py2tosc render mixer.tosc -o mixer.svg
$ py2tosc render synth.ui.json -o synth.html
```

Extension picks the wrapper, as `convert` already does for encodings. Input is
whatever `load` accepts, so a description renders without being compiled first
-- which is the case section 1 cares most about.


## 6. The fidelity bar, and the oracle problem

TouchOSC is the only thing that knows what a layout looks like, and it cannot
be scripted. So a test cannot assert the render is *right*, only that it is
consistent -- the same position `tests/test_validate.py` reached on Lua
behaviour, and worth taking the same way rather than pretending otherwise.

The bar is therefore stated rather than measured: **a reader can see where
every control is, how big it is, and what kind it is.** Not: it looks like a
screenshot. Anyone who later wants the second thing is starting a different
project, and saying so now is what stops this one from becoming it.

What the suite can hold:

- Every layout in the corpus renders without raising, and every control type
  appears across it -- the sweep `tests/test_corpus.py` already establishes.
- Every control in the document produces exactly one addressable node in the
  output, with the id the document gave it. This is the property the later
  runtime depends on, so it is worth pinning before there is a runtime.
- Frames in the output match the frames in the document, read back out of the
  SVG. That is the one thing that *is* checkable against a real oracle, since
  `ui.resolve` computed them.
- A handful of goldens, reviewed by eye once and then frozen, so a change that
  moves something says which file and where.


## 7. What interactive adds later, and where it attaches

Recorded so the seam is deliberate, not so it gets built.

A live page needs three things this does not have: pointer handling that turns
a drag into a value, a transport carrying that value somewhere, and feedback
coming back. The first is a modest amount of JavaScript against the nodes
section 4 already guarantees. The second and third are not py2tosc's --
they are minihost's, and `osc_and_touch.md` section 7 has already worked out
that a browser cannot send UDP, that Web MIDI is absent from iPadOS, and that
a WebSocket server is the only float-resolution path and a real dependency.

Which is the useful boundary: **py2tosc renders and knows nothing about
transports.** Everything about what is on the other end stays outside. If that
line holds, the static renderer is finished work rather than a half-built
product waiting on a decision in another repository.

### Whether py2tosc ever ships JavaScript

Decided as far as it needs to be, which is less far than it first looked. Not
shipping a runtime forecloses nothing: what keeps the option open is the
contract in section 4 -- one addressable node per control, the value through a
named channel, the bindings emitted as data -- and that contract is in v1
whatever happens next. The irreversibility is all on the other side. A shipped
runtime is a thing that has to keep working.

The distinction that matters is not script or no script, it is *where the
script lives*:

- **Inline, written by the emitter.** A string in the Python source. No new
  file type in the wheel, no build configuration, no separate tooling; it is
  reviewed and versioned exactly as the SVG it sits next to is.
- **A shipped `runtime.js` asset.** A new kind of thing in a package that is
  currently Python source and a `py.typed` marker, carrying its own linting,
  its own browser tests and its own compatibility surface.

Only the second changes what the package is. So: **v1 emits no script,
prefers CSS wherever CSS can do the job, and may emit inline script where a
case beats the CSS-only version.** A shipped asset is a separate decision, and
the honest trigger for taking it is the point where the script needs browser
tests of its own -- because that is when "a string the emitter writes" stops
being a fair description.

Tabs are the case that would otherwise force this early, and they do not.
A pager in `to_html` can be one radio input per page plus
`:checked ~ .p2t-page { display: block }`, which is ordinary CSS with no
script at all; it needs the SVG inline rather than in an `<img>` and the pages
as siblings, both of which the renderer decides. Standalone SVG has the same
shape through `<a href="#page2">` and `#page2:target`, though that one is a
claim to check in a browser rather than one to design around yet.


## 8. Stability

Provisional, under the same carve-out `ui` and `ui_json` have. It is a new
emitter with no corpus behind it and an appearance that will want changing
once anyone looks at real output, and pinning it in a minor release would be
promising something nobody has seen yet.

The documents it renders are unaffected, exactly as with `ui`: nothing here
reads or writes a layout, so a change to how something is drawn cannot reach a
file.


## 9. Open questions

Three, and none of them blocks starting.

- **Whether `:target` drives a pager in standalone SVG.** The radio-input
  spelling in `to_html` is not in doubt; this one decides whether a bare
  `.svg` gets working tabs as well as the side-by-side view, or only the
  second. One browser check answers it, and the answer changes nothing else.

- **Which mechanism carries `--v`**, per section 4. SVG 2 makes `x`, `y`,
  `width` and `height` presentation attributes on `<rect>`, so
  `height: calc(var(--v) * 80px)` may work directly; `transform:
  scaleY(var(--v))` with an explicit `transform-origin` is the conservative
  spelling. Also one browser check. The claim that the constraint is free
  rests on this, so it is the first thing to try.

- **Whether the clipped single line for TEXT is good enough** once there is
  real output to look at, or whether `foreignObject` earns its incompatibility.
  Section 3 starts with the first and treats the second as an upgrade, so this
  is a question to reopen with pictures rather than one to answer now.

Settled while scoping, recorded so they are not re-litigated: classes and an
embedded stylesheet over presentation attributes (section 3); a PAGER laid out
side by side in SVG and tabbed in HTML (section 5); no shipped JavaScript, CSS
preferred, inline script only where it beats CSS (section 7); a `p2t-scripted`
class for the 146 corpus controls carrying Lua, so the stylesheet decides
whether a mark appears at all rather than the emitter deciding for everyone.
