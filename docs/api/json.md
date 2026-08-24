# The JSON encoding

The same layout tree the `.tosc` holds, written as JSON. Reading and writing it is a `load` and a `save` away -- the extension chooses on the way out and the content decides on the way in -- and these are the functions underneath that, for when the text rather than the file is what you have.

The format itself is described in [The .json format](../guide/json.md).

::: py2tosc.to_json

::: py2tosc.from_json

::: py2tosc.json_codec.encode

::: py2tosc.json_codec.decode
