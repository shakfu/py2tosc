# Controls and properties

Every node in a layout is a [`Control`][py2tosc.Control]: a control type, an id, a set of properties, its live values, its messages, and its children.

## Creating

There is a factory per control type, and each applies that type's defaults:

```python
import py2tosc

py2tosc.box()      py2tosc.button()    py2tosc.label()
py2tosc.text()     py2tosc.fader()     py2tosc.xy()
py2tosc.radial()   py2tosc.encoder()   py2tosc.radar()
py2tosc.radio()    py2tosc.group()     py2tosc.pager()
py2tosc.grid()
```

Properties can be passed straight in:

```python
fader = py2tosc.fader(
    name="cutoff",
    frame=(0, 0, 50, 200),
    color="#e76f51",
    grid_steps=13,
)
```

For a type chosen at runtime, construct a `Control` directly:

```python
control = py2tosc.Control("FADER", name="cutoff")
control = py2tosc.Control(py2tosc.ControlType.FADER, name="cutoff")
```

## Naming

TouchOSC property keys are camelCase, because that is what the file stores. Python names are `snake_case`. py2tosc translates between them, so you never write camelCase yourself:

| Python | Stored in the file |
|--------|--------------------|
| `corner_radius` | `cornerRadius` |
| `text_size` | `textSize` |
| `grid_steps_x` | `gridStepsX` |
| `outline_style` | `outlineStyle` |

Both spellings work everywhere, so pasting a key out of Hexler's documentation also works:

```python
fader.grid_steps = 13
fader.set("gridSteps", 13)     # identical
```

The raw dict is available when you need it, and is always keyed the way the file is:

```python
fader.properties["gridSteps"].type   #> <PropertyType.INTEGER: 'i'>
sorted(fader.properties)             # every key on this control
```

## Reading

Attribute access raises `AttributeError` for a property that is not set, rather than returning `None` and letting the mistake travel:

```python
fader.name              #> 'cutoff'
fader.script            #> AttributeError: FADER control has no property 'script'

fader.get("script")     #> None
fader.get("script", "") #> ''
fader.has("script")     #> False
```

## Types

Property types are inferred from the value, with known TouchOSC keys using their documented type. You rarely have to think about it:

```python
fader.visible = 1        # stored as type 'b', because visible is a boolean
fader.corner_radius = 1  # stored as type 'f', because cornerRadius is a float
fader.text_size = 14     # stored as type 'i'
```

Frames and colours are both four-item tuples, so those keys are resolved by name. Custom keys fall back to the Python type:

```python
group.set("myThreshold", 0.5)     # type 'f'
group.set("myLabel", "hello")     # type 's'
```

Force a type when you need to:

```python
group.set("myFlag", 1, type="b")
```

## Frames and colours

Both come back as named tuples that still compare and unpack as plain tuples:

```python
fader.frame          #> Frame(x=0, y=0, w=50, h=200)
fader.frame.w        #> 50
x, y, w, h = fader.frame
fader.frame == (0, 0, 50, 200)   #> True
```

Colours accept whichever notation is convenient:

```python
fader.color = (1.0, 0.0, 0.0, 1.0)   # normalised floats
fader.color = (255, 0, 0)            # 0-255, alpha defaults to opaque
fader.color = "#e76f51"              # hex, with or without the #
fader.color = "#e76f51ff"            # hex with alpha
```

## Named numbers

A dozen properties hold a number that stands for a name. `shape` 2 is a circle, `orientation` 1 faces east, `buttonType` 0 is momentary. The [enumerations](../api/enums.md) name them, and because they are `IntEnum` the two spellings are one value:

```python
button.shape = py2tosc.Shape.HEXAGON
button.shape = 6                        # identical, and still what the file stores

button.shape == py2tosc.Shape.HEXAGON   #> True
py2tosc.Shape(button.shape).name        #> 'HEXAGON'
```

Nothing requires you to use them. A layout written before they existed loads and compares against them unchanged, which is the point of their being integers underneath.

| Property | Enumeration |
|----------|-------------|
| `shape` | [`Shape`](../api/enums.md#py2tosc.Shape) |
| `text_align_h` | [`AlignH`](../api/enums.md#py2tosc.AlignH) |
| `text_align_v` | [`AlignV`](../api/enums.md#py2tosc.AlignV) |
| `orientation` | [`Orientation`](../api/enums.md#py2tosc.Orientation) |
| `button_type` | [`ButtonType`](../api/enums.md#py2tosc.ButtonType) |
| `outline_style` | [`OutlineStyle`](../api/enums.md#py2tosc.OutlineStyle) |
| `cursor_display`, `bar_display`, `lines_display` | [`CursorDisplay`](../api/enums.md#py2tosc.CursorDisplay) |
| `font` | [`Font`](../api/enums.md#py2tosc.Font) |
| `response` | [`Response`](../api/enums.md#py2tosc.Response) |
| `radio_type` | [`RadioType`](../api/enums.md#py2tosc.RadioType) |
| `pointer_priority` | [`PointerPriority`](../api/enums.md#py2tosc.PointerPriority) |

The reason to prefer the names is that the numbering is not uniform. `shape`, `text_align_h` and `text_align_v` count from 1; every other property here counts from 0. Hexler's manual lists the names in order without numbers, so reading it and counting from zero gets three of the twelve wrong -- `Shape.RECTANGLE` is 1, not 0.

`GamepadInput` names the twenty-one buttons and axes a gamepad binding can use, and is a string rather than a number:

```python
control.messages.append(py2tosc.GamepadMessage(type=py2tosc.GamepadInput.BUTTON_A))
```

## Values

A control's values are its live state. `default` is what it starts at.

```python
fader.values                       #> [Value(key='x', ...), Value(key='touch', ...)]
fader.value("x").default = 0.5
fader.value("x").locked = True
```

## Children

```python
panel = py2tosc.group(name="panel")
panel.add(py2tosc.fader(name="a"), py2tosc.fader(name="b"))

len(panel)              #> 2
panel[0]                #> <FADER 'a'>
list(panel)             # direct children
list(panel.walk())      # panel and everything beneath it
panel.remove(panel[0])
```

`find` and `find_all` search the whole subtree, never including the control they are called on:

```python
panel.find("a")
panel.find_all(type="FADER")
panel.find("a", type="FADER")
```

## Copying

`copy` duplicates a control and its subtree with fresh ids, which is what you want almost every time -- TouchOSC expects ids to be unique.

```python
strip = doc.find("channel1")

for channel in range(2, 9):
    doc.add(strip.copy(name=f"channel{channel}"))
```

Pass `new_ids=False` only if you are deliberately writing duplicates.
