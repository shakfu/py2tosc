# Faders from JSON

Build a layout from external data: one fader per plugin parameter, each named after its parameter and sending to `/<group name>/<fader name>`.

```python
--8<-- "tests/demos/from_json.py"
```

```console
$ python tests/demos/from_json.py tests/data/pro_c_2_fabfilter.json
```

The OSC address is assembled from [`Partial`][py2tosc.Partial] segments, so it follows the controls if they are renamed later. See [Messages](../guide/messages.md).

For the same idea at full size -- pages, captions and MIDI bindings, laid out with the combinators in [`py2tosc.ui`](../api/ui.md) -- see [Control surface](control-surface.md).
