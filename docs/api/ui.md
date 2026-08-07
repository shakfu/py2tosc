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

These describe an arrangement instead of applying one. Each returns a `GROUP` holding its children, so the result goes wherever a control goes and layouts nest by ordinary composition. Frames are assigned later, by `resolve`.

::: py2tosc.ui.row

::: py2tosc.ui.column

::: py2tosc.ui.grid

::: py2tosc.ui.stack

::: py2tosc.ui.pager

::: py2tosc.ui.resolve

## Idioms

Thin wrappers over the two layers above.

::: py2tosc.ui.labelled

::: py2tosc.ui.inset
