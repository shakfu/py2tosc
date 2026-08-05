# Image converter

Pixelate an image and draw it as BOX controls inside a named group. Mostly a demonstration that generating thousands of controls is practical.

Needs Pillow, which is not a py2tosc dependency.

```python
--8<-- "tests/demos/image_converter.py"
```

```console
$ pip install pillow
$ python tests/demos/image_converter.py tests/data/test.tosc out.tosc tests/data/logo.jpg canvas
```

At 64x64 with 4-point boxes this emits 4096 controls. Going much beyond that hurts both file size and the editor's performance, and the whole tree is held in memory rather than streamed.

![Example output](https://user-images.githubusercontent.com/58243333/168332352-cb848b15-13fc-4573-861d-27b47f6da2ee.jpg)
