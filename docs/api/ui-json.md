# Layout descriptions

Building a layout from JSON that describes it, rather than from JSON that holds it. The format is documented in [Describing a layout in JSON](../guide/ui-json.md), and unlike everything else here it is read only: a resolved layout cannot be turned back into the description that built it.

The dialect carries a schema number, and it is the producer that stamps it: this is the one format here written by something other than py2tosc, so whatever writes a description is the thing that has to say which schema it wrote. `SCHEMAS` and `supports` are how a generator asks what the installed release reads, before it writes a file that release cannot build.

`required_schema` answers the other half: the lowest schema that builds a given description, which is the number to stamp. Asking rather than remembering is what keeps the key honest, since nothing downstream audits it.

::: py2tosc.ui_json.required_schema

::: py2tosc.ui_json.supports

::: py2tosc.ui_json.build

::: py2tosc.ui_json.from_json
