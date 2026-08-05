# Custom properties

TouchOSC accepts properties it does not recognise, keeps them across a save, and exposes them to Lua. That makes them a usable place to store configuration or globals for a layout.

What it does *not* accept is new sub-elements. You can add `<property><key>Style</key>` under `<properties>`, but you cannot add a `<styles>` element under `<node>` -- the editor refuses the file. Values and the message categories are likewise fixed: bindings must be [one of the documented kinds](https://hexler.net/touchosc/manual/script-functions-global#message).

Scripts are similarly constrained to [the documented functions](https://hexler.net/touchosc/manual/script-objects-control#functions).

## Adding one

```python
import py2tosc

doc = py2tosc.load("layout.tosc")
doc.root.set("CustomProperty", "1007")
doc.save("out.tosc")
```

The type is inferred from the Python value, so a string is stored as `s` and a float as `f`. Force it if you need to:

```python
doc.root.set("CustomFlag", 1, type="b")
```

Custom keys are usually not `snake_case`, and that is fine -- a key with no underscore passes through untouched:

```python
doc.root.set("CustomProperty", "1007")
doc.root.get("CustomProperty")     #> '1007'
```

## Reading it back in Lua

Inside the TouchOSC editor, a custom property on a node is reachable as a field on that node:

```lua
function init()
    self.values.text = self.parent.CustomProperty
end

function onValueChanged(key, value)
    if key == "touch" and self.values.touch == true then
        print(self.parent.CustomProperty)
        self.parent.CustomProperty = self.parent.children.label2.values.text
    end
end
```

The value survives a save-and-reload, which is what makes this useful for configuration a layout needs to remember.

## Scripts

`script` is just a string property, so a Lua script can be attached from Python like any other:

```python
doc.find("readout").script = """
function init()
    self.values.text = self.parent.CustomProperty
end
"""
```

See the [copy scripts demo](../demos/copy-scripts.md) for pushing one script across many controls at once.
