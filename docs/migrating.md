# Coming from tosclib

py2tosc is a rewrite of [tosclib](https://github.com/AlbertoV5/tosclib). Scripts written against tosclib 0.3.x will not run against it, and there are no compatibility shims.

The short version of why: 0.3.x could not be installed cleanly, wrote invalid MIDI bindings, silently corrupted any control carrying two messages, and exposed a camelCase API over raw `ElementTree` objects.

## The shape of the change

`ElementTOSC` wrapped an `xml.etree` element and made you re-wrap every child by hand. `Control` *is* the model, and traversal returns controls.

=== "0.3.x"

    ```python
    import py2tosc as tosc

    root = tosc.load("layout.tosc")
    parent = tosc.ElementTOSC(root[0])
    fader = tosc.ElementTOSC(parent.findChildByName("fader1"))
    fader.setColor((1, 0, 0, 1))
    fader.setFrame((10, 20, 50, 200))
    tosc.write(root, "out.tosc")
    ```

=== "0.4"

    ```python
    import py2tosc

    doc = py2tosc.load("layout.tosc")
    fader = doc.find("fader1")
    fader.color = (1, 0, 0, 1)
    fader.frame = (10, 20, 50, 200)
    doc.save("out.tosc")
    ```

## Name by name

| tosclib 0.3.x | py2tosc |
|-------|-----|
| `tosc.load(path)` -> `ET.Element` | [`py2tosc.load(path)`][py2tosc.load] -> `Document` |
| `tosc.write(root, path)` | `doc.save(path)` |
| `tosc.createTemplate(frame)` | `py2tosc.Document.new(frame=...)` |
| `ElementTOSC(root[0])` | `doc.root` |
| `e.findChildByName(name)` | `doc.find(name)` |
| `e.createChild(ControlType.FADER)` | `parent.add(py2tosc.fader())` |
| `e.setName(v)` / `e.getName()` | `control.name = v` / `control.name` |
| `e.setColor(v)` / `e.getColor()` | `control.color = v` / `control.color` |
| `e.setFrame(v)` / `e.getFrame()` | `control.frame = v` / `control.frame` |
| `e.setScript(v)`, `setTag`, `setLocked`, ... | `control.script = v`, `control.tag`, `control.locked` |
| `e.createProperty(Property("i", "textSize", "14"))` | `control.text_size = 14` |
| `e.setProperty(key, value)` | `control.set(key, value)` |
| `e.getPropertyValue(key).text` | `control.get(key)` |
| `e.getPropertyParam("frame", "w").text` | `control.frame.w` |
| `e.hasProperty(key)` | `control.has(key)` |
| `e.createOSC(msg)` | `control.messages.append(OscMessage())` |
| `e.createMIDI(msg)` | `control.messages.append(MidiMessage())` |
| `e.createLOCAL(msg)` | `control.messages.append(LocalMessage())` |
| `e.removeOSC()` | `control.messages = [m for m in control.messages if ...]` |
| `tosc.copyProperties(a, b, *keys)` | `b.set(k, a.get(k))`, or `a.copy()` for the whole control |
| `tosc.copyChildren(a, b, *types)` | `b.add(*(c.copy() for c in a.find_all(type=t)))` |
| `tosc.pullValueFromKey(f, "name", n, k)` | `py2tosc.load(f).find(n).get(k)` |
| `tosc.parseProperties(node, *keys)` | `[{k: c.get(k) for k in keys} for c in doc.walk()]` |
| `@layout.row` decorator | [`layout.row(parent, ...)`][py2tosc.layout.row] function |
| `PropertyFactory.build(k, v)` | `Property(k, v)` |
| `tosc.Value("touch", "0", "0", "false", "0")` | `Value("touch", default=False)` |
| `tosc.OSC(...)` | `OscMessage(...)` |
| `tosc.MIDI(...)` | `MidiMessage(...)` |
| `tosc.LOCAL(...)` | `LocalMessage(...)` |
| `ControlElements.GAMEPAD` (unimplemented) | `GamepadMessage(...)` |
| `tosc.MidiMessage(...)` | `MidiCommand(...)` |

## Things that behave differently

**Property names are `snake_case`.** `cornerRadius` is `corner_radius`, `textSize` is `text_size`. The camelCase spelling still works if you pass it to `get` or `set`, and the file itself is unchanged.

**Values are native Python types, not strings.** `Value.locked` is a `bool`, not `"0"`. `Property("textSize", 14).value` is `14`, not `"14"`.

**Reading no longer mutates.** 0.3.x added empty `<messages>` and `<children>` elements to any control it wrapped. py2tosc leaves the tree alone.

**Missing properties raise.** `control.script` raises `AttributeError` if there is no script. Use `control.get("script")` when absence is expected.

**Layouts are functions.** The `@layout.row` / `@layout.column` / `@layout.grid` decorators are gone. The replacements are [`layout.row`][py2tosc.layout.row], [`layout.column`][py2tosc.layout.column] and [`layout.matrix`][py2tosc.layout.matrix] -- the last renamed so that `grid` names the `GRID` control and nothing else. They take the parent as an argument and return the controls they made, so nesting is ordinary function composition. See also [`py2tosc.ui`](api/ui.md), which describes a layout instead of applying one.

**numpy is not required.** It is not a dependency at all. py2tosc has none.

**New layouts are version 6.** 0.3.x always wrote `lexml version=3` and omitted the `<includes>` element TouchOSC 1.5 expects. py2tosc writes version 6 for new documents and preserves whatever version a loaded file declared, so editing an old layout does not silently change its format. Set `doc.version = "6"` to upgrade one deliberately.

**Gamepad bindings are supported.** 0.3.x had a `ControlElements.GAMEPAD` enum member with no implementation behind it, so a layout containing one could not be read. See [`GamepadMessage`][py2tosc.GamepadMessage].

**The public namespace is curated.** `import py2tosc` used to expose 75 names, including `zlib`, `re`, `uuid` and `ET`. It now exposes what `__all__` lists.
