from threading import Lock
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypeVar,
    Union,
    TYPE_CHECKING,
    cast,
)

from .input import Buttons, Keys, MouseInputEvent, KeyboardInputEvent, DefocusInputEvent
from .context import Color, RenderContext, BoundingRectangle
from .settings import Settings

if TYPE_CHECKING:
    from .scene import Scene
    from .input import InputEvent


class ComponentException(Exception):
    pass


DeferredInput = Callable[[], bool]
SettingT = TypeVar("SettingT")


class Component:
    def __init__(self) -> None:
        self.lock = Lock()

    def _attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.settings = settings
        self.scene = scene
        self.location: Optional[BoundingRectangle] = None
        self.__children: List["Component"] = []
        self.attach(scene, settings)

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        """
        Override this in your subclass to do any attach-related handling.
        """
        pass

    def _detach(self) -> None:
        for child in self.__children:
            child._detach()
        self.detach()

    def detach(self) -> None:
        """
        Override this in your subclass to do any detach-related handling.
        """
        pass

    def register(self, component: "Component", location: BoundingRectangle) -> None:
        self.scene.register_component(component, location, parent=self)
        self.__children.append(component)

    def unregister(self, component: "Component") -> None:
        self.scene.unregister_component(component)
        self.__children = [c for c in self.__children if id(c) != id(component)]

    @property
    def dirty(self) -> bool:
        """
        Override this in your subclass to declare that you're dirty and
        need to be redrawn.
        """
        return False

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        """
        Override this in your subclass to determine the exact size of
        your component, if it can be calculated by its properties. If
        it cannot be, return None.
        """
        return None

    def tick(self) -> None:
        """
        Override this in your subclass to tick forward animations.
        """
        pass

    def _render(self, context: RenderContext, bounds: BoundingRectangle) -> None:
        with context.clip(bounds) as subcontext:
            self.location = subcontext.location
            with self.lock:
                self.render(subcontext)

    def render(self, context: RenderContext) -> None:
        """
        Override this in your subclass to render to a context.
        """
        pass

    def _handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        if isinstance(event, MouseInputEvent):
            if self.location is not None:
                if self.location.contains(event.y, event.x):
                    # Send a mouse event
                    return self.handle_input(event)
                else:
                    # Send that a mouse event happened elsewhere
                    return self.handle_input(DefocusInputEvent(event.button))
            # Should never happen, but if location isn't set we don't handle mouse
            return False
        else:
            # Ask the control's override to process the input, returning whether
            # it handled the input or not, or if it wants to be called back as a
            # deferred input if no other controls handle it.
            return self.handle_input(event)

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        """
        Override this in your subclass to handle input. Return a True if your
        control handled the input (it will not be propagated futher). Return a
        False if your control did not handle the input (it will be propagated
        to other components). Return a DeferredInput callback if you wish to
        handle the input as long as no other control handles the input first.
        """
        return False

    def put_setting(self, name: str, setting: "SettingT") -> "SettingT":
        self.settings[name] = setting
        return setting

    def get_setting(
        self,
        name: str,
        expected_type: Type["SettingT"],
        default: Optional["SettingT"] = None,
    ) -> "SettingT":
        if name not in self.settings:
            if default is not None:
                return default
            raise Exception("Invalid setting {}".format(name))
        setting = self.settings[name]
        if not isinstance(setting, expected_type):
            raise Exception("Invalid setting {}".format(name))
        return setting

    def get_optional_setting(
        self, name: str, expected_type: Type["SettingT"]
    ) -> Optional["SettingT"]:
        if name not in self.settings:
            return None
        setting = self.settings[name]
        if not isinstance(setting, expected_type):
            raise Exception("Invalid setting {}".format(name))
        return setting

    def del_setting(self, name: str) -> None:
        if name in self.settings:
            del self.settings[name]

    def __repr__(self) -> str:
        return "{}()".format(self.__class__.__name__)


ComponentT = TypeVar("ComponentT", bound=Component)


class EmptyComponent(Component):
    pass


def _text_to_hotkeys(text: str) -> Tuple[str, Optional[str]]:
    hotkey = None
    last_char = None
    output = ""

    for char in text:
        if char == "&":
            # Either output it if its escaped from last time, or
            # don't output it at all waiting to see what follows it.
            if last_char == "&":
                # Escaped & character
                output = output + "&"
                last_char = None
                continue
        elif last_char == "&":
            # If we have no hotkey, capture this as the hotkey and label
            # it as such.
            if hotkey is None and char.isalnum():
                hotkey = char
                output = output + "<underline>" + char + "</underline>"
            else:
                # We already got our hotkey, or this is an invalid hotkey
                output = output + char
        else:
            # Just copy the input
            output = output + char

        # Remember this for next time
        last_char = char

    if hotkey is not None:
        return (output, hotkey.lower())
    else:
        return (output, None)


class LabelComponent(Component):
    def __init__(
        self,
        text: str = "",
        *,
        textcolor: Optional[Color] = None,
        backcolor: Optional[Color] = None,
        invert: bool = False,
        formatted: bool = False,
        centered: bool = False
    ) -> None:
        super().__init__()
        self.__text = text
        self.__forecolor = textcolor or Color.NONE
        self.__backcolor = backcolor or Color.NONE
        self.__invert = invert
        self.__rendered = False
        self.__formatted = formatted
        self.__centered = centered
        self.__visible = True

    def render(self, context: RenderContext) -> None:
        if not self.__visible:
            self.__rendered = True
            return

        if self.__invert or (self.__backcolor != Color.NONE):
            # Fill the entire label so that it is fully inverted
            for line in range(context.bounds.height):
                context.draw_string(
                    line,
                    0,
                    " " * context.bounds.width,
                    forecolor=self.__forecolor,
                    backcolor=self.__backcolor,
                    invert=True,
                )
        else:
            # Erase the background because labels aren't clear.
            context.clear()

        # Display differently depending on if the text is formatted or not
        if self.__formatted:
            if self.__invert:
                pre = "<invert>"
                post = "</invert>"
            else:
                pre = ""
                post = ""
            if self.__forecolor != Color.NONE or self.__backcolor != Color.NONE:
                pre = pre + "<{},{}>".format(
                    self.__forecolor.name.lower(), self.__backcolor.name.lower()
                )
                post = (
                    "</{},{}>".format(
                        self.__forecolor.name.lower(), self.__backcolor.name.lower()
                    )
                    + post
                )
            context.draw_formatted_string(
                0, 0, pre + self.__text + post, wrap=True, centered=self.__centered
            )
        else:
            context.draw_string(
                0,
                0,
                self.__text,
                forecolor=self.__forecolor,
                backcolor=self.__backcolor,
                invert=self.__invert,
                wrap=True,
                centered=self.__centered,
            )

        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    @property
    def text(self) -> str:
        return self.__text

    @text.setter
    def text(self, text: str) -> None:
        with self.lock:
            self.__rendered = False if not self.__rendered else (self.__text == text)
            self.__text = text

    @property
    def textcolor(self) -> Color:
        return self.__forecolor

    @textcolor.setter
    def textcolor(self, textcolor: Color) -> None:
        with self.lock:
            self.__rendered = (
                False if not self.__rendered else (self.__forecolor == textcolor)
            )
            self.__forecolor = textcolor

    @property
    def backcolor(self) -> Color:
        return self.__backcolor

    @backcolor.setter
    def backcolor(self, backcolor: Color) -> None:
        with self.lock:
            self.__rendered = (
                False if not self.__rendered else (self.__backcolor == backcolor)
            )
            self.__backcolor = backcolor

    @property
    def invert(self) -> bool:
        return self.__invert

    @invert.setter
    def invert(self, invert: bool) -> None:
        with self.lock:
            self.__rendered = (
                False if not self.__rendered else (self.__invert == invert)
            )
            self.__invert = invert

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        with self.lock:
            self.__rendered = (
                False if not self.__rendered else (self.__visible == visible)
            )
            self.__visible = visible

    def __repr__(self) -> str:
        return "LabelComponent(text={})".format(self.__text)


ClickableComponentT = TypeVar("ClickableComponentT", bound="ClickableComponent")


class ClickableComponent(Component):

    callback: Optional[Callable[[Component, Buttons], bool]] = None

    def on_click(
        self: ClickableComponentT, callback: Callable[[Component, Buttons], bool]
    ) -> ClickableComponentT:
        self.callback = callback
        return self

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        # Overrides handle_input instead of _handle_input because this is
        # meant to be used as either a mixin. This handles input entirely,
        # instead of intercepting it, so thus overriding the public function.
        if isinstance(event, MouseInputEvent):
            if self.callback is not None:
                handled = self.callback(self, event.button)
                # Fall through to default if the callback didn't handle.
                if bool(handled):
                    return handled
            else:
                # We still handled this regardless of notification
                return True

        return super().handle_input(event)


HotkeyableComponentT = TypeVar("HotkeyableComponentT", bound="HotkeyableComponent")


class HotkeyableComponent(Component):

    hotkey: Optional[str] = None

    def set_hotkey(self: HotkeyableComponentT, key: str) -> HotkeyableComponentT:
        if key.isalnum():
            self.hotkey = key.lower()
        return self

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        # Overrides handle_input instead of _handle_input because this is
        # meant to be used as either a mixin. This handles input entirely,
        # instead of intercepting it, so thus overriding the public function.
        if self.hotkey is not None:
            if isinstance(event, KeyboardInputEvent):
                if event.character != self.hotkey:
                    # Wrong input, defer to other mixins
                    return super().handle_input(event)

                callback = cast(
                    Optional[Callable[[Component, Buttons], bool]],
                    getattr(self, "callback", None),
                )
                if callback is not None:
                    handled = callback(self, Buttons.KEY)
                    # Fall through to default if the callback didn't handle
                    if bool(handled):
                        return handled
                else:
                    # We still handled this regardless of notification
                    return True

        return super().handle_input(event)


class ButtonComponent(HotkeyableComponent, ClickableComponent, Component):
    def __init__(
        self,
        text: str = "",
        *,
        textcolor: Optional[Color] = None,
        bordercolor: Optional[Color] = None,
        invert: bool = False,
        formatted: bool = False,
        centered: bool = False
    ) -> None:
        super().__init__()
        text, hotkey = _text_to_hotkeys(text)
        self.__label = LabelComponent(
            text,
            textcolor=textcolor,
            formatted=formatted,
            centered=centered,
            invert=invert,
        )
        self.__border = BorderComponent(
            PaddingComponent(self.__label, horizontalpadding=1),
            style=BorderComponent.DOUBLE
            if Settings.enable_unicode
            else BorderComponent.ASCII,
            bordercolor=bordercolor,
        )
        if hotkey:
            self.set_hotkey(hotkey)

    def render(self, context: RenderContext) -> None:
        self.__border._render(context, context.bounds)

    @property
    def dirty(self) -> bool:
        return self.__border.dirty or self.__label.dirty

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__border._attach(scene, settings)

    def detach(self) -> None:
        self.__border._detach()

    def tick(self) -> None:
        self.__border.tick()

    @property
    def text(self) -> str:
        return self.__label.text

    @text.setter
    def text(self, text: str) -> None:
        with self.lock:
            self.__label.text = text

    @property
    def textcolor(self) -> Color:
        return self.__label.textcolor

    @textcolor.setter
    def textcolor(self, color: Color) -> None:
        with self.lock:
            self.__label.textcolor = color

    @property
    def bordercolor(self) -> Color:
        return self.__border.bordercolor

    @bordercolor.setter
    def bordercolor(self, color: Color) -> None:
        with self.lock:
            self.__border.bordercolor = color

    @property
    def invert(self) -> bool:
        return self.__label.invert

    @invert.setter
    def invert(self, invert: bool) -> None:
        with self.lock:
            self.__label.invert = invert

    @property
    def visible(self) -> bool:
        return self.__border.visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        with self.lock:
            self.__border.visible = visible

    def __repr__(self) -> str:
        return "ButtonComponent(text={})".format(self.__label.text)


class BorderComponent(Component):

    SOLID = "SOLID"
    ASCII = "ASCII"
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"

    def __init__(
        self,
        component: Component,
        *,
        style: Optional[str] = None,
        bordercolor: Optional[Color] = None
    ) -> None:
        super().__init__()
        self.__component = component
        self.__style = style or BorderComponent.SOLID
        self.__color = bordercolor or Color.NONE
        self.__drawn = False
        self.__visible = True

        if self.__style in [self.SINGLE, self.DOUBLE] and not Settings.enable_unicode:
            raise ComponentException(
                "Unicode is not enabled, cannot use {} border style!".format(
                    self.__style
                )
            )

    @property
    def dirty(self) -> bool:
        return (not self.__drawn) or self.__component.dirty

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        innerbounds = self.__component.bounds
        if innerbounds is None:
            return None
        return BoundingRectangle(
            top=0,
            bottom=(innerbounds.height + 2) if (innerbounds.height > 0) else 0,
            left=0,
            right=(innerbounds.width + 2) if (innerbounds.width > 0) else 0,
        )

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        self.__drawn = True
        if not self.__visible:
            return

        context.clear()

        for x in range(context.bounds.width):
            if self.__style == BorderComponent.SOLID:
                context.draw_string(0, x, " ", invert=True, forecolor=self.__color)
                context.draw_string(
                    context.bounds.height - 1,
                    x,
                    " ",
                    invert=True,
                    forecolor=self.__color,
                )
            elif self.__style == BorderComponent.ASCII:
                context.draw_string(0, x, "-", forecolor=self.__color)
                context.draw_string(
                    context.bounds.height - 1, x, "-", forecolor=self.__color
                )
            elif self.__style == BorderComponent.SINGLE:
                context.draw_string(0, x, "\u2500", forecolor=self.__color)
                context.draw_string(
                    context.bounds.height - 1, x, "\u2500", forecolor=self.__color
                )
            elif self.__style == BorderComponent.DOUBLE:
                context.draw_string(0, x, "\u2550", forecolor=self.__color)
                context.draw_string(
                    context.bounds.height - 1, x, "\u2550", forecolor=self.__color
                )
            else:
                raise ComponentException("Invalid border style {}".format(self.__style))

        for y in range(1, context.bounds.height - 1):
            if self.__style == BorderComponent.SOLID:
                context.draw_string(y, 0, " ", invert=True, forecolor=self.__color)
                context.draw_string(
                    y,
                    context.bounds.width - 1,
                    " ",
                    invert=True,
                    forecolor=self.__color,
                )
            elif self.__style == BorderComponent.ASCII:
                context.draw_string(y, 0, "|", forecolor=self.__color)
                context.draw_string(
                    y, context.bounds.width - 1, "|", forecolor=self.__color
                )
            elif self.__style == BorderComponent.SINGLE:
                context.draw_string(y, 0, "\u2502", forecolor=self.__color)
                context.draw_string(
                    y, context.bounds.width - 1, "\u2502", forecolor=self.__color
                )
            elif self.__style == BorderComponent.DOUBLE:
                context.draw_string(y, 0, "\u2551", forecolor=self.__color)
                context.draw_string(
                    y, context.bounds.width - 1, "\u2551", forecolor=self.__color
                )
            else:
                raise ComponentException("Invalid border style {}".format(self.__style))

        if self.__style == BorderComponent.ASCII:
            context.draw_string(0, 0, "+", forecolor=self.__color)
            context.draw_string(
                0, context.bounds.width - 1, "+", forecolor=self.__color
            )
            context.draw_string(
                context.bounds.height - 1, 0, "+", forecolor=self.__color
            )
            context.draw_string(
                context.bounds.height - 1,
                context.bounds.width - 1,
                "+",
                forecolor=self.__color,
            )
        elif self.__style == BorderComponent.SINGLE:
            context.draw_string(0, 0, "\u250C", forecolor=self.__color)
            context.draw_string(
                0, context.bounds.width - 1, "\u2510", forecolor=self.__color
            )
            context.draw_string(
                context.bounds.height - 1, 0, "\u2514", forecolor=self.__color
            )
            context.draw_string(
                context.bounds.height - 1,
                context.bounds.width - 1,
                "\u2518",
                forecolor=self.__color,
            )
        elif self.__style == BorderComponent.DOUBLE:
            context.draw_string(0, 0, "\u2554", forecolor=self.__color)
            context.draw_string(
                0, context.bounds.width - 1, "\u2557", forecolor=self.__color
            )
            context.draw_string(
                context.bounds.height - 1, 0, "\u255A", forecolor=self.__color
            )
            context.draw_string(
                context.bounds.height - 1,
                context.bounds.width - 1,
                "\u255D",
                forecolor=self.__color,
            )

        if context.bounds.width > 2 and context.bounds.height > 2:
            self.__component._render(
                context,
                BoundingRectangle(
                    top=context.bounds.top + 1,
                    bottom=context.bounds.bottom - 1,
                    left=context.bounds.left + 1,
                    right=context.bounds.right - 1,
                ),
            )

    @property
    def bordercolor(self) -> Color:
        return self.__color

    @bordercolor.setter
    def bordercolor(self, color: Color) -> None:
        with self.lock:
            self.__drawn = False if not self.__drawn else (self.__color == color)
            self.__color = color

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        with self.lock:
            self.__drawn = False if not self.__drawn else (self.__visible == visible)
            self.__visible = visible

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        return self.__component._handle_input(event)

    def __repr__(self) -> str:
        return "BorderComponent({})".format(repr(self.__component))


class ListComponent(Component):

    DIRECTION_TOP_TO_BOTTOM = "top_to_bottom"
    DIRECTION_LEFT_TO_RIGHT = "left_to_right"

    def __init__(
        self,
        components: Sequence[Component],
        *,
        direction: str,
        size: Optional[int] = None
    ) -> None:
        super().__init__()
        self.__components = components
        self.__size = size
        self.__direction = direction
        self.__visible = True

    @property
    def dirty(self) -> bool:
        return any(component.dirty for component in self.__components)

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        perpendicular = 0
        element_size = self.__get_size(None)
        if element_size is None:
            return None

        for component in self.__components:
            innerbounds = component.bounds
            if innerbounds is None:
                return None

            if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
                perpendicular = max(perpendicular, innerbounds.width)
            elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
                perpendicular = max(perpendicular, innerbounds.height)
            else:
                raise ComponentException(
                    "Invalid direction {}".format(self.__direction)
                )

        if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
            return BoundingRectangle(
                top=0,
                bottom=len(self.__components) * element_size,
                left=0,
                right=perpendicular,
            )
        elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
            return BoundingRectangle(
                top=0,
                bottom=perpendicular,
                left=0,
                right=len(self.__components) * element_size,
            )
        else:
            raise ComponentException("Invalid direction {}".format(self.__direction))

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        for component in self.__components:
            component._attach(scene, settings)

    def detach(self) -> None:
        for component in self.__components:
            component._detach()

    def tick(self) -> None:
        for component in self.__components:
            component.tick()

    def __get_size(self, context: Optional[RenderContext]) -> Optional[int]:
        if self.__size is None:
            if context is None:
                return None
            if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
                size = int(context.bounds.height / len(self.__components))
            elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
                size = int(context.bounds.width / len(self.__components))
            else:
                raise ComponentException(
                    "Invalid direction {}".format(self.__direction)
                )
        else:
            size = self.__size
        if size is None:
            raise Exception("Logic error!")
        if size < 1:
            size = 1
        return size

    def render(self, context: RenderContext) -> None:
        if not self.__components or not self.__visible:
            return

        size = self.__get_size(context)
        if size is None:
            raise Exception("Logic error!")

        offset = 0
        for component in self.__components:
            if self.__direction == self.DIRECTION_TOP_TO_BOTTOM:
                if offset >= context.bounds.height:
                    break

                componenttop = context.bounds.top + offset
                componentbottom = context.bounds.top + offset + size
                if componentbottom > context.bounds.bottom:
                    componentbottom = context.bounds.bottom

                bounds = BoundingRectangle(
                    top=componenttop,
                    bottom=componentbottom,
                    left=context.bounds.left,
                    right=context.bounds.right,
                )
            elif self.__direction == self.DIRECTION_LEFT_TO_RIGHT:
                if offset >= context.bounds.width:
                    break

                componentleft = context.bounds.left + offset
                componentright = context.bounds.left + offset + size
                if componentright > context.bounds.right:
                    componentright = context.bounds.right

                bounds = BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=componentleft,
                    right=componentright,
                )
            else:
                raise ComponentException(
                    "Invalid direction {}".format(self.__direction)
                )

            offset += size
            component._render(context, bounds)

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        # First, try all the controls we manage, seeing if any of them
        # handle the input. If any defer, save it for later.
        deferred: List[DeferredInput] = []
        for component in self.__components:
            handled = component._handle_input(event)
            if isinstance(handled, bool):
                if handled:
                    return handled
            else:
                deferred.append(handled)

        # Nobody deferred, and we didn't get any controls that handled
        # the input, so state that.
        if not deferred:
            return False

        # Create a function that loops through our deferred controls and
        # tries each one until we find one that handles the input.
        def _defer() -> bool:
            for callback in deferred:
                if callback():
                    return True
            return False

        return _defer

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        with self.lock:
            self.__visible = visible

    def __repr__(self) -> str:
        return "ListComponent({}, direction={})".format(
            ",".join(repr(c) for c in self.__components), self.__direction
        )


class StickyComponent(Component):

    LOCATION_TOP = "top"
    LOCATION_BOTTOM = "bottom"
    LOCATION_LEFT = "left"
    LOCATION_RIGHT = "right"

    def __init__(
        self,
        stickycomponent: Component,
        othercomponent: Component,
        *,
        location: str,
        size: int
    ) -> None:
        super().__init__()
        self.__components = [stickycomponent, othercomponent]
        self.__size = size
        self.__location = location
        self.__visible = True

    @property
    def dirty(self) -> bool:
        return any(component.dirty for component in self.__components)

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        stickybounds, otherbounds = (
            self.__components[0].bounds,
            self.__components[1].bounds,
        )
        if stickybounds is None or otherbounds is None:
            return None

        if self.__location in [self.LOCATION_TOP, self.LOCATION_BOTTOM]:
            return BoundingRectangle(
                top=0,
                bottom=otherbounds.height + self.__size,
                left=0,
                right=max(stickybounds.width, otherbounds.width),
            )
        elif self.__location in [self.LOCATION_LEFT, self.LOCATION_RIGHT]:
            return BoundingRectangle(
                top=0,
                bottom=max(stickybounds.height, otherbounds.height),
                left=0,
                right=otherbounds.width + self.__size,
            )
        else:
            raise ComponentException("Invalid location {}".format(self.__location))

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        for component in self.__components:
            component._attach(scene, settings)

    def detach(self) -> None:
        for component in self.__components:
            component._detach()

    def tick(self) -> None:
        for component in self.__components:
            component.tick()

    def __get_size(self) -> int:
        size = self.__size
        if size < 1:
            size = 1
        return size

    def render(self, context: RenderContext) -> None:
        if not self.__visible:
            return

        size = self.__get_size()

        # Set up the bounds for the sticky component then the other component.
        # Has the same traversal order as self.__components on purpose.
        if self.__location == self.LOCATION_TOP:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.top + size,
                    left=context.bounds.left,
                    right=context.bounds.right,
                ),
                BoundingRectangle(
                    top=context.bounds.top + size,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.right,
                ),
            ]
        elif self.__location == self.LOCATION_BOTTOM:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.bottom - size,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.right,
                ),
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom - size,
                    left=context.bounds.left,
                    right=context.bounds.right,
                ),
            ]
        elif self.__location == self.LOCATION_LEFT:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.left + size,
                ),
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left + size,
                    right=context.bounds.right,
                ),
            ]
        elif self.__location == self.LOCATION_RIGHT:
            bounds = [
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.right - size,
                    right=context.bounds.right,
                ),
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.bottom,
                    left=context.bounds.left,
                    right=context.bounds.right - size,
                ),
            ]
        else:
            raise ComponentException("Invalid location {}".format(self.__location))

        for i in range(len(self.__components)):
            component = self.__components[i]
            cbounds = bounds[i]
            if cbounds.width > 0 and cbounds.height > 0:
                component._render(context, cbounds)

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        # First, try all the controls we manage, seeing if any of them
        # handle the input. If any defer, save it for later.
        deferred: List[DeferredInput] = []
        for component in self.__components:
            handled = component._handle_input(event)
            if isinstance(handled, bool):
                if handled:
                    return handled
            else:
                deferred.append(handled)

        # Nobody deferred, and we didn't get any controls that handled
        # the input, so state that.
        if not deferred:
            return False

        # Create a function that loops through our deferred controls and
        # tries each one until we find one that handles the input.
        def _defer() -> bool:
            for callback in deferred:
                if callback():
                    return True
            return False

        return _defer

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        with self.lock:
            self.__visible = visible

    def __repr__(self) -> str:
        return "StickyComponent({}, location={})".format(
            ",".join(repr(c) for c in self.__components), self.__location
        )


class PaddingComponent(Component):
    def __init__(self, component: Component, **kwargs: int) -> None:
        super().__init__()
        self.__component: Component = component
        self.__leftpad: int = 0
        self.__rightpad: int = 0
        self.__toppad: int = 0
        self.__bottompad: int = 0

        if "padding" in kwargs:
            self.__leftpad = (
                self.__rightpad
            ) = self.__toppad = self.__bottompad = kwargs["padding"]
        if "verticalpadding" in kwargs:
            self.__toppad = self.__bottompad = kwargs["verticalpadding"]
        if "horizontalpadding" in kwargs:
            self.__leftpad = self.__rightpad = kwargs["horizontalpadding"]
        if "leftpadding" in kwargs:
            self.__leftpad = kwargs["leftpadding"]
        if "rightpadding" in kwargs:
            self.__rightpad = kwargs["rightpadding"]
        if "toppadding" in kwargs:
            self.__toppad = kwargs["toppadding"]
        if "bottompadding" in kwargs:
            self.__bottompad = kwargs["bottompadding"]

    @property
    def dirty(self) -> bool:
        return self.__component.dirty

    @property
    def bounds(self) -> Optional[BoundingRectangle]:
        innerbounds = self.__component.bounds
        if innerbounds is None:
            return None
        return BoundingRectangle(
            top=0,
            bottom=(innerbounds.height + self.__toppad + self.__bottompad)
            if (innerbounds.height > 0)
            else 0,
            left=0,
            right=(innerbounds.width + self.__leftpad + self.__rightpad)
            if (innerbounds.width > 0)
            else 0,
        )

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        bounds = BoundingRectangle(
            top=context.bounds.top + self.__toppad,
            bottom=context.bounds.bottom - self.__bottompad,
            left=context.bounds.left + self.__leftpad,
            right=context.bounds.right - self.__rightpad,
        )

        if bounds.width <= 0 or bounds.height <= 0:
            return

        self.__component._render(context, bounds)

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        return self.__component._handle_input(event)

    def __repr__(self) -> str:
        return "PaddingComponent({})".format(repr(self.__component))


class DialogBoxComponent(Component):
    def __init__(
        self,
        text: str,
        options: Sequence[Tuple[str, Callable[[Component, str], Any]]],
        *,
        padding: int = 5,
        formatted: bool = False,
        centered: bool = False,
        escape_option: Optional[str] = None
    ) -> None:
        super().__init__()
        self.__text = text
        self.__padding = padding
        self.__escape_callback: Optional[Callable[[], bool]] = None

        buttons: List[Component] = []

        def __cb(
            button: Buttons, option: str, callback: Callable[[Component, str], Any]
        ) -> bool:
            if button == Buttons.LEFT or button == Buttons.KEY:
                callback(self, option)
            return True

        for option, callback in options:
            text, hotkey = _text_to_hotkeys(option)

            def __create_cb(
                option: str, callback: Callable[[Component, str], Any]
            ) -> Callable[[Component, Buttons], bool]:
                def __closure_cb(component: Component, button: Buttons) -> bool:
                    return __cb(button, option, callback)

                return __closure_cb

            entry = ButtonComponent(text, formatted=True).on_click(
                __create_cb(option, callback)
            )
            if hotkey is not None:
                entry = entry.set_hotkey(hotkey)
            if option == escape_option:
                self.__escape_callback = lambda: __cb(Buttons.KEY, option, callback)
            buttons.append(PaddingComponent(entry, horizontalpadding=1))

        self.__component = PaddingComponent(
            BorderComponent(
                PaddingComponent(
                    StickyComponent(
                        ListComponent(
                            buttons, direction=ListComponent.DIRECTION_LEFT_TO_RIGHT
                        ),
                        LabelComponent(
                            self.__text, formatted=formatted, centered=centered
                        ),
                        size=3,
                        location=StickyComponent.LOCATION_BOTTOM,
                    ),
                    padding=1,
                ),
            ),
            padding=self.__padding,
        )

    @property
    def dirty(self) -> bool:
        return self.__component.dirty

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        self.__component._render(context, context.bounds)

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        if isinstance(event, KeyboardInputEvent):
            if event.character == Keys.ESCAPE:
                cb = self.__escape_callback
                if cb is not None:
                    cb()
                    return True
        handled = self.__component._handle_input(event)
        if isinstance(handled, bool):
            # Swallow events, since we don't want this to be closeable or to allow clicks
            # behind it.
            return True

        # Return the deferred input callback to be processed. Swallow inputs on this
        # as well. Create a local because mypy seems to lose the type information when
        # creating a closure over handled.
        deferredcallback: DeferredInput = handled

        def _defer() -> bool:
            deferredcallback()
            return True

        return _defer

    def __repr__(self) -> str:
        return "DialogBoxComponent(text={})".format(self.__text)


class MenuComponent(Component):
    pass


class MenuEntryComponent(HotkeyableComponent, ClickableComponent, MenuComponent):
    def __init__(self, text: str = "", *, expandable: bool = False) -> None:
        super().__init__()
        self.__text = text
        self.__expandable = expandable
        self.__rendered = False
        self.__animating = False
        self.__animation_spot = 0

    def render(self, context: RenderContext) -> None:
        context.clear()
        invert = self.__animating and (self.__animation_spot & 1) != 0
        if invert:
            # Fill the entire label so that it is fully inverted
            for line in range(context.bounds.height):
                context.draw_string(line, 0, " " * context.bounds.width, invert=True)
        else:
            context.clear()
        if invert:
            pre = "<invert>"
            post = "</invert>"
        else:
            pre = ""
            post = ""
        context.draw_formatted_string(0, 0, pre + " " + self.__text + " " + post)
        if self.__expandable:
            context.draw_formatted_string(
                0, context.bounds.width - 2, pre + " >" + post
            )
        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    @property
    def bounds(self) -> BoundingRectangle:
        return BoundingRectangle(
            top=0,
            bottom=1,
            left=0,
            right=RenderContext.formatted_string_length(self.__text)
            + (3 if self.__expandable else 2),
        )

    def tick(self) -> None:
        self.__animation_spot += 1
        if self.__animating:
            self.__rendered = False

    @property
    def animating(self) -> bool:
        return self.__animating

    @animating.setter
    def animating(self, animating: bool) -> None:
        with self.lock:
            self.__rendered = (
                False if not self.__rendered else (self.__animating == animating)
            )
            self.__animating = animating
            self.__animation_spot = 1

    @property
    def text(self) -> str:
        return self.__text

    def __repr__(self) -> str:
        return "MenuEntryComponent(text={})".format(self.__text)


class MenuSeparatorComponent(MenuComponent):
    def __init__(self) -> None:
        super().__init__()
        self.__rendered = False

    def render(self, context: RenderContext) -> None:
        context.clear()
        context.draw_string(
            0, 0, ("\u2500" if Settings.enable_unicode else "-") * context.bounds.width
        )
        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    @property
    def bounds(self) -> BoundingRectangle:
        return BoundingRectangle(
            top=0,
            bottom=1,
            left=0,
            right=0,
        )

    def __repr__(self) -> str:
        return "MenuSeparatorComponent()"


class PopoverMenuComponent(Component):
    def __init__(
        self, options: Sequence[Tuple[str, Any]], *, animated: bool = False
    ) -> None:
        super().__init__()
        self.__parent: Optional["PopoverMenuComponent"] = None
        self.__children: List["PopoverMenuComponent"] = []
        self.__animated: bool = animated
        self.__closecb: Optional[Callable[[], None]] = None
        self.__closedelay: int = 0

        entries: List[MenuComponent] = []

        def __cb(
            component: Component,
            button: Buttons,
            option: str,
            callback: Callable[[Component, str], None],
        ) -> bool:
            if not isinstance(component, MenuEntryComponent):
                raise Exception("Logic error, called from wrong component!")

            if self.__is_closing():  # pyre-ignore Pyre can't see that this exists.
                return True
            if button == Buttons.LEFT or button == Buttons.KEY:
                if self.__animated:  # pyre-ignore Pyre can't see that this exists.

                    def __closeaction() -> None:
                        callback(self, option)
                        self.__close()

                    # Delayed close
                    component.animating = True
                    self.__closecb = __closeaction
                    self.__closedelay = 12
                else:
                    callback(self, option)
                    self.__close()  # pyre-ignore Pyre can't see that this exists.
            return True

        def __new_menu(
            button: Buttons, position: int, menuentries: Sequence[Tuple[str, Any]]
        ) -> bool:
            if button == Buttons.LEFT or button == Buttons.KEY:
                menu = PopoverMenuComponent(
                    menuentries, animated=self.__animated
                )  # pyre-ignore Pyre can't see that this exists.
                menu.__parent = self
                self.register(menu, menu.bounds.offset(position, self.bounds.width))
                self.__children.append(
                    menu
                )  # pyre-ignore Pyre can't see that this exists.
            return True

        position = 0
        for option, callback in options:
            position += 1
            if option == "-":
                # Separator
                entries.append(MenuSeparatorComponent())
            elif isinstance(callback, list):
                # Submenu
                text, hotkey = _text_to_hotkeys(option)

                def __create_submenu_cb(
                    position: int, menuentries: Sequence[Tuple[str, Any]]
                ) -> Callable[[Component, Buttons], bool]:
                    def __closure_cb(component: Component, button: Buttons) -> bool:
                        return __new_menu(button, position - 1, menuentries)

                    return __closure_cb

                entry = MenuEntryComponent(text, expandable=True).on_click(
                    __create_submenu_cb(position, callback)
                )
                if hotkey is not None:
                    entry = entry.set_hotkey(hotkey)
                entries.append(entry)
            else:
                # Menu Entry
                text, hotkey = _text_to_hotkeys(option)

                def __create_menuentry_cb(
                    option: str, callback: Callable[[Component, str], None]
                ) -> Callable[[Component, Buttons], bool]:
                    def __closure_cb(component: Component, button: Buttons) -> bool:
                        # The typing here is a bit weird, what's really going on is that this closure callback
                        # will get passed into the menu entry component's on_click(), meaning that technically
                        # component is a "MenuEntryComponent" since callbacks always get the self type. However,
                        # that doesn't work with our mixin strategy. So, for better or worse, we will need to
                        # change the signature of __cb and assert on the type dynamically.
                        return __cb(component, button, option, callback)

                    return __closure_cb

                entry = MenuEntryComponent(text).on_click(
                    __create_menuentry_cb(option, callback)
                )
                if hotkey is not None:
                    entry = entry.set_hotkey(hotkey)
                entries.append(entry)

        self.__component = BorderComponent(
            ListComponent(
                entries,
                direction=ListComponent.DIRECTION_TOP_TO_BOTTOM,
                size=1,
            ),
        )
        self.__entries: List[MenuComponent] = entries

    def __close(self, *, close_parent: bool = True) -> None:
        self.unregister(self)
        if self.__parent is not None and close_parent:
            self.__parent.__close()
        for child in self.__children:
            # Kill our link so we don't recurse indefinitely
            child.__parent = None
            child.__close()

    @property
    def dirty(self) -> bool:
        return self.__component.dirty

    @property
    def bounds(self) -> BoundingRectangle:
        return BoundingRectangle(
            top=0,
            bottom=len(self.__entries) + 2,
            left=0,
            right=max(e.bounds.width for e in self.__entries if e.bounds is not None)
            + 2,
        )

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        if self.__animated and self.__closedelay > 0:
            self.__closedelay -= 1
        if self.__closedelay == 0 and self.__closecb is not None:
            self.__closecb()
            self.__closecb = None
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        self.__component._render(context, context.bounds)

    def __is_closing(self) -> bool:
        if self.__closecb is not None:
            return True
        if self.__parent is not None and self.__parent.__closecb is not None:
            return True
        for child in self.__children:
            if child.__closecb is not None:
                return True
        return False

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        # If we're closing, swallow ALL inputs so we can't double-choose
        if self.__is_closing():
            return True

        handled = self.__component._handle_input(event)
        if self.__parent is not None:
            # Allow closing submenus by clicking other menu entries.
            if isinstance(event, DefocusInputEvent):
                self.__close(close_parent=False)
            # Treat mouse events as handled, since we don't want to close on
            # border clicks which are otherwise unhandled.
            if isinstance(event, MouseInputEvent):
                handled = True

            # Top level will handle outside clicks
            return handled

        if not handled:
            # Make sure that we close if we're clicked out of or escape is pressed.
            if isinstance(event, KeyboardInputEvent):
                if event.character == Keys.ESCAPE:
                    self.__close()
            elif isinstance(event, DefocusInputEvent):
                self.__close()

        # Swallow events, since we don't want this to be closeable or to allow clicks
        # behind it.
        return True

    def __repr__(self) -> str:
        return "PopoverMenuComponent({})".format(
            ",".join(str(e) for e in self.__entries)
        )


class MonochromePictureComponent(Component):

    SIZE_FULL = "SIZE_FULL"
    SIZE_HALF = "SIZE_HALF"

    def __init__(
        self,
        data: Sequence[Sequence[bool]],
        *,
        size: Optional[str] = None,
        forecolor: Optional[Color] = None,
        backcolor: Optional[Color] = None
    ) -> None:
        super().__init__()
        self.__forecolor = forecolor or Color.NONE
        self.__backcolor = backcolor or Color.NONE
        self.__size = size or self.SIZE_FULL
        if self.__size == self.SIZE_HALF and not Settings.enable_unicode:
            raise ComponentException(
                "Unicode is not enabled, cannot use {} drawing style!".format(
                    self.__size
                )
            )
        self.__rendered = False
        self.__set_data_impl(data)

    @property
    def bounds(self) -> BoundingRectangle:
        if self.__size == self.SIZE_FULL:
            return BoundingRectangle(
                top=0,
                bottom=self.__height,
                left=0,
                right=self.__width,
            )
        elif self.__size == self.SIZE_HALF:
            return BoundingRectangle(
                top=0,
                bottom=int((self.__height + 1) / 2),
                left=0,
                right=int((self.__width + 1) / 2),
            )
        else:
            raise ComponentException("Invalid size {}".format(self.__size))

    def render(self, context: RenderContext) -> None:
        if self.__size == self.SIZE_FULL:
            for row in range(self.__height):
                for column in range(self.__width):
                    if Settings.enable_unicode:
                        char = "\u2588" if self.__data[row][column] else " "
                        invert = False
                    else:
                        invert = self.__data[row][column]
                        char = " "

                    context.draw_string(
                        row,
                        column,
                        char,
                        invert=invert,
                        forecolor=self.__forecolor,
                        backcolor=self.__backcolor,
                    )

        if self.__size == self.SIZE_HALF:
            for row in range(int((self.__height + 1) / 2)):
                for column in range(int((self.__width + 1) / 2)):
                    # Grab a quad that represents what graphic to draw
                    quad: List[bool] = (
                        self.__data[row * 2][(column * 2) : ((column * 2) + 2)]
                        + self.__data[(row * 2) + 1][(column * 2) : ((column * 2) + 2)]
                    )
                    quadstr: str = "".join("1" if v else "0" for v in quad)

                    # Look it up
                    if quadstr == "0000":
                        char = " "
                    elif quadstr == "0001":
                        char = "\u2597"
                    elif quadstr == "0010":
                        char = "\u2596"
                    elif quadstr == "0011":
                        char = "\u2584"
                    elif quadstr == "0100":
                        char = "\u259D"
                    elif quadstr == "0101":
                        char = "\u2590"
                    elif quadstr == "0110":
                        char = "\u259E"
                    elif quadstr == "0111":
                        char = "\u259F"
                    elif quadstr == "1000":
                        char = "\u2598"
                    elif quadstr == "1001":
                        char = "\u259A"
                    elif quadstr == "1010":
                        char = "\u258C"
                    elif quadstr == "1011":
                        char = "\u2599"
                    elif quadstr == "1100":
                        char = "\u2580"
                    elif quadstr == "1101":
                        char = "\u259C"
                    elif quadstr == "1110":
                        char = "\u259B"
                    elif quadstr == "1111":
                        char = "\u2588"
                    else:
                        raise Exception(
                            "Logic error, invalid quad '{}'!".format(quadstr)
                        )

                    # Render it
                    context.draw_string(
                        row,
                        column,
                        char,
                        forecolor=self.__forecolor,
                        backcolor=self.__backcolor,
                    )

        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    @property
    def data(self) -> Sequence[Sequence[bool]]:
        return self.__data

    @data.setter
    def data(self, data: Sequence[Sequence[bool]]) -> None:
        with self.lock:
            self.__set_data_impl(data)

    def __set_data_impl(self, data: Sequence[Sequence[bool]]) -> None:
        self.__height = len(data)
        self.__width = max(len(p) for p in data)

        # Chunk our graphics data into groups of 2
        self.__data = [[x for x in row] for row in data]

        if self.__size == self.SIZE_HALF:
            # First, do the easy part of making sure the height is divisible by 2
            if (len(self.__data) & 1) == 1:
                self.__data = [*self.__data, []]

            # Now, do the hard part of making sure the width is divisible by 2
            if (self.__width & 1) == 1:
                desired_width = self.__width + 1
            else:
                desired_width = self.__width
        else:
            desired_width = self.__width

        for i in range(len(self.__data)):
            if len(self.__data[i]) < desired_width:
                self.__data[i] = [
                    *self.__data[i],
                    *([False] * (desired_width - len(self.__data[i]))),
                ]

    @property
    def forecolor(self) -> Color:
        return self.__forecolor

    @forecolor.setter
    def forecolor(self, forecolor: Color) -> None:
        with self.lock:
            self.__rendered = (
                False if not self.__rendered else (self.__forecolor == forecolor)
            )
            self.__forecolor = forecolor

    @property
    def backcolor(self) -> Color:
        return self.__backcolor

    @backcolor.setter
    def backcolor(self, backcolor: Color) -> None:
        with self.lock:
            self.__rendered = (
                False if not self.__rendered else (self.__backcolor == backcolor)
            )
            self.__backcolor = backcolor


class PictureComponent(Component):

    SIZE_FULL = "SIZE_FULL"
    SIZE_HALF = "SIZE_HALF"

    def __init__(
        self, data: Sequence[Sequence[Color]], *, size: Optional[str] = None
    ) -> None:
        super().__init__()
        self.__size = size or self.SIZE_FULL
        if self.__size == self.SIZE_HALF and not Settings.enable_unicode:
            raise ComponentException(
                "Unicode is not enabled, cannot use {} drawing style!".format(
                    self.__size
                )
            )
        self.__rendered = False
        self.__set_data_impl(data)

    @property
    def bounds(self) -> BoundingRectangle:
        if self.__size == self.SIZE_FULL:
            return BoundingRectangle(
                top=0,
                bottom=self.__height,
                left=0,
                right=self.__width,
            )
        elif self.__size == self.SIZE_HALF:
            return BoundingRectangle(
                top=0,
                bottom=int((self.__height + 1) / 2),
                left=0,
                right=int((self.__width + 1) / 2),
            )
        else:
            raise ComponentException("Invalid size {}".format(self.__size))

    def render(self, context: RenderContext) -> None:
        if self.__size == self.SIZE_FULL:
            for row in range(self.__height):
                for column in range(self.__width):
                    char = " "
                    forecolor = Color.NONE
                    backcolor = self.__data[row][column]

                    context.draw_string(
                        row, column, char, forecolor=forecolor, backcolor=backcolor
                    )

        if self.__size == self.SIZE_HALF:
            for row in range(int((self.__height + 1) / 2)):
                for column in range(int((self.__width + 1) / 2)):
                    # Grab a quad that represents what graphic to draw
                    quad = (
                        self.__data[row * 2][(column * 2) : ((column * 2) + 2)]
                        + self.__data[(row * 2) + 1][(column * 2) : ((column * 2) + 2)]
                    )
                    colors = [q for q in quad if q != Color.NONE]
                    forecolor = colors[0] if len(colors) > 0 else Color.NONE
                    backcolor = Color.NONE
                    for color in colors:
                        if color != forecolor:
                            backcolor = color
                            break

                    quadstr = "".join("1" if v == forecolor else "0" for v in quad)
                    if quadstr == "1111" and forecolor == backcolor:
                        quadstr = "0000"

                    # Look it up
                    if quadstr == "0000":
                        char = " "
                    elif quadstr == "0001":
                        char = "\u2597"
                    elif quadstr == "0010":
                        char = "\u2596"
                    elif quadstr == "0011":
                        char = "\u2584"
                    elif quadstr == "0100":
                        char = "\u259D"
                    elif quadstr == "0101":
                        char = "\u2590"
                    elif quadstr == "0110":
                        char = "\u259E"
                    elif quadstr == "0111":
                        char = "\u259F"
                    elif quadstr == "1000":
                        char = "\u2598"
                    elif quadstr == "1001":
                        char = "\u259A"
                    elif quadstr == "1010":
                        char = "\u258C"
                    elif quadstr == "1011":
                        char = "\u2599"
                    elif quadstr == "1100":
                        char = "\u2580"
                    elif quadstr == "1101":
                        char = "\u259C"
                    elif quadstr == "1110":
                        char = "\u259B"
                    elif quadstr == "1111":
                        char = "\u2588"
                    else:
                        raise Exception(
                            "Logic error, invalid quad '{}'!".format(quadstr)
                        )

                    # Render it
                    context.draw_string(
                        row, column, char, forecolor=forecolor, backcolor=backcolor
                    )

        self.__rendered = True

    @property
    def dirty(self) -> bool:
        return not self.__rendered

    @property
    def data(self) -> Sequence[Sequence[Color]]:
        return self.__data

    @data.setter
    def data(self, data: Sequence[Sequence[Color]]) -> None:
        with self.lock:
            self.__set_data_impl(data)

    def __set_data_impl(self, data: Sequence[Sequence[Color]]) -> None:
        self.__height = len(data)
        self.__width = max(len(p) for p in data)

        # Chunk our graphics data into groups of 2
        self.__data = [[x for x in row] for row in data]

        if self.__size == self.SIZE_HALF:
            # First, do the easy part of making sure the height is divisible by 2
            if (len(self.__data) & 1) == 1:
                self.__data = [*self.__data, []]

            # Now, do the hard part of making sure the width is divisible by 2
            if (self.__width & 1) == 1:
                desired_width = self.__width + 1
            else:
                desired_width = self.__width
        else:
            desired_width = self.__width

        for i in range(len(self.__data)):
            if len(self.__data[i]) < desired_width:
                self.__data[i] = [
                    *self.__data[i],
                    *([Color.NONE] * (desired_width - len(self.__data[i]))),
                ]


class TextInputComponent(Component):
    def __init__(
        self,
        text: str,
        *,
        allowed_characters: str,
        focused: bool = False,
        max_length: int = -1,
        cursor_pos: int = -1
    ) -> None:
        super().__init__()
        self.__focused = focused
        self.__cursor = min(
            max(0, len(text) if cursor_pos == -1 else cursor_pos), len(text)
        )
        self.__text = text
        self.__max_length = max_length
        self.__characters = allowed_characters
        self.__changed = True

    @property
    def dirty(self) -> bool:
        return self.__changed

    def render(self, context: RenderContext) -> None:
        text = self.__text
        if len(text) < context.bounds.width:
            text = text + " " * (context.bounds.width - len(text))

        if not self.__focused:
            context.draw_formatted_string(0, 0, "<underline>" + text + "</underline>")
        else:
            if self.__cursor < 0:
                self.__cursor = 0
            if self.__cursor > len(self.__text):
                self.__cursor = len(self.__text)
            context.draw_formatted_string(
                0,
                0,
                "<invert>"
                + text[: self.__cursor]
                + "</invert>"
                + text[self.__cursor : (self.__cursor + 1)]
                + "<invert>"
                + text[(self.__cursor + 1) :]
                + "</invert>",
            )

        self.__changed = False

    @property
    def text(self) -> str:
        return self.__text

    @text.setter
    def text(self, text: str) -> None:
        with self.lock:
            self.__changed = True if self.__changed else (self.__text != text)
            self.__text = text
            self.__cursor = len(text)

    @property
    def focus(self) -> bool:
        return self.__focused

    @focus.setter
    def focus(self, focus: bool) -> None:
        with self.lock:
            self.__changed = True if self.__changed else (self.__focused != focus)
            self.__focused = focus

    @property
    def cursor(self) -> int:
        return self.__cursor

    @cursor.setter
    def cursor(self, cursor: int) -> None:
        with self.lock:
            self.__changed = True if self.__changed else (self.__cursor != cursor)
            self.__cursor = min(max(0, cursor), len(self.__text))

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        def add(char: str) -> None:
            if (
                self.__max_length == -1 or len(self.__text) < self.__max_length
            ):  # pyre-ignore Pyre can't see that this exists.
                self.__text = (
                    self.__text[: self.__cursor] + char + self.__text[self.__cursor :]
                )  # pyre-ignore Pyre can't see that this exists.
                self.__cursor += 1
                self.__changed = True

        if self.__focused:
            if isinstance(event, KeyboardInputEvent):
                if event.character == Keys.LEFT:
                    if self.__cursor > 0:
                        self.__cursor -= 1
                        self.__changed = True
                    return True
                if event.character == Keys.RIGHT:
                    if self.__cursor <= len(self.__text):
                        self.__cursor += 1
                        self.__changed = True
                    return True
                if event.character in self.__characters:
                    add(event.character)
                    return True
                if event.character.upper() in self.__characters:
                    add(event.character.upper())
                    return True
                if event.character.lower() in self.__characters:
                    add(event.character.lower())
                    return True
                if event.character == Keys.DELETE:
                    if self.__cursor < len(self.__text):
                        self.__text = (
                            self.__text[: self.__cursor]
                            + self.__text[(self.__cursor + 1) :]
                        )
                        self.__changed = True
                    return True
                if event.character == Keys.BACKSPACE:
                    if self.__cursor > 0:
                        self.__text = (
                            self.__text[: (self.__cursor - 1)]
                            + self.__text[self.__cursor :]
                        )
                        self.__cursor -= 1
                        self.__changed = True
                    return True
        return False

    def __repr__(self) -> str:
        return "TextInputComponent(text={}, focused={})".format(
            repr(self.__text), "True" if self.__focused else "False"
        )


class SelectInputComponent(Component):
    def __init__(
        self, selected: str, options: Sequence[str], *, focused: bool = False
    ) -> None:
        super().__init__()
        self.__selected = selected
        self.__options = options
        self.__focused = focused
        self.__changed = False
        self.__visible = True
        if selected not in options:
            raise Exception("Selected value must be in options!")

    def render(self, context: RenderContext) -> None:
        if not self.__visible:
            self.__changed = False
            return

        # No artifacts, please!
        context.clear()

        # First, calculate how much area we have for text
        area = context.bounds.width - 4
        if len(self.__selected) > area:
            # Doesn't fit, truncate.
            if Settings.enable_unicode:
                text = self.__selected[: (area - 1)] + "\u2026"
            else:
                text = self.__selected[: (area - 3)] + "..."
        elif area > len(self.__selected):
            # Fits, center
            text = " " * int((area - len(self.__selected)) / 2) + self.__selected
            text = text + " " * (area - len(text))
        else:
            # Exact, just show
            text = self.__selected

        if Settings.enable_unicode:
            text = "\u2039 " + text + " \u203A"
        else:
            text = "< " + text + " >"

        context.draw_string(0, 0, text, invert=self.__focused)
        self.__changed = False

    @property
    def dirty(self) -> bool:
        return self.__changed

    @property
    def options(self) -> Sequence[str]:
        return self.__options

    @property
    def focus(self) -> bool:
        return self.__focused

    @focus.setter
    def focus(self, focus: bool) -> None:
        with self.lock:
            self.__changed = True if self.__changed else (self.__focused != focus)
            self.__focused = focus

    @property
    def selected(self) -> str:
        return self.__selected

    @selected.setter
    def selected(self, selected: str) -> None:
        if selected not in self.__options:
            raise Exception("Selected value must be in options!")
        with self.lock:
            self.__changed = True if self.__changed else (self.__selected != selected)
            self.__selected = selected

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, visible: bool) -> None:
        with self.lock:
            self.__changed = True if self.__changed else (self.__visible != visible)
            self.__visible = visible

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        options = self.__options

        def select_previous() -> None:
            for i, option in enumerate(options):
                if (
                    option == self.__selected
                ):  # pyre-ignore Pyre can't see that this exists.
                    if i > 0:
                        self.__selected = options[i - 1]
                        self.__changed = True
                    return

        def select_next() -> None:
            for i, option in enumerate(options):
                if (
                    option == self.__selected
                ):  # pyre-ignore Pyre can't see that this exists.
                    if i < len(options) - 1:
                        self.__selected = options[i + 1]
                        self.__changed = True
                    return

        if isinstance(event, KeyboardInputEvent):
            if self.__focused:
                if event.character == Keys.LEFT:
                    select_previous()
                    return True
                if event.character == Keys.RIGHT:
                    select_next()
                    return True
        if isinstance(event, MouseInputEvent):
            if event.button == Buttons.LEFT and self.location is not None:
                relx = event.x - self.location.left
                rely = event.y - self.location.top
                if rely == 0 and relx == 0:
                    select_previous()
                elif rely == 0 and relx == self.location.width - 1:
                    select_next()
                return True
        return False

    def __repr__(self) -> str:
        return "SelectInputComponent(selected={}, options={}, focused={})".format(
            repr(self.__selected),
            repr(self.__options),
            "True" if self.__focused else "False",
        )


class CenteredComponent(Component):
    def __init__(self, component: Component, *, width: int, height: int) -> None:
        super().__init__()
        self.__component = component
        self.__width = width
        self.__height = height

    @property
    def dirty(self) -> bool:
        return self.__component.dirty

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        self.__component._attach(scene, settings)

    def detach(self) -> None:
        self.__component._detach()

    def tick(self) -> None:
        self.__component.tick()

    def render(self, context: RenderContext) -> None:
        if self.__width < context.bounds.width:
            xpos = int((context.bounds.width - self.__width) / 2)
            width = self.__width
        else:
            xpos = 0
            width = context.bounds.width

        if self.__height < context.bounds.height:
            ypos = int((context.bounds.height - self.__height) / 2)
            height = self.__height
        else:
            ypos = 0
            height = context.bounds.height

        context.clear()
        bounds = BoundingRectangle(
            top=context.bounds.top + ypos,
            bottom=context.bounds.top + ypos + height,
            left=context.bounds.left + xpos,
            right=context.bounds.left + xpos + width,
        )

        if bounds.width <= 0 or bounds.height <= 0:
            return

        self.__component._render(context, bounds)

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        return self.__component._handle_input(event)

    def __repr__(self) -> str:
        return "CenteredComponent({})".format(repr(self.__component))


class TabComponent(Component):
    def __init__(self, tabs: Sequence[Tuple[str, Component]]) -> None:
        super().__init__()
        self.__buttons = [
            ButtonComponent(
                name,
                formatted=True,
                centered=True,
            ).on_click(lambda component, button: self.__change_tab(component))
            for name, _ in tabs
        ]
        self.__borders = [
            BorderComponent(
                component,
                style=(
                    BorderComponent.SINGLE
                    if Settings.enable_unicode
                    else BorderComponent.ASCII
                ),
            )
            for _, component in tabs
        ]
        self.__tabs = tabs
        self.__selected = 0
        self.__drawn = False
        self.__highlight()

    def __highlight(self) -> None:
        for i, button in enumerate(self.__buttons):
            button.invert = i == self.__selected

    def __change_tab(self, component: Component) -> bool:
        for i, btn in enumerate(self.__buttons):
            if btn is component:
                self.__selected = i
                self.__drawn = False
                self.__highlight()

                return True
        return False

    @property
    def dirty(self) -> bool:
        if not self.__drawn:
            return True
        for component in [*self.__buttons, *self.__borders]:
            if component.dirty:
                return True
        return False

    def attach(self, scene: "Scene", settings: Dict[str, Any]) -> None:
        for component in [*self.__buttons, *self.__borders]:
            component._attach(scene, settings)

    def detach(self) -> None:
        for component in [*self.__buttons, *self.__borders]:
            component._detach()

    def tick(self) -> None:
        for component in [*self.__buttons, *self.__borders]:
            component.tick()

    def handle_input(self, event: "InputEvent") -> Union[bool, DeferredInput]:
        if isinstance(event, KeyboardInputEvent):
            if event.character == Keys.TAB:
                self.__selected = (self.__selected + 1) % len(self.__buttons)
                self.__drawn = False
                self.__highlight()

                return True

        for component in [*self.__buttons, self.__borders[self.__selected]]:
            if component._handle_input(event):
                return True
        return False

    def render(self, context: RenderContext) -> None:
        # Bookkeeping please!
        self.__drawn = True
        context.clear()

        # First, draw the tab buttons.
        for i, button in enumerate(self.__buttons):
            button._render(
                context,
                BoundingRectangle(
                    top=context.bounds.top,
                    bottom=context.bounds.top + 3,
                    left=context.bounds.left + (22 * i),
                    right=context.bounds.left + (22 * i) + 21,
                ),
            )

        # Now, draw the actual component that is selected.
        self.__borders[self.__selected]._render(
            context,
            BoundingRectangle(
                top=context.bounds.top + 3,
                bottom=context.bounds.bottom,
                left=context.bounds.left,
                right=context.bounds.right,
            ),
        )
