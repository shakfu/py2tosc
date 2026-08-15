# The corpus conformance sweep

**Status:** run, and its one finding is in place. This is a maintenance trigger, not queued work, which is why it lives here rather than in `TODO.md`.

## What it is

A sweep over every layout in the corpus asking what the editor writes that the library does not, at two levels: per control type, and per role a control plays inside a container.

## What it found

The type-level half was already covered by `test_defaults_cover_every_property_the_editor_writes`. The role-level half, run across all 45 files, found exactly one rule: a `PAGER` page needs `tabLabel` and four tab colours. `ui.pager` applies it.

The geometric half was worth more than either. It found the tab bar orientation defect, and every pager page in the corpus is now reproduced exactly.

## Why it is not automated

A corpus-wide majority cannot tell a wrong default from a popular style. That is not a detail of how the sweep was written; it is the reason the method needs a human at the end.

The 0.3.2 defaults work is the case in point. Frequency counts across 5134 instances suggested four wrong defaults but could not settle them, because `outline`, `background` and `cornerRadius` disagree with the defaults just as loudly and are simply designers turning things off. What settled it was `controls.tosc`: one of every control type, made in the editor and left unstyled. One purpose-built file beat the whole corpus, because everything in it is something the control actually needs.

Building the sweep into the suite would encode the half that cannot conclude, and would report the same unresolvable disagreements on every run.

## When to run it again

When a container type is added. The role-level and geometric halves are the ones that pay, and both are about how a control behaves inside a parent that did not exist before.

Keep any minimal file drawn to settle a single question in `tests/data/`, so `tests/examples/` stays purely what TouchOSC ships. That has earned its keep twice: once for how a `GRID` tiles its cells, once for how a `PAGER` insets its pages.
