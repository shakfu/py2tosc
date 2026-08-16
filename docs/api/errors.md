# Errors

Everything py2tosc raises on its own behalf inherits from `Py2ToscError`, so a
caller that wants to treat any library failure alike can write one `except`.

Errors caused by passing a bad argument are deliberately left on the builtins.
A `ValueError` for an unparseable colour or a `TypeError` for the wrong kind of
message says exactly what it means already, and wrapping those would make
ordinary Python harder to read without telling the caller anything new.

```python
try:
    doc = py2tosc.load(path)
except py2tosc.FormatError as exc:
    print(f"{path}: not a layout ({exc})")
```

::: py2tosc.Py2ToscError

::: py2tosc.FormatError

::: py2tosc.ValidationError
