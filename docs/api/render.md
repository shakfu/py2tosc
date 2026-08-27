# Rendering

Drawing a layout as a picture, for looking at rather than for loading. Layout defects are visual and coordinates are not: a `sizes` that divides wrongly, a `gap` that eats a row and a `labelled` that mis-splits are otherwise assertable one frame at a time.

```python
doc = py2tosc.load("mixer.tosc")
Path("mixer.svg").write_text(py2tosc.to_svg(doc))
```

Nothing reads SVG back, which is why this is `render` rather than a `convert` target: `convert` means the same layout in another encoding and implies the reverse works.

**What it promises** is that a reader can see where every control is, how big it is and what kind it is -- not that it matches a screenshot. TouchOSC cannot be scripted, so there is no oracle for pixel fidelity. A Lua script can set any property at runtime, so what is drawn is the document rather than the running state.

Rules live in one `<style>` inside the SVG, so the file travels alone and draws through an `<img src>`. Classes are prefixed `p2t-` so an inline SVG cannot leak selectors into the page. Per-control values are emitted as custom properties rather than baked into coordinates: a fader's bar is driven by `--v`.

`to_svg(doc, clip=True)` cuts a control off at the edge of the one holding it, as TouchOSC does. Off by default: an overflowing control is a defect the picture is being drawn to find.

`to_html` wraps the same SVG in a page carrying the layout's name, its control count and whatever `validate` found. The output extension picks the wrapper.

```console
$ py2tosc render mixer.tosc -o mixer.html
```

Pages of a pager are laid out side by side in HTML as well, not behind tabs. `pagers.tosc` holds four pagers and `:target` matches one element per document, so independent tabs would need radio inputs positioned over the SVG at each pager's coordinates plus a second rendering mode where pages stack.

Provisional under the [stability policy](../stability.md), like `py2tosc.ui`.

::: py2tosc.to_svg

::: py2tosc.to_html

::: py2tosc.render.STYLESHEET
