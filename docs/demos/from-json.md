# Faders from JSON

Build a layout from external data: one fader per plugin parameter, each named after its parameter and sending to `/<group name>/<fader name>`.

```python
--8<-- "tests/demos/from_json.py"
```

```console
$ python tests/demos/from_json.py "tests/data/Pro-C 2 (FabFilter).json" out.tosc
```

The OSC address is assembled from [`Partial`][py2tosc.Partial] segments, so it follows the controls if they are renamed later. See [Messages](../guide/messages.md).
