"""Controls: the nodes a TouchOSC layout is built from."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from .defaults import default_values_for, defaults_for
from .enums import ControlType
from .messages import LocalMessage, Message, Value
from .properties import Color, Frame, Property, to_camel, to_color, to_frame

if TYPE_CHECKING:  # pragma: no cover
    from .validate import Issue

__all__ = [
    "Control",
    "box",
    "button",
    "encoder",
    "fader",
    "grid",
    "group",
    "label",
    "pager",
    "radar",
    "radial",
    "radio",
    "text",
    "xy",
]

_RESERVED = frozenset(
    {"control_type", "id", "properties", "values", "messages", "children"}
)


def _rewire(root: Control, remapped: dict[str, str]) -> None:
    """Point local messages at the copies rather than at the originals.

    A `LocalMessage` addresses its destination by node id, so reminting ids
    without this leaves a duplicated subtree driving the subtree it was copied
    from -- silently, since the id it holds still resolves.

    Only ids in `remapped` are rewritten. A destination outside the copied
    subtree is a deliberate reference to a control the copy does not own, and
    it survives unchanged.
    """
    for control in root.walk():
        for message in control.messages:
            if isinstance(message, LocalMessage) and message.dst_id in remapped:
                message.dst_id = remapped[message.dst_id]


class Control:
    """One `<node>`: a control, or a group of controls.

    Properties are reachable as attributes in `snake_case`, which is translated
    to the camelCase key the file uses:

    ```python
    fader.name = "cutoff"
    fader.frame = (0, 0, 50, 200)
    fader.corner_radius = 2.0    # writes the "cornerRadius" property
    ```

    Any key TouchOSC accepts works, including custom ones, and unknown keys
    raise `AttributeError` on read rather than returning `None`.

    Attributes:
        control_type: Which kind of control this is.
        id: The node's unique id, as a UUID string.
        properties: Every property, keyed by its camelCase file key.
        values: The control's live state entries.
        messages: The control's OSC, MIDI and local bindings.
        children: Nested controls. Only groups, grids and pagers use these.
    """

    # Declared for type checkers only. These are assigned through
    # object.__setattr__ in __init__, because __setattr__ routes everything
    # else to the property table.
    control_type: ControlType
    id: str
    properties: dict[str, Property]
    values: list[Value]
    messages: list[Message]
    children: list[Control]

    def __init__(
        self,
        control_type: ControlType | str,
        *,
        id: str | None = None,
        properties: dict[str, Any] | None = None,
        values: list[Value] | None = None,
        messages: list[Message] | None = None,
        children: list[Control] | None = None,
        **kwargs: Any,
    ):
        """
        Args:
            control_type: Which kind of control to create.
            id: A specific node id. Generated if omitted.
            properties: Properties to set, as `snake_case` or camelCase keys.
                Merged over the type's defaults.
            values: Replaces the type's default values entirely.
            messages: Bindings to attach.
            children: Nested controls.
            **kwargs: More properties, as keyword arguments. `fader(name="x")`
                and `fader(properties={"name": "x"})` are equivalent.
        """
        object.__setattr__(self, "control_type", ControlType(control_type))
        object.__setattr__(self, "id", id or str(uuid.uuid4()))
        object.__setattr__(self, "properties", {})
        object.__setattr__(self, "messages", list(messages or []))
        object.__setattr__(
            self, "children", list(children if children is not None else [])
        )
        object.__setattr__(self, "_has_includes", False)

        for key, value in defaults_for(self.control_type).items():
            self.set(key, value)
        for key, value in {**(properties or {}), **kwargs}.items():
            self.set(key, value)

        if values is not None:
            object.__setattr__(self, "values", list(values))
        else:
            object.__setattr__(
                self,
                "values",
                [
                    Value(key, default=default)
                    for key, default in default_values_for(self.control_type)
                ],
            )

    # -- properties ---------------------------------------------------------

    def set(self, key: str, value: Any, type: str | None = None) -> Control:
        """Set a property, creating it if it does not exist.

        Args:
            key: The property key, in `snake_case` or camelCase.
            value: The value to store.
            type: Force a property type instead of inferring one.

        Returns:
            This control, so calls can be chained.
        """
        prop = Property(key, value, type)
        self.properties[prop.key] = prop
        return self

    def get(self, key: str, default: Any = None) -> Any:
        """Read a property's value, or `default` if it is not set.

        Args:
            key: The property key, in `snake_case` or camelCase.
            default: What to return when the property is absent.

        Returns:
            The property's native Python value.
        """
        prop = self.properties.get(to_camel(key))
        return default if prop is None else prop.value

    def has(self, key: str) -> bool:
        """Whether a property is set.

        Args:
            key: The property key, in `snake_case` or camelCase.

        Returns:
            True if the property exists.
        """
        return to_camel(key) in self.properties

    def delete(self, key: str) -> bool:
        """Remove a property.

        Args:
            key: The property key, in `snake_case` or camelCase.

        Returns:
            True if a property was removed, False if there was none.
        """
        return self.properties.pop(to_camel(key), None) is not None

    def __getattr__(self, name: str) -> Any:
        # Guard the real attributes too: reaching __getattr__ for one of those
        # means it was never initialised, and looking it up again would recurse.
        if name.startswith("_") or name in _RESERVED:
            raise AttributeError(name)
        try:
            return self.properties[to_camel(name)].value
        except KeyError:
            raise AttributeError(
                f"{self.control_type} control has no property {name!r}"
            ) from None

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _RESERVED or name.startswith("_"):
            object.__setattr__(self, name, value)
        else:
            self.set(name, value)

    def __delattr__(self, name: str) -> None:
        if not self.delete(name):
            raise AttributeError(name)

    # -- typed accessors for the two composite properties -------------------

    # These are read accessors only. They need no setter: `__setattr__` routes
    # every assignment through `set`, which coerces via `to_frame`/`to_color`
    # for these two keys anyway, so a setter here would be unreachable.

    @property
    def frame(self) -> Frame:
        """The control's position and size, `(0, 0, 0, 0)` if unset.

        Assignable from any 4-item sequence.
        """
        prop = self.properties.get("frame")
        return Frame(0, 0, 0, 0) if prop is None else to_frame(prop.value)

    @property
    def color(self) -> Color:
        """The control's colour, opaque black if unset.

        Assignable from floats, 0-255 integers or a hex string.
        """
        prop = self.properties.get("color")
        return Color(0.0, 0.0, 0.0, 1.0) if prop is None else to_color(prop.value)

    # -- values -------------------------------------------------------------

    def value(self, key: str) -> Value | None:
        """Find one of the control's live-state entries.

        Args:
            key: `x`, `y`, `touch`, `text` or `page`.

        Returns:
            The matching value, or None.
        """
        return next((v for v in self.values if v.key == key), None)

    # -- children -----------------------------------------------------------

    def add(self, *controls: Control) -> Control:
        """Append one or more controls as children.

        Args:
            *controls: The controls to nest inside this one.

        Returns:
            This control, so calls can be chained.
        """
        self.children.extend(controls)
        return self

    def remove(self, control: Control) -> Control:
        """Detach a direct child.

        Args:
            control: The child to remove.

        Returns:
            This control, so calls can be chained.

        Raises:
            ValueError: If `control` is not a direct child.
        """
        self.children.remove(control)
        return self

    def copy(self, *, new_ids: bool = True, **overrides: Any) -> Control:
        """Duplicate this control and everything beneath it.

        Local messages are re-pointed at the copy: a binding whose destination
        lies inside the duplicated subtree follows the copy of that
        destination, so a wired module can be duplicated and keep working. A
        binding pointing outside the subtree is left alone, since that is a
        deliberate reference to a control the copy does not own.

        Args:
            new_ids: Give the copy and its descendants fresh ids. Leave this on
                unless you are deliberately writing a layout with duplicates --
                TouchOSC expects ids to be unique.
            **overrides: Properties to set on the copy.

        Returns:
            The new control, not attached to any parent.
        """
        clone = deepcopy(self)
        if new_ids:
            remapped = {}
            for control in clone.walk():
                remapped[control.id] = str(uuid.uuid4())
                object.__setattr__(control, "id", remapped[control.id])
            _rewire(clone, remapped)
        for key, value in overrides.items():
            clone.set(key, value)
        return clone

    def validate(self) -> list[Issue]:
        """Check this control and its subtree. See [`validate`][py2tosc.validate].

        Returns:
            Every finding, errors first. An empty list means nothing was found.
        """
        from .validate import validate as _validate

        return _validate(self)

    def walk(self) -> Iterator[Control]:
        """Iterate over this control and every control beneath it, depth first.

        Yields:
            Each control in the subtree, starting with this one.
        """
        yield self
        for child in self.children:
            yield from child.walk()

    def find(
        self, name: str | None = None, *, type: ControlType | str | None = None
    ) -> Control | None:
        """Find the first control beneath this one matching name and/or type.

        Args:
            name: The `name` property to match exactly.
            type: The control type to match.

        Returns:
            The first match in depth-first order, or None.
        """
        return next(iter(self.find_all(name, type=type)), None)

    def find_all(
        self, name: str | None = None, *, type: ControlType | str | None = None
    ) -> list[Control]:
        """Find every control beneath this one matching name and/or type.

        This control itself is never included. With no arguments, returns the
        whole subtree.

        Args:
            name: The `name` property to match exactly.
            type: The control type to match.

        Returns:
            All matches in depth-first order.
        """
        wanted = ControlType(type) if type is not None else None
        found = []
        for control in self.walk():
            if control is self:
                continue
            if name is not None and control.get("name") != name:
                continue
            if wanted is not None and control.control_type is not wanted:
                continue
            found.append(control)
        return found

    # -- dunders ------------------------------------------------------------

    def __iter__(self) -> Iterator[Control]:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __getitem__(self, index: int) -> Control:
        return self.children[index]

    def __repr__(self) -> str:
        name = self.get("name")
        label = f" {name!r}" if name else ""
        kids = f", {len(self.children)} children" if self.children else ""
        return f"<{self.control_type.value}{label}{kids}>"


def _factory(control_type: ControlType) -> Callable[..., Control]:
    def make(**kwargs: Any) -> Control:
        return Control(control_type, **kwargs)

    make.__name__ = control_type.value.lower()
    make.__qualname__ = make.__name__
    make.__doc__ = (
        f"Create a {control_type.value} control.\n\n"
        "Args:\n"
        "    **kwargs: Properties and constructor arguments, forwarded to\n"
        "        [`Control`][py2tosc.Control].\n\n"
        "Returns:\n"
        f"    A new {control_type.value} with its default properties applied.\n"
    )
    return make


box = _factory(ControlType.BOX)
button = _factory(ControlType.BUTTON)
label = _factory(ControlType.LABEL)
text = _factory(ControlType.TEXT)
fader = _factory(ControlType.FADER)
xy = _factory(ControlType.XY)
radial = _factory(ControlType.RADIAL)
encoder = _factory(ControlType.ENCODER)
radar = _factory(ControlType.RADAR)
radio = _factory(ControlType.RADIO)
group = _factory(ControlType.GROUP)
pager = _factory(ControlType.PAGER)
grid = _factory(ControlType.GRID)
