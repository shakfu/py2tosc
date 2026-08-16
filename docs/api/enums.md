# Enumerations

These mirror TouchOSC's own vocabulary and are written verbatim into the file. Anywhere one is accepted, the equivalent plain string works too.

## Structure

::: py2tosc.ControlType

::: py2tosc.PropertyType

## Messages

::: py2tosc.PartialType

::: py2tosc.Conversion

::: py2tosc.TriggerCondition

::: py2tosc.MidiType

::: py2tosc.GamepadInput

## Property values

The properties below hold a number, and these name the numbers. They are `IntEnum`, so they are interchangeable with the bare integers in both directions -- `control.shape = 2` and `control.shape = Shape.CIRCLE` produce the same file, and a layout written before these existed compares equal to them on load.

Worth knowing that TouchOSC does not number them consistently. `shape`, `textAlignH` and `textAlignV` count from 1; every other property here counts from 0. The manual lists the names in order without numbers, so reading it alone and counting from zero gets those three wrong. The values here come from the 45 layouts in the corpus, and `tests/test_enums.py` checks that no file holds a number these cannot name.

::: py2tosc.Shape

::: py2tosc.AlignH

::: py2tosc.AlignV

::: py2tosc.Orientation

::: py2tosc.ButtonType

::: py2tosc.OutlineStyle

::: py2tosc.CursorDisplay

::: py2tosc.Font

::: py2tosc.Response

::: py2tosc.RadioType

::: py2tosc.PointerPriority
