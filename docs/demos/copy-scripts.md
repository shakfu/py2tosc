# Copy scripts

Copy one control's Lua script onto every child of another group. Useful when a layout has dozens of controls that should all behave the same way.

```python
--8<-- "tests/demos/copy_scripts.py"
```

```console
$ python tests/demos/copy_scripts.py tests/data/test.tosc source target
```

`script` is an ordinary string property, so this is just a read and a write -- see [Controls and properties](../guide/controls.md).
