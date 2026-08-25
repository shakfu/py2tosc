# Message combinators

Shorter ways to build the message dataclasses. See [Messages](../guide/messages.md) in the guide for the objects these return.

!!! warning "Unstable"

    `py2tosc.ui` encodes opinions about how bindings are best described, rather than binding to the file format. It is kept out of the core namespace so those opinions can change without dragging the rest of the library's version with them, and it may change shape before 1.0.

## Sources

The same four constructors describe an OSC argument, a MIDI slot and either end of a local binding.

::: py2tosc.ui.value

::: py2tosc.ui.const

::: py2tosc.ui.prop

::: py2tosc.ui.index

## Addresses

::: py2tosc.ui.path

## Bindings

::: py2tosc.ui.osc

::: py2tosc.ui.midi_cc

::: py2tosc.ui.midi_note

::: py2tosc.ui.connect

## Layout

These describe an arrangement instead of applying one. Each returns the container it built, so the result goes wherever a control goes and layouts nest by ordinary composition. Frames are assigned later, by `resolve`.

Children are controls, or any nesting of lists and generators of them -- the `Children` alias in the signatures below. A group is a child rather than the controls inside it, and anything that is neither a control nor a sequence of them is a `TypeError` at the call.

The first four build a `GROUP`, arranging controls you already have.

::: py2tosc.ui.row

::: py2tosc.ui.column

::: py2tosc.ui.tiles

::: py2tosc.ui.stack

The last two build the control the format names, which cannot be a plain group: a `PAGER` pages between its children, and a `GRID` holds copies of one control type.

::: py2tosc.ui.pager

::: py2tosc.ui.grid

## Resolving

::: py2tosc.ui.resolve

## Idioms

Thin wrappers over the two layers above.

::: py2tosc.ui.labelled

::: py2tosc.ui.inset
