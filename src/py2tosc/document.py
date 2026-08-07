"""The `.tosc` file itself: loading, saving and creating layouts."""

from __future__ import annotations

import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from os import PathLike
from typing import TYPE_CHECKING, Any

from ._geometry import resolve, resolve_pending
from .codec import from_xml, to_xml
from .control import Control, group
from .enums import ControlType

if TYPE_CHECKING:  # pragma: no cover
    from .validate import Issue

__all__ = ["Document", "dumps", "load", "loads", "save"]

_PathLike = str | PathLike[str]

#: A `.tosc` file is a zlib stream; the header's first byte is always 0x78.
_ZLIB_MAGIC = 0x78


@dataclass
class Document:
    """A TouchOSC layout: one root control plus the format version.

    Attributes:
        root: The group every other control lives inside.
        version: The `lexml` version written to the file. TouchOSC 1.5 uses 6.
    """

    root: Control
    version: str = "6"

    @classmethod
    def new(
        cls, frame: tuple[int, int, int, int] = (0, 0, 1024, 768), **kwargs: Any
    ) -> Document:
        """Create an empty layout.

        Args:
            frame: The canvas position and size.
            **kwargs: Further properties for the root group.

        Returns:
            A document holding an empty root group.
        """
        return cls(root=group(frame=frame, **kwargs))

    # -- traversal, delegated to the root -----------------------------------

    def find(
        self, name: str | None = None, *, type: ControlType | str | None = None
    ) -> Control | None:
        """Find the first control in the layout matching name and/or type.

        Args:
            name: The `name` property to match exactly.
            type: The control type to match.

        Returns:
            The first match in depth-first order, or None.
        """
        return self.root.find(name, type=type)

    def find_all(
        self, name: str | None = None, *, type: ControlType | str | None = None
    ) -> list[Control]:
        """Find every control in the layout matching name and/or type.

        Args:
            name: The `name` property to match exactly.
            type: The control type to match.

        Returns:
            All matches in depth-first order.
        """
        return self.root.find_all(name, type=type)

    def walk(self) -> Iterator[Control]:
        """Iterate over every control in the layout, depth first.

        Yields:
            The root, then each control beneath it.
        """
        return self.root.walk()

    def add(self, *controls: Control) -> Document:
        """Append controls to the root group.

        Args:
            *controls: The controls to add.

        Returns:
            This document, so calls can be chained.
        """
        self.root.add(*controls)
        return self

    def resolve(self) -> Document:
        """Assign frames to everything the layout combinators described.

        The combinators in `py2tosc.ui` record an arrangement without sizing
        anything, since a layout can only divide a frame it knows. This is the
        pass that hands the root's frame down the tree.

        Call it when you want the frames before writing anything -- to read
        them, or to check them. Saving places whatever is still unplaced, so a
        layout is never written out unsized, but it will not re-run a layout
        that was already resolved. This will, which is how a tree is re-laid
        out after its root frame changes.

        Returns:
            This document, so calls can be chained.

        Raises:
            ValueError: If a layout cannot fit its children into its space.
        """
        resolve(self.root)
        return self

    def validate(self) -> list[Issue]:
        """Check the layout. See [`validate`][py2tosc.validate].

        Returns:
            Every finding, errors first. An empty list means nothing was found.
        """
        from .validate import validate as _validate

        return _validate(self)

    def __iter__(self) -> Iterator[Control]:
        return iter(self.root)

    # -- output --------------------------------------------------------------

    def dumps(self, pretty: bool = False, *, validate: bool = False) -> str:
        """Serialize the layout to XML text.

        Args:
            pretty: Emit one element per line, matching the editor's XML export.
            validate: Check the layout first and refuse to serialize if it has
                errors. Off by default, because a rule in the checker being
                wrong should not stop you writing a file.

        Unlike `save`, this does not place an unresolved layout, and the
        difference is deliberate rather than an oversight. `save` writes a file
        for TouchOSC to open, where an unplaced layout is never what anyone
        wanted; `dumps` is for looking at the tree, and while debugging a
        layout the unplaced state is exactly what you need to see.

        Returns:
            The complete XML document.

        Raises:
            ValidationError: If `validate` is set and the layout has errors.
        """
        if validate:
            self._raise_on_errors()
        return to_xml(self.root, version=self.version, pretty=pretty)

    def _raise_on_errors(self) -> None:
        from .validate import ERROR, ValidationError

        issues = self.validate()
        if any(issue.level == ERROR for issue in issues):
            raise ValidationError(issues)

    def save(
        self, path: _PathLike, *, pretty: bool | None = None, validate: bool = False
    ) -> None:
        """Write the layout to disk.

        The format follows the file extension: `.xml` writes readable XML, and
        anything else writes a zlib-compressed `.tosc` that TouchOSC can open.

        Args:
            path: Where to write. A `.xml` suffix selects the XML export.
            pretty: Override the line-per-element formatting that the extension
                would otherwise choose.
            validate: Check the layout first and write nothing if it has errors.
                This is the checkpoint worth using it at: the mistake is caught
                before the file exists, rather than when TouchOSC refuses it.

        Any layout the combinators described but nobody resolved is placed
        first, since the alternative is writing a file whose every control sits
        at the origin -- structurally valid, byte-exact on a round trip, and
        visibly wrong in TouchOSC. A layout that was already resolved is left
        as it is, so a frame placed by hand inside one survives. Loading a file
        and saving it again is unaffected: a loaded control carries no layout.

        Raises:
            ValidationError: If `validate` is set and the layout has errors.
                Nothing is written.
            ValueError: If a layout cannot fit its children into its space.
        """
        resolve_pending(self.root)
        if validate:
            self._raise_on_errors()
        as_xml = str(path).lower().endswith(".xml")
        if pretty is None:
            pretty = as_xml
        text = self.dumps(pretty=pretty).encode("utf-8")
        with open(path, "wb") as file:
            file.write(text if as_xml else zlib.compress(text))

    def __repr__(self) -> str:
        count = sum(1 for _ in self.walk()) - 1
        return (
            f"<Document version={self.version} root={self.root!r} ({count} controls)>"
        )


def loads(source: str | bytes) -> Document:
    """Parse a layout from XML text or from raw `.tosc` bytes.

    Compressed input is detected and decompressed automatically, so this accepts
    either form without being told which it was given.

    Args:
        source: XML text, XML bytes, or the contents of a `.tosc` file.

    Returns:
        The parsed document.

    Raises:
        ValueError: If the input is neither valid XML nor a valid `.tosc`.
    """
    if isinstance(source, bytes) and source[:1] and source[0] == _ZLIB_MAGIC:
        source = zlib.decompress(source)
    root, version = from_xml(source)
    return Document(root=root, version=version)


def load(path: _PathLike) -> Document:
    """Read a layout from a `.tosc` or `.xml` file.

    Args:
        path: The file to read. Either format is accepted.

    Returns:
        The parsed document.

    Raises:
        ValueError: If the file is neither valid XML nor a valid `.tosc`.
    """
    with open(path, "rb") as file:
        return loads(file.read())


def dumps(document: Document, pretty: bool = False) -> str:
    """Serialize a document to XML text.

    Args:
        document: The layout to serialize.
        pretty: Emit one element per line, matching the editor's XML export.

    Returns:
        The complete XML document.
    """
    return document.dumps(pretty=pretty)


def save(document: Document, path: _PathLike, *, pretty: bool | None = None) -> None:
    """Write a document to disk.

    Args:
        document: The layout to write.
        path: Where to write. A `.xml` suffix selects the XML export.
        pretty: Override the formatting the extension would choose.
    """
    document.save(path, pretty=pretty)
